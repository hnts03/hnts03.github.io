---
layout: post
title: "LLM Serving Frameworks #1: Deep Dive into vLLM"
subtitle: "Multi-process architecture, Scheduler, KVCacheManager, and parallelism strategies (V1)"
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

The [overview post](/2026-06-19-llm-serving-overview-en/) introduced PagedAttention and Continuous Batching at a conceptual level. This post covers the internal structure of vLLM V1 (default since v0.8.0) — its multi-process architecture, Scheduler, KVCacheManager, and parallelism strategies.

---

## 1. What is vLLM?

**vLLM** is an open-source LLM serving framework released by UC Berkeley in 2023. It is built on the PagedAttention paper presented at SOSP 2023, with the primary goal of maximizing inference throughput in both single-GPU and distributed environments.

Three core contributions define vLLM:

- **PagedAttention**: Manages KV Cache memory using OS-style paging, eliminating memory waste
- **Continuous Batching**: Removes completed requests and inserts new ones at each iteration boundary
- **Multi-hardware support**: NVIDIA, AMD (ROCm), Google TPU, AWS Inferentia

---

## 2. Overall Architecture

![vLLM V1 Architecture](/assets/img/posts/llm-serving-1-vllm/arch-overview.png)

V1 is a **multi-process architecture**. Three process types handle distinct responsibilities:

```
HTTP Request
    ↓
[API Server]          ─── FastAPI, OpenAI-compatible
    ↓
[AsyncLLM]            ─── tokenize · detokenize · stream   (main process)
    │  ZMQ socket
    ↓
[EngineCore]          ─── scheduling · KV management loop  (separate process)
    ├── [Scheduler]           ─── request scheduling, preemption
    │       └── [KVCacheManager]  ─── block alloc · prefix cache
    └── [MultiprocExecutor]
            └── [GPUWorker × N]   ─── one process per GPU
                    └── [GPUModelRunner]  ─── model forward pass
```

The most significant change from V0 is that `EngineCore` now runs in a **separate process**. `AsyncLLM` and `EngineCore` communicate via ZMQ sockets, letting each run its own loop independently — free from Python GIL contention.

---

## 3. Frontend

### API Server

`vllm.entrypoints.openai.api_server` runs a FastAPI HTTP server. The `/v1/chat/completions` and `/v1/completions` endpoints implement the OpenAI API spec exactly, allowing existing OpenAI SDK clients to work without modification.

### AsyncLLM

`AsyncLLM` (`vllm/v1/engine/async_llm.py`) is V1's async entry point. It serves three roles:

1. Accepts concurrent requests, tokenizes them, and forwards them to `EngineCore`
2. Receives output tokens from `EngineCore` and detokenizes them
3. Streams tokens back to clients via `AsyncGenerator`

`EngineCore` runs as a separate process (`EngineCoreProc`). `AsyncLLM` sends requests and receives outputs through `EngineCoreClient` over ZMQ. Separating I/O processing from the scheduling loop means a slow tokenizer or streamer no longer stalls inference.

---

## 4. Scheduler and KVCacheManager

### Scheduler

The `Scheduler` (`vllm/v1/core/sched/scheduler.py`) manages two queues:

```
waiting  ─── requests not yet started
running  ─── requests currently executing on GPU
```

**Swap preemption has been removed in V1.** When memory pressure requires preemption, `KVCacheManager` frees the request's blocks and the request returns to the `waiting` queue for **Recompute** — prefill is re-executed when resources become available.

**Chunked Prefill is always enabled in V1.** Long prompts are split into chunks of `max_num_batched_tokens` and batched together with decode requests. This prevents a single long prefill from blocking decode iterations and allows fine-grained control over TTFT / TPOT tradeoffs.

### KVCacheManager

**KVCacheManager** (`vllm/v1/core/kv_cache_manager.py`) is the memory manager behind PagedAttention — the V1 counterpart of V0's `BlockSpaceManager`.

```
Logical Block         →  Physical Block
  [req A: block 0]   →  [GPU block #42]
  [req A: block 1]   →  [GPU block #7 ]
  [req B: block 0]   →  [GPU block #42]  ← shared prefix
```

Key operations:

- `allocate_slots()`: assign new token slots for a running request
- `free()` / `free_slots()`: return blocks when a request completes or is preempted
- **Hash-based prefix caching**: blocks are identified by a content hash; identical prefixes are reused automatically. Enabled by default in V1.

Internally, `KVCacheCoordinator` coordinates per-layer-type `SingleTypeKVCacheManager` instances, supporting heterogeneous attention (e.g., some layers use sliding-window attention, others use full attention).

---

## 5. Worker

### MultiprocExecutor

Worker coordination in V1 is handled by `MultiprocExecutor`. It spawns the required number of `GPUWorker` processes based on the TP/PP configuration and broadcasts execution commands to each.

### GPUWorker

`GPUWorker` (`vllm/v1/worker/gpu_worker.py`) corresponds to one GPU rank. During initialization it loads model weights and partitions them according to the TP/PP configuration. KV Cache tensors allocated by `EngineCore` are passed down via `bind_kv_cache()` and bound to `GPUModelRunner`.

### GPUModelRunner

`GPUModelRunner` (`vllm/v1/worker/gpu_model_runner.py`) executes the actual forward pass:

1. **Input preparation**: construct token IDs, position IDs, and attention metadata (block table, context lengths)
2. **CUDA Graph or eager execution**: for the decode phase with small, fixed batch sizes, CUDA Graph captures reduce kernel launch overhead
3. **Model forward**: pass through attention → FFN → LayerNorm per layer
4. **Sampling**: apply temperature, top-p, top-k to logits and select the next token

KV Cache tensors are allocated by `EngineCore` at startup — it profiles available GPU memory and reserves per-layer KV tensors in bulk. `GPUModelRunner` binds these tensors via `bind_kv_cache()` and accesses them directly during the forward pass. V0's `CacheEngine` (with `swap_in` / `swap_out`) has been removed in V1 and replaced by the Recompute preemption strategy.

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

Activations are passed between stages via NCCL P2P (`send`/`recv`). Multiple micro-batches fill the pipeline to reduce **pipeline bubble** time — the idle periods where a stage waits for its predecessor.

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
| `AsyncLLM` | Async request handling, tokenize · stream (main process) |
| `EngineCore` | Scheduling · KV management loop (separate process, ZMQ) |
| `Scheduler` | 2-queue (waiting/running), Recompute preemption, Chunked Prefill |
| `KVCacheManager` | Block alloc/free, hash-based prefix caching |
| `MultiprocExecutor` | GPUWorker coordination, execution broadcast |
| `GPUWorker` / `GPUModelRunner` | GPU forward pass, KV Cache binding |
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
