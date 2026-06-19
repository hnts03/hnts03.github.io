---
layout: post
title: "LLM Serving Frameworks Overview: vLLM, SGLang, TensorRT-LLM"
subtitle: "Design philosophies and core technologies compared"
tags: [LLM, Inference, vLLM, SGLang, TensorRT-LLM, GPU, AI]
lang: en
translation-url: /2026-06-19-llm-serving-overview-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic |
|:--:|:---|
| **0** | **Overview & Comparison — vLLM, SGLang, TensorRT-LLM** |
| 1 | Deep Dive: vLLM — PagedAttention and Scheduling |
| 2 | Deep Dive: SGLang — RadixAttention and Structured Generation |
| 3 | Deep Dive: TensorRT-LLM — Compiled Optimization and Deployment |

---

## Why Do We Need Dedicated Serving Frameworks?

LLM inference has characteristics that general-purpose deep learning frameworks are not designed to handle efficiently.

**Autoregressive generation**: Output tokens are generated one at a time. Rather than recomputing the Key-Value (KV) representations of all previous tokens at each step, they are cached and reused (KV Cache). Managing this cache is the central memory bottleneck.

**Variable request lengths**: Input prompts and output lengths differ per request. With static batching, a short request wastes GPU cycles waiting for the longest request in the batch to finish.

**Prefill-Decode asymmetry**: Processing the input prompt (Prefill) is compute-bound; generating output tokens (Decode) is memory-bound. How these two phases are scheduled determines overall throughput and latency.

PyTorch and TensorFlow do not optimize for these characteristics. This is why LLM-specific serving frameworks exist.

---

## vLLM

> UC Berkeley, 2023. The de facto standard for open-source LLM serving.

### Core Technology: PagedAttention

KV Cache memory is managed using a scheme analogous to OS virtual memory paging. Each request's KV Cache is allocated in fixed-size physical blocks that need not be contiguous, with a logical-to-physical block mapping table maintained at runtime.

Prior approaches required pre-allocating contiguous memory equal to the maximum sequence length per request, wasting 60–80% of allocated memory on average. PagedAttention allocates blocks only as needed, nearly eliminating waste and allowing far more concurrent requests per GPU.

```
Conventional KV Cache allocation
Request A: [████████████████████████______] (tail wasted)
Request B: [████████████__________________] (tail wasted)

PagedAttention
Physical blocks: [Block0][Block1][Block2][Block3][Block4]...
Request A → Block0, Block2, Block4 (non-contiguous, no waste)
Request B → Block1, Block3        (non-contiguous, no waste)
```

Copy-on-Write block sharing enables prefix reuse and parallel sampling (e.g., beam search) with minimal memory overhead.

### Continuous Batching

The batch is rebuilt at each iteration. When a forward pass completes, finished sequences are removed and waiting requests are inserted immediately. This keeps GPU utilization high regardless of output length variance.

### Key Features

- Built-in OpenAI API-compatible server
- Hardware: NVIDIA, AMD (ROCm), Google TPU, AWS Inferentia, and more
- Multi-LoRA concurrent serving
- Chunked Prefill and Speculative Decoding support
- Largest open-source contributor community

---

## SGLang

> Stanford, 2024. Optimized for complex LLM programs and prefix reuse.

### Core Technology: RadixAttention

KV Cache is organized as a Radix Tree. Requests that share a common prefix automatically reuse cached KV blocks without any manual configuration.

```
Radix Tree example
"system prompt + user A's history" → cache hit on system prompt
"system prompt + user B's history" → cache hit on system prompt
```

This is particularly effective for multi-turn conversation, few-shot prompting, and agent loops, where the same prefix appears repeatedly. While vLLM's prefix caching requires explicit configuration, SGLang handles this automatically.

### Structured Generation

High-throughput generation constrained to JSON Schema, regular expressions, or EBNF grammars. SGLang integrates XGrammar to apply constraints at the CUDA level, significantly reducing latency compared to CPU-side implementations.

### Key Features

- Aggressive CUDA Graph use for the decode phase → reduced kernel launch overhead
- FlashInfer kernel integration
- torch.compile support
- Hardware: NVIDIA, AMD (ROCm)

---

## TensorRT-LLM

> NVIDIA, 2023. Maximum raw throughput through ahead-of-time compilation.

### Core Technology: TensorRT Engine Compilation

The model is compiled into a TensorRT engine before serving. During compilation:

- **Kernel Fusion**: Multiple operations (Layer Norm → Linear → Activation) are merged into a single CUDA kernel
- **Layer/Tensor Fusion**: Computational graph is optimized
- **Quantization**: FP8, INT8 (SmoothQuant), INT4 (AWQ, GPTQ) applied at compile time

At runtime, the pre-optimized engine executes directly, yielding the highest raw throughput in NVIDIA environments.

### In-flight Batching

NVIDIA's continuous batching implementation, integrated with Triton Inference Server.

### Key Features

- Broad quantization support: FP8, INT8, INT4
- Built-in Tensor Parallelism and Pipeline Parallelism
- Official Triton Inference Server integration
- Hardware: NVIDIA GPU only
- Drawbacks: requires per-model TRT-LLM implementation, long engine build times, no AMD/other GPU support

---

## Comparison

| | vLLM | SGLang | TensorRT-LLM |
|:---|:---:|:---:|:---:|
| Origin | UC Berkeley | Stanford | NVIDIA |
| Core Technology | PagedAttention | RadixAttention | TRT engine compilation |
| Prefix Caching | Manual config | Automatic (Radix Tree) | Limited |
| Structured Generation | Basic | Specialized (XGrammar) | Limited |
| Hardware | Multi-vendor | NVIDIA, AMD | NVIDIA only |
| Deployment Complexity | Low | Low | High (build required) |
| Raw Throughput | High | High | Highest (on NVIDIA) |
| Best For | General serving | Agents, complex LLM programs | NVIDIA production deployment |

**Decision guide:**

- **General serving, multi-vendor hardware** → vLLM
- **High proportion of multi-turn chat, agents, or structured output** → SGLang
- **Maximum throughput on NVIDIA in production** → TensorRT-LLM

---

The next post covers vLLM internals — how PagedAttention is implemented and how the scheduler is designed.

---

*한국어 버전은 상단 언어 스위처를 통해 확인할 수 있습니다.*
