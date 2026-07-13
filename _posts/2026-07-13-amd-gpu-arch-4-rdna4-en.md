---
layout: post
title: "AMD GPU Architecture #4: RDNA 4"
subtitle: "Return to monolithic, 3rd-gen Ray Accelerators, FSR 4's ML shift, and a head-to-head with Blackwell"
tags: [GPU, Architecture, AMD, RDNA, Computer-Architecture]
lang: en
translation-url: /2026-07-13-amd-gpu-arch-4-rdna4-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| Overview | [RDNA / CDNA Full Timeline](/2026-07-09-amd-gpu-arch-overview-en/) | ✅ |
| 1 | [RDNA 1 — Wave32, WGP, 7nm](/2026-07-09-amd-gpu-arch-1-rdna1-en/) | ✅ |
| 2 | [RDNA 2 — Ray Accelerator, Infinity Cache, Ampere comparison](/2026-07-13-amd-gpu-arch-2-rdna2-en/) | ✅ |
| 3 | [RDNA 3 — Chiplet (GCD+MCD), Dual-Issue, Ada comparison](/2026-07-13-amd-gpu-arch-3-rdna3-en/) | ✅ |
| 4 | RDNA 4 — Return to monolithic, 3rd-gen RA, FSR 4, Blackwell comparison | ✅ |

---

## The Two Problems RDNA 3 Left Behind

RDNA 3 changed manufacturing economics with chiplets. But two weaknesses were clear.

- **Ray tracing**: The 2nd-gen Ray Accelerator fell well behind NVIDIA Ada's 3rd-gen RT Core. The gap was large in RT-enabled games.
- **AI upscaling**: FSR 3 was still non-ML. The image-quality gap versus DLSS (deep-learning based) never closed.

Chiplet power overhead was also a burden. RDNA 4 (Navi 48, March 2025) changed strategy: abandon the top flagship, and attack both weaknesses head-on in the performance tier.

---

## Return to Monolithic and a Strategic Pivot

RDNA 4 dropped chiplets and returned to a **monolithic die**.

```
RDNA die strategy by generation:
  RDNA 1 (Navi 10)  : Monolithic 7nm
  RDNA 2 (Navi 21)  : Monolithic 7nm  (Big Navi)
  RDNA 3 (Navi 31)  : Chiplet (GCD N5 + 6 MCD N6)
  RDNA 4 (Navi 48)  : Monolithic N4P  ← return
```

Navi 48 packs 53.9 billion transistors into a 357 mm² die on TSMC **N4P (4nm)**. RDNA 3's chiplet split targeted the cost of large high-end dies. Since RDNA 4 focuses on the performance tier (a midsize die), monolithic wins on power efficiency and latency rather than paying chiplet communication overhead.

This generation has no top flagship (a successor to the RX 7900 XTX class). The top product is the Navi 48-based **RX 9070 XT**.

| Item | Navi 31 (RDNA 3) | Navi 48 (RDNA 4) |
|:---|:---:|:---:|
| Die config | Chiplet (GCD + 6 MCD) | Monolithic |
| Process | GCD N5 / MCD N6 | N4P (4nm) |
| Die area | GCD 304 mm² + 6 MCD | 357 mm² (single) |
| Transistors | ~57.8B | 53.9B |
| Top product | RX 7900 XTX (96 CU) | RX 9070 XT (64 CU) |

---

## 3rd-Gen Ray Accelerator: Closing the RT Gap

RDNA 4's core improvement is ray tracing. It introduced the **3rd-gen Ray Accelerator**.

```
Ray Accelerator generations:
  RDNA 2 : 1st-gen - BVH traversal + box/triangle intersection (baseline)
  RDNA 3 : 2nd-gen - ~1.5× throughput, ray box sorting
  RDNA 4 : 3rd-gen - triangle intersection 2.5×, throughput 2×,
                     dedicated HW for instance transform + stack management
```

Improvements in the 3rd-gen Ray Accelerator:

- **Ray-triangle intersection 2.5× faster** (vs. RDNA 3)
- **BVH traversal throughput doubled**
- **Dedicated instance transform hardware**: coordinate transforms for object instancing (repeated placement of the same geometry) handled in hardware
- **Stack management acceleration**: BVH traversal stack push/pop offloaded to hardware, reducing shader load

AMD's RT, which began as a software fallback in RDNA 2, moved most of the BVH traversal bottlenecks (intersection, stack management) into fixed-function hardware by RDNA 4. The absolute gap to NVIDIA remains, but the collapse under heavy RT workloads is greatly reduced.

---

## 2nd-Gen AI Accelerator and FSR 4

RDNA 4 strengthened the AI acceleration RDNA 3 first introduced via WMMA, now a **2nd-gen AI Accelerator**.

- **Added FP8 and INT4 format support**: low-precision inference acceleration
- **Improved on-chip scheduling**
- **Up to 8× AI performance vs. the previous generation when using sparsity**

This hardware enables RDNA 4's software headline: **FSR 4**.

![FSR Evolution: from spatial to ML-based](/assets/img/posts/amd-gpu-arch-4-rdna4/fsr-evolution.png)

**FSR 4 is AMD's first machine-learning-based upscaling.** FSR 1–3 used spatial and temporal algorithms with no AI inference, which is why an image-quality gap persisted versus NVIDIA DLSS.

FSR 4 fundamentally changed this approach. It runs AMD-trained game ML models on the RDNA 4 AI Accelerator, inferring an FP8 model on-chip to raise upscaling quality toward DLSS levels.

| Item | FSR 3 and earlier | FSR 4 |
|:---|:---:|:---:|
| Method | Spatial/temporal algorithm | ML-based inference |
| AI hardware | Not required | Requires RDNA 4 AI Accelerator |
| Cross-GPU compat | Yes (incl. NVIDIA) | RDNA 4 only |
| Quality vs. DLSS | Behind | Parity as goal |

FSR 4's cost is hardware dependency. Through FSR 3, it ran on any GPU; FSR 4 requires the RDNA 4 AI accelerator — the same structure as DLSS requiring Tensor Cores. AMD traded some of its openness for image quality.

---

## Other Improvements

- **3rd-gen Infinity Cache**: 64 MB on Navi 48
- **PCIe 5.0** interface
- **DisplayPort 2.1a (UHBR13.5)**, HDMI 2.1b
- Improved performance-per-watt vs. RDNA 3 (monolithic + N4P process)

**RX 9070 XT Specs:**

| Item | Value |
|:---|:---|
| Process | TSMC N4P (4nm) |
| Die | Navi 48 monolithic, 357 mm² |
| Transistors | 53.9B |
| CUs | 64 |
| Stream processors | 4,096 |
| Ray Accelerators | 64 (3rd-gen) |
| AI Accelerators | 128 (2nd-gen) |
| Infinity Cache | 64 MB (3rd-gen) |
| VRAM | GDDR6 16 GB, 256-bit |
| Memory bandwidth | 640 GB/s |
| Game / boost clock | 2,400 / 2,970 MHz |
| FP32 | 48.7 TFLOPS |
| TBP | 304 W |
| Launch price | $599 |

The lower model **RX 9070** has 56 CUs, 3,584 SP, 36.1 TFLOPS, 220 W TBP, at $549.

---

## Comparison with NVIDIA Blackwell

RDNA 4's competitor is NVIDIA's **Blackwell (RTX 50)** generation. The RX 9070 XT's ($599) direct rival is the **RTX 5070 Ti ($749)**.

### Specification Comparison

![RX 9070 XT (RDNA 4) vs RTX 5070 Ti (Blackwell)](/assets/img/posts/amd-gpu-arch-4-rdna4/spec-compare.png)

| | RX 9070 XT (RDNA 4) | RTX 5070 Ti (Blackwell) |
|:---|:---:|:---:|
| Process | TSMC N4P | TSMC 4N |
| Die | Navi 48 (357 mm²) | GB203 (~378 mm²) |
| Shaders | 4,096 SP | 8,960 CUDA |
| FP32 | 48.7 TFLOPS | ~43.9 TFLOPS |
| Memory | GDDR6 16 GB 256-bit | GDDR7 16 GB 256-bit |
| Memory bandwidth | 640 GB/s | 896 GB/s |
| RT | 3rd-gen RA | 4th-gen RT Core |
| ML upscaling | FSR 4 | DLSS 4 |
| TBP | 304 W | 300 W |
| Launch price | $599 | $749 |

### Domain Breakdown

**Rasterization**

Averaged across 55 games, the RX 9070 XT trails the RTX 5070 Ti by ~5%, staying within 6% in many titles. At 20% lower price ($599 vs. $749), it clearly leads on value.

**Ray Tracing**

The 3rd-gen Ray Accelerator improved substantially, but a gap to Blackwell's 4th-gen RT Core remains. In heavy RT titles (e.g., F1 25), the RTX 5070 Ti leads by 20–24%. In extreme RT workloads like path tracing, the gap widens further.

**ML Upscaling**

FSR 4, AMD's first ML upscaling, greatly improved image quality over FSR 3. DLSS 4 still leads on feature breadth including multi-frame generation, but the gap in upscaling image quality itself narrowed dramatically compared to the previous generation.

**Positioning**

RDNA 4 gave up the top-performance race to focus on the value tier. Its core strategy is delivering near-RTX 5070 Ti rasterization at a 20% lower price.

---

## Software

**FSR 4 and FSR Redstone**

FSR 4 is ML upscaling on the RDNA 4 AI accelerator. It was later extended by **FSR Redstone**, expanding AI-based upscaling and frame generation.

FSR 4.1 extended to provide some upscaling on RDNA 3 as well, though full quality parity is RDNA 4-exclusive.

**ROCm**

RDNA 4 continues ROCm compute support as a consumer card. The 2nd-gen AI Accelerator's FP8 support increases usefulness for consumer ML workloads like local LLM inference. Large-scale training and HPC still center on CDNA (the MI series).

---

## Summary

| Item | Change vs. RDNA 3 |
|:---|:---|
| Die config | Chiplet → return to monolithic |
| Process | GCD N5 / MCD N6 → N4P (4nm) |
| Ray Accelerator | 2nd-gen → 3rd-gen (triangle intersection 2.5×) |
| AI Accelerator | 1st-gen (WMMA) → 2nd-gen (FP8/INT4) |
| Upscaling | FSR 3 (non-ML) → FSR 4 (ML-based) |
| Positioning | Includes flagship → performance-tier focus |
| Interface | PCIe 4.0 → PCIe 5.0 |

| | RX 9070 XT (RDNA 4) | RTX 5070 Ti (Blackwell) |
|:---|:---:|:---:|
| FP32 | 48.7 TFLOPS | ~43.9 TFLOPS |
| Memory BW | 640 GB/s | 896 GB/s |
| Raster (55-game avg) | -5% | Baseline |
| Ray tracing | 3rd-gen, behind | 4th-gen, ahead |
| ML upscaling | FSR 4 | DLSS 4 |
| Launch price | $599 | $749 |

RDNA 4 gave up the top-end race and instead attacked RDNA 3's two weaknesses directly. The 3rd-gen Ray Accelerator eased the RT collapse, and FSR 4 delivered AMD's first ML upscaling. The return to monolithic was the right choice optimized for the performance tier. It did not surpass Blackwell's top end in absolute performance, but it secured clear competitiveness in the value tier.

This concludes the consumer RDNA 1 through 4 lineage. The series continues with deep-dives into the datacenter CDNA line. (upcoming)
