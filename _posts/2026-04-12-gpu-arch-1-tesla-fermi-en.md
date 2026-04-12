---
layout: post
title: "GPU Architecture Series #1: The Origin of GPU and the Birth of SIMT"
subtitle: "Tesla, Fermi Architecture and the Beginning of CUDA"
tags: [GPU, Architecture, CUDA, NVIDIA, SIMT, Computer-Architecture]
lang: en
translation-url: /2026-04-12-gpu-arch-1-tesla-fermi-kr/
readtime: true
mathjax: true
---

## Series Overview

This series covers the history and internal workings of GPU architecture.

| # | Topic |
|:--:|:---|
| **#1** | **The Origin of GPU and the Birth of SIMT — Tesla, Fermi** |
| #2 | The Evolution of GPU Architecture — Kepler to Blackwell |
| #3 | GPU Memory Systems and Optimization |
| #4 | Dissecting GPU Architecture — Instruction/Memory/Compute Pipelines |
| #5 | CUDA Kernel Optimization |

---

## 1. Where Did GPUs Come From?

GPUs were originally designed to **draw pixels on a screen as fast as possible**. The 3D gaming boom of the 1990s created enormous demand for geometry processing and per-pixel shading — workloads that CPUs alone could not handle efficiently.

Early GPUs used a **Fixed-Function Pipeline**. Each stage — T&L (Transform & Lighting), rasterization, texture mapping — was hardwired into silicon. Developers could only tune parameters, not change the logic.

The inflection point was **Programmable Shaders**. Vertex shaders, introduced in NVIDIA GeForce 3 (2001), opened part of the GPU pipeline to developer programming. By the DirectX 9 era (2002), both vertex and pixel shaders were mainstream, enabling developers to implement lighting models, shadows, and refractions through shader code.

Some researchers noticed something important: **shaders were essentially small programs that performed floating-point operations in parallel** — and this could be repurposed for scientific computing beyond graphics. The era of GPGPU (General-Purpose Computing on GPU) was about to begin.

---

## 2. Tesla Architecture — The First Step Toward GPGPU

### The Unified Shader Architecture

Through DirectX 9, vertex and pixel shaders ran on **separate, fixed hardware units**. The problem was that the ratio of vertex-to-pixel workload varies by scene complexity, yet the hardware ratio was fixed — leaving one unit idle while the other bottlenecked.

NVIDIA solved this with the **Unified Shader Architecture** introduced in the G80 (GeForce 8800, 2006). A pool of general-purpose processors handles both vertex and pixel workloads, dynamically balanced based on demand. This design is the cornerstone of the Tesla microarchitecture.

### G80 Structure

G80 shipped with 128 Scalar Processors.

```
G80 Structure (simplified)
├── TPC (Texture Processor Cluster) × 8
│   └── SM (Streaming Multiprocessor) × 2
│       ├── SP (Scalar Processor) × 8
│       ├── SFU (Special Function Unit) × 2
│       └── Shared Memory / L1 Cache
└── ROP (Raster Operation Processor)
```

SMs sit beneath the graphics-facing TPC layer, and SPs inside each SM perform the actual arithmetic.

### The Birth of CUDA

Alongside G80, NVIDIA announced **CUDA (Compute Unified Device Architecture)** in 2006. CUDA carries two meanings:

1. **Hardware**: An architecture designed to expose the GPU for general computation — direct memory addressing, synchronization primitives, and eventually ECC support.
2. **Software**: A C-based parallel programming platform for GPUs.

Before CUDA, GPGPU required abusing shader languages (GLSL, HLSL) as a workaround — extremely low productivity. CUDA opened the door to programming GPUs directly in C, which brought the scientific computing community in force.

---

## 3. SIMT — Single Instruction, Multiple Threads

The key execution model introduced with Tesla is **SIMT**.

### How It Differs from SIMD

SIMT is often confused with CPU SIMD (Single Instruction, Multiple Data), but the two are fundamentally different:

| | SIMD | SIMT |
|:---|:---|:---|
| Abstraction unit | Vector lane | Independent thread |
| Register file | Shared vector register | Per-thread private registers |
| Branch handling | Explicit mask (programmer-managed) | Hardware-managed automatically |
| Programming model | Must express vector operations | Write scalar code |

The key insight of SIMT: **the programmer writes scalar code, and the hardware bundles threads together for parallel execution**.

### Warp — The Unit of Execution

In SIMT, the hardware unit of parallel execution is the **Warp** — a group of **32 threads** that execute the same instruction at the same cycle.

```
Thread hierarchy
Thread  → Smallest execution unit; has its own registers and PC
Warp    → 32 threads; the hardware scheduling unit
Block   → N warps; shares Shared Memory; can synchronize with __syncthreads()
Grid    → M blocks; one full kernel launch
```

An SM holds multiple warps in-flight simultaneously. When a warp stalls (e.g., waiting for a memory access), the scheduler immediately switches to another warp that is ready to execute. This is **Warp Latency Hiding** — the primary mechanism by which GPUs tolerate memory latency.

### Branch Divergence

All 32 threads in a warp must execute the same instruction. What happens when threads take different branches?

```c
// Example: different paths based on even/odd threadIdx.x
if (threadIdx.x % 2 == 0) {
    doA();  // even threads
} else {
    doB();  // odd threads
}
```

The hardware handles this via an **Active Mask**, executing both paths serially with different thread subsets active:

```
Cycles 1~N:  [T0 T2 T4 ... T30] active → execute doA()
Cycles N~M:  [T1 T3 T5 ... T31] active → execute doB()
```

Since both paths execute sequentially, throughput can be cut in half. This is **Warp Divergence** — a critical consideration in GPU kernel optimization.

---

## 4. SM — Streaming Multiprocessor

The SM is the fundamental compute building block of a GPU. The Tesla (G80) SM:

```
Tesla SM (G80)
├── 8× SP (Scalar Processor, INT/FP32 ALU)
├── 2× SFU (Special Function Unit: sin, cos, sqrt, rcp, etc.)
├── Instruction Cache
├── Warp Scheduler (1)
├── Register File (8,192 × 32-bit)
└── Shared Memory (16 KB)
```

**Register File**: All thread contexts are kept live in the register file. Warp switching requires no save/restore — this zero-overhead context switching is what makes GPU warp scheduling practical.

**Shared Memory**: An on-chip memory space shared among threads in the same block. As fast as L1 cache but explicitly managed by the programmer. Used for inter-thread communication and to reduce redundant global memory accesses.

---

## 5. Fermi Architecture — GPU Computing Comes of Age

If Tesla opened the door to GPGPU, **Fermi (GF100, 2010)** completed the transformation of GPU into a first-class computing platform.

### Key Changes

```
Fermi SM
├── 32× CUDA Core (FP32/INT32 ALU) — 4× Tesla
├── 4× SFU
├── 16× Load/Store Unit
├── 2× Warp Scheduler (dual-issue capable)
├── Register File (32,768 × 32-bit)
└── L1 Cache / Shared Memory (64 KB, configurable ratio)
```

**Dual Warp Scheduler**: Two warp schedulers per SM allow up to two warps to be issued per cycle. This doesn't simply double throughput — it allows instructions from different warps to fill execution units without overlap, improving IPC.

**L1/L2 Cache Hierarchy**: Tesla had essentially no caches. Fermi introduced per-SM L1 (16–48 KB) and a shared L2 (768 KB), significantly reducing the performance impact of irregular memory access patterns.

**ECC Support**: Error-Correcting Code memory support — essential for scientific computing where bit errors are unacceptable.

**Full IEEE 754-2008 Compliance**: Tesla's double-precision (FP64) support was incomplete. Fermi achieved full IEEE standard compliance, unlocking the HPC market.

### Fermi's Full Structure

```
Fermi (GF100)
├── GPC (Graphics Processing Cluster) × 4
│   └── SM × 4
│       └── CUDA Core × 32
├── L2 Cache (768 KB, shared)
├── Memory Controller × 6 (GDDR5, 384-bit bus total)
└── Total CUDA Cores: 512
```

Fermi shipped with CUDA 2.0, adding C++ features, recursion, and function pointers to GPU programming — capabilities that were heavily restricted or absent in Tesla.

---

## Summary

| | Tesla (G80, 2006) | Fermi (GF100, 2010) |
|:---|:---:|:---:|
| CUDA Cores / SM | 8 | 32 |
| Warp Schedulers / SM | 1 | 2 |
| L1 Cache | None | 16–48 KB |
| L2 Cache | None | 768 KB |
| FP64 | Partial | Full IEEE 754 |
| ECC | No | Yes |
| Shared Memory | 16 KB | 16 or 48 KB |

Tesla introduced SIMT and CUDA to the world. Fermi built the infrastructure to run real HPC workloads on top of that foundation.

The next post traces GPU architecture from Kepler through Blackwell — examining what problems each generation set out to solve and how.

---

*This post is also available in Korean via the language switcher above.*
