---
layout: post
title: "LLM Serving Frameworks #1: Deep Dive into vLLM"
subtitle: "Frontend · Scheduler · Executor · Worker architecture and parallelism strategies"
tags: [LLM, Inference, vLLM, PagedAttention, GPU, AI, Parallelism]
lang: en
translation-url: /2026-06-22-llm-serving-1-vllm-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| 0 | [Overview & Comparison — vLLM, SGLang, TensorRT-LLM](/2026-06-19-llm-serving-overview-en/) | ✅ |
| **1** | **vLLM Deep Dive** | |
| 2 | SGLang Deep Dive | |
| 3 | TensorRT-LLM Deep Dive | |

The [overview post](/2026-06-19-llm-serving-overview-en/) introduced PagedAttention and Continuous Batching at a conceptual level. This post covers the internal structure of vLLM — Frontend, Scheduler, Executor, and Worker — along with its parallelism strategies.

---

## 1. What is vLLM?

**vLLM** is an open-source LLM serving framework released by UC Berkeley in 2023. It is built on the PagedAttention paper presented at SOSP 2023, with the primary goal of maximizing inference throughput in both single-GPU and distributed environments.

Three core contributions define vLLM:

- **PagedAttention**: Manages KV Cache memory using OS-style paging, eliminating memory waste
- **Continuous Batching**: Removes completed requests and inserts new ones at each iteration boundary
- **Multi-hardware support**: NVIDIA, AMD (ROCm), Google TPU, AWS Inferentia

---

## 2. Overall Architecture

![vLLM Architecture](/assets/img/posts/llm-serving-1-vllm/arch-overview.png)

The request processing pipeline flows as follows:

```
HTTP Request
    ↓
[API Server]          ─── FastAPI, OpenAI-compatible
    ↓
[AsyncLLMEngine]      ─── async request queue
    ↓
[LLMEngine]
    ├── [Scheduler]               ─── request scheduling, preemption decisions
    │       └── [BlockSpaceManager]  ─── KV Cache block allocation
    └── [ExecutorBase]
            └── [Worker × N GPU]
                    ├── [ModelRunner]   ─── model forward pass
                    └── [CacheEngine]  ─── KV Cache initialization and transfer
```

---

## 3. Frontend

### API Server

`vllm.entrypoints.openai.api_server` runs a FastAPI HTTP server. The `/v1/chat/completions` and `/v1/completions` endpoints implement the OpenAI API spec exactly, allowing existing OpenAI SDK clients to work without modification.

### AsyncLLMEngine

`AsyncLLMEngine` is an async wrapper around `LLMEngine`. It serves two purposes:

1. Accepts concurrent requests and enqueues them
2. Runs a background loop that repeatedly calls `LLMEngine.step()` to drive the scheduling and execution cycle

Each request receives a unique `request_id`, and generated tokens are streamed back via `AsyncGenerator`.

---

## 4. Scheduler and BlockSpaceManager

### Scheduler

The `Scheduler` manages three queues:

```
waiting  ─── requests not yet started
running  ─── requests currently executing on GPU
swapped  ─── preempted requests whose KV Cache has been moved to CPU
```

At each `step()`, the scheduler decides:

- Which requests in the `running` queue to execute (FCFS by default)
- Whether to **preempt** a running request when KV Cache blocks are exhausted

**Preemption policies:**

| Policy | Mechanism | Cost |
|:---|:---|:---|
| **Swap** | Move KV Cache to CPU RAM, restore later | swap I/O overhead |
| **Recompute** | Discard KV Cache, redo prefill later | recomputation cost |

The default is Recompute. Recomputation is cheaper for short sequences; Swap becomes advantageous for long ones.

**Chunked Prefill** splits long prompts into chunks of `max_num_batched_tokens` and batches them together with decode requests. This eliminates the problem of a single long prefill blocking all decode iterations, allowing fine-grained control over the TTFT / TPOT tradeoff.

### BlockSpaceManager

**BlockSpaceManager** is the memory manager behind PagedAttention.

```
Logical Block         →  Physical Block
  [seq 0: block 0]   →  [GPU block #42]
  [seq 0: block 1]   →  [GPU block #7 ]
  [seq 1: block 0]   →  [GPU block #42]  ← shared (same prefix)
```

Key operations:

- `allocate()`: assign physical blocks to a new request
- `free()`: return blocks when a request completes
- `fork()`: increment `ref_count` for prefix sharing (Copy-on-Write)
- `can_allocate()`: used by the scheduler to decide whether to accept new requests

---

## 5. Executor and Worker

### ExecutorBase

`ExecutorBase` abstracts away the Worker layer. Three implementations exist depending on the deployment environment:

| Implementation | Target |
|:---|:---|
| `GPUExecutor` | Single GPU |
| `MultiprocessingGPUExecutor` | Single node, multiple GPUs |
| `RayGPUExecutor` | Multi-node (Ray cluster) |

When `execute_model()` is called, the Executor broadcasts the command to all Workers. With TP or PP enabled, Workers communicate with each other via NCCL during execution.

### Worker

A `Worker` corresponds to one GPU rank. During initialization, it loads model weights and partitions them according to the TP/PP configuration.

### ModelRunner

`ModelRunner` executes the actual forward pass. The sequence within `execute_model()` is:

1. **Input preparation**: construct token IDs, position IDs, and attention metadata (block table, context lengths)
2. **CUDA Graph or eager execution**: for the decode phase with small, fixed batch sizes, CUDA Graph captures reduce kernel launch overhead
3. **Model forward**: pass through attention → FFN → LayerNorm per layer
4. **Sampling**: apply temperature, top-p, top-k to logits and select the next token

### CacheEngine

`CacheEngine` manages the GPU KV Cache tensors:

- `allocate_gpu_cache()`: allocates per-layer KV Cache tensors at startup
- `swap_in(blocks)` / `swap_out(blocks)`: moves KV Cache between CPU and GPU during preemption
- `copy(src, dst)`: duplicates blocks during Copy-on-Write

---

## 6. Transfer Layer

### Inter-Worker Communication (NCCL)

When TP or PP is active, Workers communicate via NCCL:

| Parallelism | Collective | Trigger |
|:---|:---|:---|
| Tensor Parallel | `all_reduce` | after each attention + FFN layer |
| Pipeline Parallel | `send` / `recv` (P2P) | at each stage boundary |
| Expert Parallel | `all_to_all` | MoE token routing |

### Disaggregated Prefill (P/D Separation)

**Disaggregated Prefill** separates the prefill and decode phases into distinct instances:

```
Prefill Instance               Decode Instance
─────────────────              ─────────────────
prompt → prefill compute       receive KV Cache
generate KV Cache    ───────→  iterate decode
                  KV Transfer  stream tokens back
```

Because prefill is compute-bound and decode is memory-bandwidth-bound, separating them allows each phase to be deployed on hardware (or configuration) optimized for its bottleneck.

vLLM abstracts this transfer layer through the `KVConnector` interface. Implementations like Mooncake and nixl exist; custom connectors can also be written to plug into the interface.

---

## 7. Supported Parallelism

### Tensor Parallelism

![Tensor Parallelism Layout](/assets/img/posts/llm-serving-1-vllm/tp-layout.png)

**Tensor Parallelism (TP)** distributes individual layer computations across GPUs.

- **Attention**: Q/K/V projections split by head (`ColumnParallelLinear`). Each GPU computes attention for its assigned heads and contributes to a final `all_reduce`.
- **FFN**: up-projection uses column parallel; down-projection uses row parallel. Both terminate in `all_reduce`.

`all_reduce` fires at every layer, so communication bandwidth is the limiting factor. **TP is recommended within a single node over NVLink.** Cross-node TP over InfiniBand is possible but incurs higher communication overhead.

```python
vllm serve meta-llama/Llama-3-70B \
  --tensor-parallel-size 4
```

### Pipeline Parallelism

![Pipeline Parallelism Schedule](/assets/img/posts/llm-serving-1-vllm/pp-schedule.png)

**Pipeline Parallelism (PP)** splits Transformer layers into stages, one per GPU.

```
Stage 0 (Layer 0-7) → Stage 1 (Layer 8-15) → Stage 2 (Layer 16-23) → Stage 3 (Layer 24-31)
        ↓ activation          ↓ activation           ↓ activation
      send/recv             send/recv              send/recv
```

Activations are passed between stages via NCCL P2P (`send`/`recv`). As shown in the diagram, multiple micro-batches fill the pipeline to reduce **pipeline bubble** time — the idle periods where a stage waits for its predecessor.

PP is typically used in **multi-node environments** alongside TP. A common pattern is `TP=8, PP=2` on 2 nodes × 8 GPUs each.

```python
vllm serve meta-llama/Llama-3-70B \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 2
```

### Expert Parallelism

**Expert Parallelism (EP)** distributes MoE experts across GPUs.

```
token → Top-K router → all_to_all → assigned GPU runs expert → all_to_all return
```

MoE models such as DeepSeek-V2 and Mixtral can have tens to hundreds of experts, making single-GPU deployment infeasible. EP assigns a subset of experts to each GPU. Token routing uses `all_to_all` to dispatch tokens to the GPU holding their selected expert.

```python
vllm serve deepseek-ai/DeepSeek-V2 \
  --tensor-parallel-size 4 \
  --expert-parallel-size 8
```

### Sequence Parallelism

**Sequence Parallelism (SP)** distributes attention computation across the sequence dimension, targeting long-context inference. vLLM partially supports the Ulysses-style SP approach, where each GPU handles a portion of the sequence and `all_to_all` exchanges Q/K/V partitions across GPUs.

---

## Summary

| Component | Role |
|:---|:---|
| `AsyncLLMEngine` | Async request management, streaming output |
| `Scheduler` | FCFS + preemption, Chunked Prefill scheduling |
| `BlockSpaceManager` | PagedAttention physical block allocation/release |
| `ExecutorBase` | Worker abstraction, execution broadcast |
| `Worker` / `ModelRunner` | GPU forward pass execution |
| `CacheEngine` | KV Cache allocation and swap |
| NCCL collectives | TP all_reduce, PP send/recv, EP all_to_all |
| `KVConnector` | Disaggregated Prefill KV Cache transfer |

| Parallelism | Split unit | Collective | Recommended for |
|:---|:---|:---|:---|
| TP | Intra-layer (head/weight) | all_reduce | Single node, NVLink |
| PP | Inter-layer (stage) | send/recv | Multi-node |
| EP | Expert | all_to_all | MoE models |
| SP | Sequence | all_to_all | Long context |

---

The next post covers SGLang internals — how RadixAttention is implemented and how CUDA Graph optimization is applied.

---

*한국어 버전은 상단 언어 스위처를 통해 확인할 수 있습니다.*
