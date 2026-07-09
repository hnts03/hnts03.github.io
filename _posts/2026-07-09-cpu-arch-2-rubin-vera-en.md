---
layout: post
title: "Vera CPU / Rubin GPU: What NVIDIA Announced at GTC 2025"
subtitle: "A summary of publicly confirmed details for NVIDIA's next-generation AI platform"
tags: [CPU, Architecture, ARM, NVIDIA, Rubin, Vera, HPC, NVLink, Computer-Architecture]
lang: en
translation-url: /2026-07-09-cpu-arch-2-rubin-vera-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| 1 | Grace — NVIDIA's First Datacenter CPU | ✅ |
| 2 | Vera / Rubin — GTC 2025 Announcement Summary | ✅ |
| 3 | (TBD) | 🔲 |

---

This post covers only what was publicly disclosed at GTC 2025 (March 2025). Items not yet confirmed are marked explicitly.

---

## What Grace-Hopper Established

The GH200 Grace-Hopper Superchip demonstrated that connecting a CPU and GPU via NVLink-C2C on a single package could eliminate the PCIe bottleneck entirely. Two things were proven:

1. **Bandwidth**: NVLink-C2C at 900 GB/s — roughly 14× PCIe 5.0 x16 (~64 GB/s)
2. **Coherency**: hardware cache coherency enabling direct pointer sharing between CPU and GPU without `cudaMemcpy`

Rubin and Vera are the next generation of this strategy.

---

## GTC 2025 Announcement

At GTC March 2025, Jensen Huang announced:

- **Rubin**: next-generation GPU architecture
- **Vera**: the CPU that pairs with Rubin
- Combined platform name: **Vera-Rubin**
- Target timeline: 2026 (Rubin / Vera), 2027 (Rubin Ultra)
- Following generation: **Feynman** (name only)

NVIDIA generation roadmap:

```
         2022-23      2024-25      2026       2027      2028+
GPU:  [─ Hopper ─][─ Blackwell ─][─ Rubin ─][R.Ultra][─ Feynman ─]
CPU:  [──────────── Grace ────────][─── Vera ────────][     ?     ]
SYS:  [───────── GH200 / NVL72 ───][── Vera-Rubin ───][     ?     ]

      ■ Shipped    ░ Announced    · Name only
```

---

## Rubin GPU: What's Confirmed

| Item | Detail |
|:---|:---|
| Tensor Core | **6th generation** |
| GPU memory | **HBM4** |
| GPU-GPU interconnect | **NVLink 6.0** |
| Expected release | 2026 |

### HBM4

HBM4 is confirmed for Rubin. The JEDEC HBM4 standard and public announcements from SK Hynix, Samsung, and Micron describe higher bandwidth and capacity targets compared to HBM3e. Rubin-specific stack count, total capacity, and total bandwidth figures are not yet disclosed.

### NVLink 6.0

NVLink 6.0 connects Rubin GPUs within a node. Bandwidth progression across generations:

| Generation | GPU | Bandwidth (per GPU) |
|:---|:---:|:---:|
| NVLink 4.0 | Hopper H100 | 900 GB/s |
| NVLink 5.0 | Blackwell B200 | 1,800 GB/s |
| NVLink 6.0 | Rubin | **Not yet disclosed** |

### 6th-Generation Tensor Core

The 6th-generation Tensor Core label is confirmed. Supported precisions, throughput improvements, and architectural changes are not yet disclosed.

### Not Yet Disclosed (Rubin GPU)

SM count, die configuration (monolithic vs. MCM), process node, HBM4 total capacity, NVLink 6.0 bandwidth, Tensor Core supported precisions and throughput.

---

## Vera CPU: What's Confirmed

The total public information about Vera at the time of this writing:

| Item | Detail |
|:---|:---|
| Role | Successor to Grace; datacenter CPU |
| Paired GPU | Rubin |
| Platform | Vera-Rubin |
| Expected release | 2026 |

### CPU-GPU Interconnect

Grace-Hopper established NVLink-C2C as NVIDIA's CPU-GPU intra-package interconnect. The same approach is expected for Vera-Rubin, but NVIDIA has not explicitly confirmed NVLink-C2C for Vera.

### Not Yet Disclosed (Vera CPU)

Core count, microarchitecture (including whether it uses a next-generation ARM Neoverse core), memory standard and bandwidth, cache configuration, process node, NVLink-C2C bandwidth.

---

## Rubin Ultra (2027)

A higher-performance variant of Rubin. Only the name and the 2027 target year are confirmed; no technical specifications have been released.

---

## Feynman

Named after Richard Feynman — the generation after Rubin. Only the name and its approximate position in the roadmap (2027–2028) are confirmed. No technical content has been released.

---

## Side-by-Side with Grace-Hopper

Placing the confirmed information next to Grace-Hopper highlights what's known and what isn't:

| Item | Grace-Hopper (GH200) | Vera-Rubin |
|:---|:---:|:---:|
| GPU architecture | Hopper | Rubin |
| CPU architecture | Grace (Neoverse V2) | Vera (not disclosed) |
| GPU memory | HBM3 / HBM3e | HBM4 |
| GPU-GPU link | NVLink 4.0 (900 GB/s) | NVLink 6.0 (BW not disclosed) |
| CPU-GPU link | NVLink-C2C (900 GB/s) | Not disclosed (NVLink-C2C expected) |
| GPU TC generation | 4th gen (FP8) | 6th gen (details not disclosed) |
| Release | 2022–2023 | 2026 (planned) |

The asymmetry is notable. On the GPU side, generation, memory type, and interconnect name are confirmed. On the CPU side (Vera), only the name and its pairing with Rubin have been publicly stated.

Further disclosures are expected at SC (Supercomputing) 2025 or GTC 2026.

Next post: TBD
