---
layout: post
title: "AMD GPU Architecture #6: CDNA 2"
subtitle: "AMD's first GPU MCM, the FP64 Matrix Core, and the world's first exascale system, Frontier"
tags: [GPU, Architecture, AMD, CDNA, ROCm, HPC, Computer-Architecture]
lang: en
translation-url: /2026-07-15-amd-gpu-arch-6-cdna2-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| Overview | [RDNA / CDNA Full Timeline](/2026-07-09-amd-gpu-arch-overview-en/) | ✅ |
| 4 | [RDNA 4 — Monolithic return, FSR 4](/2026-07-13-amd-gpu-arch-4-rdna4-en/) | ✅ |
| 5 | [CDNA 1 — GCN inheritance, Matrix Core, A100 comparison](/2026-07-15-amd-gpu-arch-5-cdna1-en/) | ✅ |
| 6 | CDNA 2 — MCM 2-die, FP64 Matrix, Frontier | ✅ |
| 7 | [CDNA 3 — 3D stacking, unified GPU, MI300A APU, El Capitan](/2026-07-16-amd-gpu-arch-7-cdna3-en/) | ✅ |

---

## The Two Problems CDNA 1 Left Behind

CDNA 1 (MI100) inherited GCN's compute foundation and began matrix acceleration with Matrix Core. It beat the A100 on FP64/FP32 vector. But it had two weaknesses.

- **No FP64 matrix operation**: Matrix Core accelerated only FP16/BF16/FP32. FP64 ran on the vector pipeline alone, with no answer to the A100's FP64 Tensor Core for scientific computing centered on double-precision dense linear algebra.
- **The limit of a single die**: MI100 was a 120-CU monolith. More performance meant a bigger die, and large dies suffer collapsing yields.

**CDNA 2 (Aldebaran, MI250/MI250X, November 2021)** attacked both head-on: surpass the die limit with MCM, and complete HPC performance with an FP64 Matrix Core.

---

## MCM: AMD's First Multi-Die GPU

CDNA 2's headline is **MCM (Multi-Chip Module)** — AMD's first integration of two GPU dies in a single package.

![MI250X MCM Structure](/assets/img/posts/amd-gpu-arch-6-cdna2/mcm-structure.png)

The MI250X places **two GCDs (Graphics Compute Dies)** on an OAM package. Each GCD has its own compute units and HBM2e memory.

- **Per GCD**: 110 CUs, 7,040 SP, 64 GB HBM2e
- **MI250X total**: 220 CUs, 14,080 SP, 128 GB HBM2e, 3.2 TB/s
- **Die-to-die link**: Infinity Fabric, 400 GB/s bidirectional (200 GB/s each direction)

### It Is Not a Unified GPU: The Key Nuance

The MI250X's two GCDs do not merge into one logical GPU. **They appear as two separate GPUs to the OS and the programmer.**

```
How software sees a single MI250X:
┌──────────────────────────────────────────┐
│  MI250X (physically one card)              │
│                                          │
│  GPU 0 (GCD 0)  ←→  GPU 1 (GCD 1)       │
│  64 GB          IF   64 GB              │
│  separate addr space  separate addr space  │
│                                          │
│  → programs see 2 GPUs and must          │
│    explicitly partition data             │
└──────────────────────────────────────────┘
```

A single Frontier node holds four MI250X cards. Software sees them as **eight GPUs (eight GCDs)**. For one GCD to access another's memory, it traverses Infinity Fabric, creating NUMA-like (non-uniform memory access) characteristics.

This design was a pragmatic way around the die-size limit, but it left the programmer to handle two dies explicitly. Merging the two dies into one logical GPU becomes the mission of the next generation, CDNA 3 (MI300).

---

## FP64 Matrix Core: Completing HPC Performance

CDNA 2's second key feature is the addition of the **FP64 Matrix Core**.

CDNA 1's Matrix Core did not support FP64 matrix operations. CDNA 2 added them and simultaneously raised FP64 vector operations to full rate.

```
FP64 performance evolution (per card):
  MI100 (CDNA 1)  : FP64 vector 11.5 TFLOPS,  no FP64 Matrix
  MI250X (CDNA 2) : FP64 vector 47.9 TFLOPS,  FP64 Matrix 95.7 TFLOPS
                    ↑ vector ~4× (2 dies + full-rate FP64 per die)
                    ↑ Matrix new (2× the vector rate)
```

FP64 jumping ~4× over MI100 is the product of two factors: the die count doubled (2×), and per-die FP64 throughput doubled to full rate (2×). On top of that, the FP64 Matrix Core adds 2× the vector rate (95.7 TFLOPS).

This double-precision performance made CDNA 2 a force in HPC. Scientific computing's dense linear algebra is dominated by FP64 matrix multiply. Against the A100's FP64 Tensor Core (19.5 TFLOPS), the MI250X's FP64 Matrix (95.7 TFLOPS) leads by roughly 5×.

---

## Memory and Interconnect

**HBM2e Memory**

The MI250X connects four HBM2e stacks per GCD — eight stacks, 128 GB total — over an 8192-bit interface at 3.2 TB/s, about 2.6× the CDNA 1 figure (1.23 TB/s).

**3rd-Gen Infinity Fabric: Extending to the CPU**

CDNA 2's Infinity Fabric extended beyond GPU-to-GPU links to a **coherent CPU-GPU connection**.

```
Frontier node configuration:
┌────────────────────────────────────────────────┐
│  EPYC CPU (64-core, 3rd Gen)                     │
│     │  Coherent Infinity Fabric (36+36 GB/s/GCD) │
│     ├── MI250X #1 (GCD 0, GCD 1)                │
│     ├── MI250X #2 (GCD 2, GCD 3)                │
│     ├── MI250X #3 (GCD 4, GCD 5)                │
│     └── MI250X #4 (GCD 6, GCD 7)                │
│  → 8 GCDs per node, unified CPU-GPU memory space │
└────────────────────────────────────────────────┘
```

CPU and GPU connect coherently over Infinity Fabric. Without going through PCIe, they share memory while maintaining cache coherence — easing bottlenecks in HPC workloads with frequent CPU-GPU data movement. AMD realized with Infinity Fabric, during the CDNA 2 era, a direction similar to what NVIDIA later built with NVLink-C2C in Grace-Hopper.

**MI250X Specs:**

| Item | Value |
|:---|:---|
| Codename | Aldebaran |
| Process | TSMC 6nm (N6) |
| Die config | 2 GCD (MCM) |
| CUs | 220 (110 per GCD) |
| Stream processors | 14,080 |
| Boost clock | 1,700 MHz |
| FP64 vector | 47.9 TFLOPS |
| FP64 Matrix | 95.7 TFLOPS |
| FP32 vector | 47.9 TFLOPS |
| FP16/BF16 Matrix | 383 TFLOPS |
| Memory | HBM2e 128 GB, 8192-bit |
| Memory bandwidth | 3.2 TB/s |
| TDP | 500 W (560 W peak) |

---

## Frontier: The World's First Exascale System

CDNA 2's significance goes beyond benchmark numbers. The MI250X is the compute engine of **Frontier**.

Frontier, at Oak Ridge National Laboratory (ORNL), took the Top500 #1 spot in June 2022 as the world's first system to break **exascale (over 1 EFlop/s)**.

- **Node config**: 1 EPYC CPU + 4 MI250X (8 GCDs)
- **Scale**: over 9,000 nodes
- **Performance**: over 1.1 EFlop/s on the HPL benchmark
- **Efficiency**: also ranked high on the Green500 (power efficiency)

Frontier proved AMD had secured a top-tier system in datacenter compute. The same MI250X powers Europe's **LUMI** supercomputer. It was a turning point showing AMD as a real alternative in the top-tier HPC market NVIDIA had dominated.

---

## Comparison with NVIDIA A100

At the MI250X launch (November 2021), the competitor was NVIDIA's **A100 (Ampere)**. The H100 (Hopper) arrived the following year.

### Specification Comparison

![MI250X (CDNA 2) vs A100 80GB (Ampere)](/assets/img/posts/amd-gpu-arch-6-cdna2/spec-compare.png)

| | MI250X (CDNA 2) | A100 80GB (Ampere) |
|:---|:---:|:---:|
| Process | TSMC 6nm | TSMC 7nm |
| Die config | 2 GCD (MCM) | Monolithic |
| FP64 vector | 47.9 TFLOPS | 9.7 TFLOPS |
| FP64 Matrix/Tensor | 95.7 TFLOPS | 19.5 TFLOPS |
| FP16 Matrix/Tensor | 383 TFLOPS | 312 TFLOPS |
| Sparsity acceleration | None | 2× (624 TFLOPS) |
| TF32 | Not supported | Supported |
| Memory | HBM2e 128 GB | HBM2e 80 GB |
| Memory bandwidth | 3.2 TB/s | 2.0 TB/s |
| Programming model | 2 GPUs (split) | 1 GPU (unified) |
| TDP | 500 W | 400 W |

### Domain Breakdown

**HPC (FP64)**

The MI250X dominates. Its 95.7 TFLOPS FP64 Matrix is nearly 5× the A100's. It also leads on memory capacity (128 vs. 80 GB) and bandwidth (3.2 vs. 2.0 TB/s). Frontier's exascale achievement is the proof of this advantage.

**AI/Deep Learning**

A mixed picture. The MI250X (383) beats the A100 (312) on dense FP16. But the A100 extends to 624 TFLOPS with **structured sparsity** and supports the **TF32** training format. In effective AI performance, the A100 often held the edge.

**Programming Model**

The A100 has the advantage. As a single logical GPU, it is simpler to program. The MI250X requires handling two GCDs explicitly, with the programmer managing die-to-die data movement — complexity that raised the burden of software porting and optimization.

**Software**

CUDA's ecosystem still led. However, Frontier's deployment began validating ROCm on a large production system, and HPC library support improved.

---

## Summary

| Item | Change vs. CDNA 1 |
|:---|:---|
| Die config | Monolithic → MCM 2-die (AMD's first GPU MCM) |
| Process | 7nm → 6nm (N6) |
| FP64 Matrix | None → 95.7 TFLOPS (new) |
| FP64 vector | 11.5 → 47.9 TFLOPS (~4×) |
| Memory | HBM2 32 GB → HBM2e 128 GB |
| Memory bandwidth | 1.23 → 3.2 TB/s |
| Infinity Fabric | GPU-to-GPU → coherent CPU-GPU |
| Supercomputer | - → Frontier (world's first exascale) |

| | MI250X (CDNA 2) | A100 (Ampere) |
|:---|:---:|:---:|
| FP64 Matrix | 95.7 TFLOPS (dominant) | 19.5 TFLOPS |
| FP16 Matrix | 383 TFLOPS (ahead) | 312 TFLOPS |
| AI effective (sparsity/TF32) | Behind | Ahead |
| Memory | 128 GB, 3.2 TB/s (ahead) | 80 GB, 2.0 TB/s |
| Programming | 2 GPUs split (complex) | 1 GPU (simple) |

CDNA 2 lifted AMD to the top of HPC. It surpassed the die limit with MCM, completed double-precision performance with the FP64 Matrix Core, and achieved the world's first exascale with Frontier. But the split-MCM design, where two GCDs appear as separate GPUs, left programming complexity behind. Merging those dies into one logical GPU — and putting the CPU in the same package — becomes the next generation's challenge.

Next: [CDNA 3 — XCD chiplets, a CPU+GPU integrated APU (MI300A), and El Capitan](/2026-07-16-amd-gpu-arch-7-cdna3-en/)
