---
layout: post
title: "AMD GPU Architecture #2: RDNA 2"
subtitle: "Ray Accelerator, Infinity Cache, Big Navi — head-to-head with NVIDIA Ampere"
tags: [GPU, Architecture, AMD, RDNA, Computer-Architecture]
lang: en
translation-url: /2026-07-13-amd-gpu-arch-2-rdna2-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| Overview | [RDNA / CDNA Full Timeline](/2026-07-09-amd-gpu-arch-overview-en/) | ✅ |
| 1 | [RDNA 1 — Wave32, WGP, 7nm](/2026-07-09-amd-gpu-arch-1-rdna1-en/) | ✅ |
| 2 | RDNA 2 — Ray Accelerator, Infinity Cache, Ampere comparison | ✅ |
| 3 | RDNA 3 — Chiplet (GCD+MCD), Dual-Issue shaders | 🔲 |

---

## What RDNA 1 Left Unfinished

RDNA 1 successfully exited the GCN era. Wave32, WGP, and a redesigned cache hierarchy raised clocks and efficiency to match NVIDIA Turing at rasterization. But two capabilities were absent.

- **Ray tracing**: Turing's RT Core handled BVH traversal and ray-intersection in fixed-function hardware. RDNA 1 had no RT hardware.
- **AI upscaling**: Turing's Tensor Core enabled DLSS. RDNA 1 had no response.

**RDNA 2 (Navi 21, November 2020)** addressed both.

---

## Ray Accelerator: AMD's First Hardware RT

RDNA 1 CUs handled ray tracing entirely in shader units — software fallback only. RDNA 2 added one **Ray Accelerator** per CU.

```
RDNA 2 CU layout:
┌──────────────────────────────────────────────────┐
│                       CU                        │
│  ┌──────────────────┐  ┌──────────────────┐     │
│  │    SIMD32 [0]    │  │    SIMD32 [1]    │     │
│  │    32 FP32       │  │    32 FP32       │     │
│  └──────────────────┘  └──────────────────┘     │
│  LDS 32 KB                                      │
│  ┌────────────────────────────────────────────┐ │
│  │           Ray Accelerator (×1)             │ │
│  │  BVH traversal + box test + triangle test  │ │
│  │  fixed-function hardware                   │ │
│  └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

Operations offloaded to the Ray Accelerator:
- **BVH (Bounding Volume Hierarchy) traversal**: determines which scene objects a ray might intersect
- **Ray-box intersection**: AABB vs. ray test in hardware
- **Ray-triangle intersection**: final primitive-level intersection

These operations are removed from the SIMD32 execution units entirely. While the Ray Accelerator processes traversal, shader resources are free for shading.

Navi 21 at 80 CUs carries **80 Ray Accelerators** in total.

### Comparison with Turing RT Core

| Item | Turing RT Core | RDNA 2 Ray Accelerator |
|:---|:---:|:---:|
| Generation | 1st | 1st |
| Position | 1 per SM | 1 per CU |
| BVH traversal | Fixed-function HW | Fixed-function HW |
| Ray-box test | Fixed-function HW | Fixed-function HW |
| Ray-triangle test | Fixed-function HW | Fixed-function HW |
| DXR 1.1 (Inline RT) | No | Yes |

The structures are comparable. In practice, Turing and RDNA 2 delivered similar RT performance in some titles, with RDNA 2 winning a few. Against Ampere's 2nd-gen RT Core, RDNA 2 was consistently behind.

---

## Infinity Cache: Routing Around GDDR6's Bandwidth Ceiling

Infinity Cache is RDNA 2's most distinctive design choice.

HBM delivers high bandwidth but is expensive and large. GDDR6 is cheap but bandwidth-limited. AMD chose a third path: add a large on-die L3 cache to reduce how often the external bus is accessed at all.

```
RDNA 1 memory path:
CU → L0 (WGP 128 KB) → GL1 (SA 128 KB) → L2 (4 MB) → GDDR6 256-bit 448 GB/s

RDNA 2 memory path:
CU → L0 (WGP 128 KB) → GL1 (SA 128 KB) → L2 (4 MB) → Infinity Cache (128 MB) → GDDR6 256-bit 512 GB/s
                                                               ↑
                                               cache hit: request resolved here
```

Navi 21's Infinity Cache is **128 MB of on-die SRAM**.

Bandwidth analysis:
- GDDR6 interface: 256-bit × 16 Gbps = **512 GB/s** (raw)
- Effective bandwidth at 100% hit rate: **~1,664 GB/s** (AMD stated)
- Actual effective bandwidth: determined by hit rate at the rendered resolution

```
Hit rate trend by resolution:
1080p: high hit rate   → effective BW approaches HBM2e-class
1440p: moderate        → benefit diminishes
4K:    low hit rate    → converges toward raw GDDR6 512 GB/s
```

This approach let AMD reach competitive effective bandwidth at 1080p and 1440p without HBM. The hit rate drop at 4K is the structural trade-off.

---

## Navi 21: Big Navi

RDNA 1 shipped only a midrange die (Navi 10, 40 CUs). RDNA 2 introduced **a large die (Navi 21, 80 CUs)** for the first time — the origin of the "Big Navi" nickname.

```
Navi 21 die layout:
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   SE 0   │  │   SE 1   │  │   SE 2   │  │   SE 3   │   │
│  │ SA0│ SA1 │  │ SA0│ SA1 │  │ SA0│ SA1 │  │ SA0│ SA1 │   │
│  │5WGP│5WGP │  │5WGP│5WGP │  │5WGP│5WGP │  │5WGP│5WGP │   │
│  │ (10 CUs) │  │ (10 CUs) │  │ (10 CUs) │  │ (10 CUs) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                  4 SEs × 20 CUs = 80 CUs total               │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  L2 cache 4 MB  |  Infinity Cache 128 MB (SRAM)    │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  [GDDR6 MC × 8, 256-bit]    [Display Engine]               │
└──────────────────────────────────────────────────────────────┘
```

| Item | Navi 10 (RDNA 1) | Navi 21 (RDNA 2) |
|:---|:---:|:---:|
| Process | TSMC 7nm | TSMC 7nm |
| Die area | 251 mm² | ~520 mm² |
| Transistors | 10.3B | 26.8B |
| CUs (full die) | 40 | 80 |
| Infinity Cache | None | 128 MB |
| Ray Accelerators | None | 80 |

**RX 6900 XT (full Navi 21 die):**

| Item | Value |
|:---|:---|
| CUs | 80 |
| Shader processors | 5,120 |
| Boost clock | ~2,250 MHz |
| FP32 performance | 23.04 TFLOPS |
| VRAM | GDDR6 16 GB |
| Memory bandwidth | 512 GB/s (raw) |
| TDP | 300 W |
| Launch price | $999 |

The 2,250 MHz boost is ~18% higher than the RX 5700 XT's 1,905 MHz — a result of both architectural improvements and 7nm voltage optimization.

---

## Smart Access Memory

AMD's branding for the PCIe **Resizable BAR** feature. It controls how much of the GPU's VRAM the CPU can directly address.

```
Legacy BAR (256 MB fixed):
CPU ──── PCIe ────► GPU VRAM 16 GB
         only [256 MB window] directly accessible; remainder requires remapping

SAM (Resizable BAR):
CPU ──── PCIe ────► GPU VRAM 16 GB
         entire 16 GB directly addressable
```

Requirements: RDNA 2 GPU + Ryzen 5000 or newer + BIOS-enabled motherboard. Measured gains reached ~15% in some titles. NVIDIA later enabled the same feature under the "Resizable BAR" name on RTX 30 series.

---

## DirectX 12 Ultimate — Full Support

RDNA 2 is the first AMD GPU to satisfy all four DirectX 12 Ultimate feature tiers.

| DX12U Feature | RDNA 1 | RDNA 2 |
|:---|:---:|:---:|
| DXR (Ray Tracing) | Software fallback | Hardware (Ray Accelerator) |
| Mesh Shaders | Not supported | Supported |
| Variable Rate Shading | Tier 1 | Tier 2 |
| Sampler Feedback | Not supported | Supported |

**Mesh Shaders** make the geometry pipeline fully programmable. The classic Input Assembler → Vertex Shader → Geometry Shader sequence can be replaced entirely. LOD and occlusion culling run directly on the GPU.

**VRS Tier 2** assigns shading rates per triangle rather than per tile, allowing reduced-quality shading on static or peripheral pixels without per-pixel overhead.

---

## Console Adoption: Xbox Series X and PlayStation 5

Both next-generation consoles launched the same month as RDNA 2 — November 2020.

| Console | GPU | CUs | Clock | FP32 |
|:---|:---:|:---:|:---:|:---:|
| Xbox Series X | RDNA 2 | 52 CU | 1,825 MHz | 12.0 TFLOPS |
| PlayStation 5 | RDNA 2 | 36 CU | 2,233 MHz | 10.3 TFLOPS |

Developers targeting consoles were targeting RDNA 2. Ray Accelerator, Mesh Shaders, and VRS Tier 2 became shared PC-console features, giving developers a strong incentive to adopt them. This feedback loop is a non-obvious amplifier of RDNA 2's real-world footprint.

---

## Comparison with NVIDIA Ampere

NVIDIA launched **Ampere (GA102, RTX 30)** in September 2020, one month before RDNA 2. The headline changes from Turing: doubled FP32 throughput per SM and a 2nd-gen RT Core.

```
Turing SM (TU104):                    Ampere SM (GA102):
┌──────────────────────────┐          ┌──────────────────────────┐
│  FP32 × 64               │          │  FP32 × 128              │
│  INT32 × 64 (concurrent) │          │  INT32 × 64 (concurrent) │
│  Tensor Core Gen 2 × 8   │          │  Tensor Core Gen 3 × 4   │
│  RT Core Gen 1 × 1       │          │  RT Core Gen 2 × 1       │
└──────────────────────────┘          └──────────────────────────┘
FP32 per SM: 64                       FP32 per SM: 128 (2×)
```

### Specification Comparison

![RX 6900 XT (RDNA 2) vs RTX 3080 10G (Ampere)](/assets/img/posts/amd-gpu-arch-2-rdna2/spec-compare.png)

| | RX 6900 XT (RDNA 2) | RTX 3080 10G (Ampere) | RTX 3090 (Ampere) |
|:---|:---:|:---:|:---:|
| Process | TSMC 7nm | Samsung 8nm | Samsung 8nm |
| Die | Navi 21 (~520 mm²) | GA102 (628 mm²) | GA102 (628 mm²) |
| Shaders | 5,120 SP | 8,704 CUDA | 10,496 CUDA |
| FP32 TFLOPS | 23.04 | 29.77 | 35.58 |
| Memory interface | GDDR6 256-bit | GDDR6X 320-bit | GDDR6X 384-bit |
| Raw memory BW | 512 GB/s | 760 GB/s | 936 GB/s |
| Effective BW | ~1,664 GB/s (w/ IC) | 760 GB/s | 936 GB/s |
| VRAM | 16 GB | 10 GB | 24 GB |
| RT generation | 1st | 2nd | 2nd |
| Matrix acceleration | None | Tensor Core Gen 3 | Tensor Core Gen 3 |
| TDP | 300 W | 320 W | 350 W |
| Launch price | $999 | $699 | $1,499 |

### Domain Breakdown

**Rasterization**

At 1080p and 1440p, RX 6900 XT and RTX 3080 trade blows depending on the title. Infinity Cache's effective bandwidth advantage is strongest at lower resolutions where cache hit rates are high. At 4K, raw bandwidth differences favor the RTX 3080.

**Ray Tracing**

RDNA 2's Ray Accelerator is 1st-gen; Ampere's RT Core is 2nd-gen with significantly higher BVH processing throughput. In DXR-enabled titles, RTX 3080 typically led RX 6900 XT by 30–50%. DXR 1.1 (Inline Ray Tracing) support was new on RDNA 2, but absolute RT performance remained lower.

**Upscaling**

DLSS 2.0 runs on Tensor Cores — unavailable on RDNA 2. AMD responded with **FSR 1.0 (FidelityFX Super Resolution, June 2021)**: a two-pass spatial algorithm (Easu: edge-adaptive upscaling + Rcas: contrast-adaptive sharpening). No AI hardware required — it runs on any GPU including NVIDIA, consoles, and legacy hardware. Image quality was below DLSS 2.0, but hardware independence was the point.

**Memory Capacity**

RTX 3080 launched with 10 GB — a capacity that generated controversy as 4K textures pushed toward that ceiling. RX 6900 XT's 16 GB was a clear advantage for high-resolution work. NVIDIA later released a 12 GB RTX 3080 to address this.

---

## Software

**FidelityFX Library Expansion**

AMD expanded the FidelityFX open-source effects library significantly during the RDNA 2 era.

| Feature | Description |
|:---|:---|
| FSR 1.0 (2021.06) | Spatial upscaling (Easu + Rcas), hardware-agnostic |
| CAS | Contrast Adaptive Sharpening |
| CACAO | Ambient occlusion |
| Denoiser | RT noise removal |

All FidelityFX effects are open-source and hardware-agnostic — they run on NVIDIA GPUs as well. This contrasts directly with DLSS, which is closed and limited to NVIDIA hardware with Tensor Cores.

**ROCm**

ROCm progressed through version 4.x during the RDNA 2 period, but the primary compute target remained CDNA 1 (Arcturus, MI100). RDNA 2 received some compute improvements over RDNA 1, but HPC and ML workloads were directed to the CDNA line.

---

## Summary

| Item | Change vs. RDNA 1 |
|:---|:---|
| Ray Tracing | Software fallback → Ray Accelerator (1 per CU) |
| Extra cache | None → Infinity Cache 128 MB (on-die SRAM) |
| Mesh Shader | Not supported → Supported |
| VRS | Tier 1 → Tier 2 |
| SAM | None → Supported |
| Max CUs | 40 → 80 (Big Navi) |
| Boost clock (flagship) | ~1,905 MHz → ~2,250 MHz (+18%) |
| VRAM (flagship) | 8 GB → 16 GB |
| Console basis | None → Xbox Series X / PS5 |

| | RX 6900 XT (RDNA 2) | RTX 3080 10G (Ampere) |
|:---|:---:|:---:|
| FP32 TFLOPS | 23.04 | 29.77 |
| Raw memory BW | 512 GB/s | 760 GB/s |
| Effective memory BW | ~1,664 GB/s (IC) | 760 GB/s |
| Raster 1440p | Comparable | Comparable |
| Raster 4K | Slightly behind | Slightly ahead |
| Ray tracing | 1st-gen, behind | 2nd-gen, ahead |
| Upscaling | FSR 1.0 (spatial) | DLSS 2.0 (AI) |
| VRAM | 16 GB | 10 GB |

RDNA 2 closed the RT gap that RDNA 1 left open. Infinity Cache was an inventive workaround for GDDR6's bandwidth ceiling, and Big Navi gave AMD a presence in the high-end market for the first time. Against Ampere's 2nd-gen RT Core and DLSS 2.0, the gap in ray tracing and AI-driven upscaling remained wider than one generation could close.

Next: RDNA 3 — chiplet die split (GCD+MCD), dual-issue shaders, 5nm transition (upcoming)
