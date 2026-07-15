---
layout: post
title: "AMD GPU Architecture #5: CDNA 1"
subtitle: "Inheriting GCN's compute lineage, the arrival of Matrix Core, and a head-to-head with NVIDIA A100"
tags: [GPU, Architecture, AMD, CDNA, ROCm, HPC, Computer-Architecture]
lang: en
translation-url: /2026-07-15-amd-gpu-arch-5-cdna1-kr/
readtime: true
mathjax: true
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| Overview | [RDNA / CDNA Full Timeline](/2026-07-09-amd-gpu-arch-overview-en/) | ✅ |
| 1 | [RDNA 1 — Wave32, WGP, 7nm](/2026-07-09-amd-gpu-arch-1-rdna1-en/) | ✅ |
| 2 | [RDNA 2 — Ray Accelerator, Infinity Cache](/2026-07-13-amd-gpu-arch-2-rdna2-en/) | ✅ |
| 3 | [RDNA 3 — Chiplet, Dual-Issue](/2026-07-13-amd-gpu-arch-3-rdna3-en/) | ✅ |
| 4 | [RDNA 4 — Monolithic return, FSR 4](/2026-07-13-amd-gpu-arch-4-rdna4-en/) | ✅ |
| 5 | CDNA 1 — GCN inheritance, Matrix Core, A100 comparison | ✅ |
| 6 | CDNA 2 — MCM, FP64 Matrix, Frontier | 🔲 |

---

## Why a Separate Compute Architecture

In 2019 AMD split its GPU architecture in two. RDNA went to consumer graphics; CDNA went to datacenter compute.

A recurring theme across the RDNA series: RDNA broke away from GCN and moved to the Wave32 execution model. CDNA is the opposite. **CDNA inherits GCN's compute foundation directly.**

![Branching from GCN into RDNA / CDNA](/assets/img/posts/amd-gpu-arch-5-cdna1/gcn-fork.png)

The logic of this split comes from workload characteristics.

- **Graphics (RDNA)**: frequent divergence, latency-sensitive. Narrowing to Wave32 reduces divergence loss and enables higher clocks.
- **Compute (CDNA)**: dominated by large matrix operations and regular data parallelism. Wave64's wide execution width favors throughput.

CDNA kept for compute the Wave64 that RDNA discarded for graphics. The two architectures specialized in opposite directions from the same GCN root.

**CDNA 1 (Arcturus, MI100, November 2020)** is the first datacenter-only architecture after this split.

---

## Removing the Graphics Pipeline

CDNA 1's first decision is the complete removal of graphics hardware.

```
Blocks removed from GCN (Vega) → CDNA 1 (Arcturus):
┌────────────────────────────────────────────┐
│  ❌ ROP (Render Output Unit)               │
│  ❌ Rasterizer                             │
│  ❌ Geometry / tessellation engines        │
│  ❌ Display engine (no output ports)       │
│  ❌ Multimedia encode/decode (partial)     │
│                                            │
│  ✅ Retained: Compute Units (CU) + memory  │
│  ✅ Added: Matrix Core                     │
└────────────────────────────────────────────┘
```

The MI100 has no display output ports — it does not draw a screen. It has no rasterizer or ROP — it does not turn triangles into pixels.

The payoff of this removal is die-area reallocation. Space once occupied by fixed-function graphics blocks goes to compute units and Matrix Cores. The MI100 packs 120 CUs — three times a same-7nm-generation consumer GPU (RDNA 1 Navi 10 at 40 CUs).

---

## CU Structure: Inheriting the GCN Lineage

CDNA 1's compute unit retains GCN's structure. The contrast with RDNA is clear.

```
RDNA CU (Wave32):              CDNA 1 CU (Wave64, GCN inheritance):
┌──────────────────────┐      ┌──────────────────────────────┐
│  SIMD32 × 2          │      │  SIMD16 × 4                  │
│  Wave32 (32 threads) │      │  Wave64 (64 threads)         │
│  1-clock completion  │      │  4-clock completion (16 × 4) │
│                      │      │  ┌────────────────────────┐  │
│  (no Matrix)         │      │  │  Matrix Core (MFMA)   │  │
│                      │      │  │  FP32/FP16/BF16/INT8  │  │
│  LDS 128KB (WGP)     │      │  └────────────────────────┘  │
└──────────────────────┘      │  LDS 64KB                    │
                              └──────────────────────────────┘
```

The CDNA 1 CU is built, like GCN, from **four SIMD16 units** and uses **Wave64 (64 threads)** as its base execution unit — in contrast to RDNA's shift to two SIMD32 units and Wave32.

| Item | GCN (Vega) | RDNA | CDNA 1 |
|:---|:---:|:---:|:---:|
| SIMD config | SIMD16 × 4 | SIMD32 × 2 | SIMD16 × 4 |
| Wave size | Wave64 | Wave32 | Wave64 |
| Wave completion clocks | 4 | 1 | 4 |
| Target workload | Mixed | Graphics | Compute |

Compute workloads repeat large array operations regularly. With little divergence, Wave64's wide width is not wasted — instead, spreading instruction fetch and scheduling overhead across more threads per wave raises efficiency.

---

## Matrix Core: AMD's First Matrix Acceleration

CDNA 1's key addition is the **Matrix Core** — AMD's dedicated matrix-operation unit, its counterpart to NVIDIA's Tensor Core.

Matrix Core operates through **MFMA (Matrix Fused Multiply-Add)** instructions. It computes $D = A \times B + C$ — multiplying matrices A and B and accumulating into C — in a single instruction. Deep learning's GEMM (general matrix multiply) and HPC's dense linear algebra follow this pattern.

```
The operation MFMA accelerates (single instruction):
    D[M×N] = A[M×K] × B[K×N] + C[M×N]

Supported precisions (CDNA 1):
  FP32 matrix : 46.1 TFLOPS  (2× the 23.1 FP32 vector)
  FP16 matrix : 184.6 TFLOPS
  BF16 matrix : 92.3 TFLOPS
  INT8 matrix : 184.6 TOPS
```

CDNA 1's Matrix Core accelerates FP32, FP16, BF16, INT8, and INT4 matrix operations. Notably, there is **no FP64 matrix operation** — FP64 is handled only by the vector pipeline (11.5 TFLOPS). An FP64 Matrix Core arrives in the next generation, CDNA 2.

Matrix Core is closer to a matrix instruction path integrated with the CU's SIMD units than a separate large fixed block. Its implementation differs from NVIDIA's Tensor Core, but the goal is identical: sharply raise matrix-multiply throughput over vector operations.

---

## Memory and Interconnect

**HBM2 Memory**

The MI100 connects four HBM2 stacks, 32 GB total, over a 4096-bit interface at 1.23 TB/s. Unlike consumer GPUs on GDDR6 256–384-bit, compute GPUs secure bandwidth with a wide HBM interface.

**Infinity Fabric (2nd gen)**

The MI100 provides three **Infinity Fabric** links for direct GPU-to-GPU connection, binding up to four GPUs into a fully-connected hive.

```
4-GPU hive (fully-connected):
    GPU0 ─── GPU1
     │  ╲   ╱  │
     │   ╳     │      each GPU directly connects to the other three
     │  ╱   ╲  │      IF links give higher peer bandwidth than PCIe
    GPU2 ─── GPU3

Host interface: PCIe 4.0 x16
```

This configuration eases PCIe bottlenecks in HPC/training workloads with frequent inter-GPU data exchange, handling GPU-to-GPU communication directly without routing through host memory.

**MI100 Specs:**

| Item | Value |
|:---|:---|
| Codename | Arcturus |
| Process | TSMC 7nm FinFET |
| CUs | 120 |
| Stream processors | 7,680 |
| Boost clock | 1,502 MHz |
| FP64 vector | 11.5 TFLOPS |
| FP32 vector | 23.1 TFLOPS |
| FP32 Matrix | 46.1 TFLOPS |
| FP16 Matrix | 184.6 TFLOPS |
| BF16 Matrix | 92.3 TFLOPS |
| Memory | HBM2 32 GB, 4096-bit |
| Memory bandwidth | 1.23 TB/s |
| TDP | 300 W |
| Interface | PCIe 4.0 x16 + 3 IF links |

---

## Comparison with NVIDIA A100

CDNA 1's competitor is NVIDIA's **A100 (Ampere, GA100)**, launched in 2020 — the de facto standard of the datacenter compute market.

### Specification Comparison

![MI100 (CDNA 1) vs A100 40GB (Ampere)](/assets/img/posts/amd-gpu-arch-5-cdna1/spec-compare.png)

| | MI100 (CDNA 1) | A100 40GB (Ampere) |
|:---|:---:|:---:|
| Process | TSMC 7nm | TSMC 7nm |
| FP64 vector | 11.5 TFLOPS | 9.7 TFLOPS |
| FP64 Matrix/Tensor | None | 19.5 TFLOPS |
| FP32 vector | 23.1 TFLOPS | 19.5 TFLOPS |
| FP16 Matrix/Tensor | 184.6 TFLOPS | 312 TFLOPS |
| TF32 | Not supported | Supported (156 TFLOPS) |
| Sparsity acceleration | None | 2× (structured sparsity) |
| Memory | HBM2 32 GB | HBM2e 40 GB |
| Memory bandwidth | 1.23 TB/s | 1.55 TB/s |
| TDP | 300 W | 400 W (SXM) |

### Domain Breakdown

**Traditional HPC (FP64/FP32 vector)**

The MI100 leads. Its 11.5 TFLOPS FP64 vector exceeds the A100's 9.7 TFLOPS by ~19%, and its FP32 vector also wins. For scientific computing centered on double-precision dense linear algebra, the MI100 was competitive.

**AI/Deep Learning (matrix/tensor)**

The A100 leads. Its 312 TFLOPS FP16 tensor far exceeds the MI100's 184.6 TFLOPS Matrix, and it extends up to 2× (624 TFLOPS) with **structured sparsity**. It also supports **TF32**, a training-friendly format the MI100 lacks, and adds an FP64 Tensor Core the MI100 does not have.

**Software Ecosystem**

The biggest gap was not hardware. NVIDIA **CUDA** holds an ecosystem accumulated since 2007. Libraries like cuBLAS, cuDNN, and NCCL — and every major ML framework — are optimized for CUDA.

AMD **ROCm** was immature during the CDNA 1 era. It offered portability via HIP (a CUDA-like API), but fell short of CUDA in library coverage and stability. Despite the MI100's hardware competitiveness, this was the key factor constraining real-world adoption.

---

## Software: ROCm and HIP

CDNA 1 is programmed through the **ROCm (Radeon Open Compute)** stack.

- **HIP (Heterogeneous-computing Interface for Portability)**: a CUDA-like C++ API. The `hipify` tool converts CUDA code to HIP, which compiles for both AMD and NVIDIA GPUs.
- **rocBLAS, MIOpen**: linear-algebra and deep-learning libraries answering cuBLAS and cuDNN.
- **RCCL**: a multi-GPU collective communication library answering NCCL.

ROCm in the CDNA 1 era was functionally in place but far behind CUDA in ecosystem maturity. That gap narrowed gradually across later generations (CDNA 2's Frontier, CDNA 3's MI300) alongside large supercomputer deployments.

---

## Summary

| Item | Detail |
|:---|:---|
| Lineage | Inherits GCN compute base (opposite of RDNA) |
| Execution model | Wave64 / SIMD16 × 4 (GCN retained) |
| Graphics | Pipeline fully removed (no ROP/raster/display) |
| Key addition | Matrix Core (MFMA) — AMD's first matrix acceleration |
| FP64 | Vector only (Matrix arrives in CDNA 2) |
| Memory | HBM2 32 GB, 1.23 TB/s |
| Interconnect | Infinity Fabric 3 links, 4-GPU hive |

| | MI100 (CDNA 1) | A100 (Ampere) |
|:---|:---:|:---:|
| FP64 vector | 11.5 TFLOPS (ahead) | 9.7 TFLOPS |
| FP32 vector | 23.1 TFLOPS (ahead) | 19.5 TFLOPS |
| FP16 Matrix/Tensor | 184.6 TFLOPS | 312 TFLOPS (ahead) |
| AI features | Baseline | TF32, Sparsity (ahead) |
| Software | ROCm (immature) | CUDA (mature, ahead) |

CDNA 1 was AMD's starting point for re-entering datacenter compute. It inherited GCN's Wave64 compute foundation and removed graphics hardware to focus the die on compute. Matrix Core took the first step into matrix acceleration. It beat the A100 on FP64/FP32 vector but trailed on AI tensor performance and software ecosystem. Closing that gap becomes the mission of the generations that follow.

Next: CDNA 2 — MCM 2-die, FP64 Matrix Core, and the world's first exascale system, Frontier (upcoming)
