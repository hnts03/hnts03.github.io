---
layout: post
title: "GPU Architecture #5: Turing — RT Cores and 2nd-Gen Tensor Cores"
subtitle: "Hardware ray tracing acceleration, INT8/INT4 Tensor Cores, and AI inference on consumer GPUs"
tags: [GPU, Architecture, CUDA, NVIDIA, Turing, RayTracing, TensorCore, Computer-Architecture]
lang: en
translation-url: /2026-07-07-gpu-arch-5-turing-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic |
|:--:|:---|
| 1 | [The Origins of GPU and the Birth of SIMT — Tesla, Fermi](/2026-04-12-gpu-arch-1-tesla-fermi-en/) |
| 2 | [Kepler and Maxwell — The Pursuit of Efficiency](/2026-07-06-gpu-arch-2-kepler-maxwell-en/) |
| 3 | [Pascal — 16nm, HBM2, NVLink](/2026-07-07-gpu-arch-3-pascal-en/) |
| 4 | [Volta — Tensor Cores and Independent Thread Scheduling](/2026-07-07-gpu-arch-4-volta-en/) |
| **5** | **Turing — RT Cores and 2nd-Gen Tensor Cores** |
| 6 | GPU Memory Systems and Optimization |

---

## After Volta

The V100 was a datacenter-only product. At 815mm², 300W TDP, and priced for server racks, it never reached consumer hands. Volta's Tensor Cores and Independent Thread Scheduling remained locked inside research clusters.

Meanwhile, **real-time ray tracing** remained an unsolved problem for consumer graphics. Ray tracing produces physically accurate lighting by testing each ray against every triangle in a scene — a task that consumed hours in offline renderers. A game must complete one frame in 16ms at 60 fps.

Turing (2018) opened two directions simultaneously. Its **RT Core** — a fixed-function hardware unit for BVH traversal and ray intersection — made real-time ray tracing practical. Its **2nd-generation Tensor Cores** brought INT8 and INT4 inference acceleration to consumer GPUs for the first time.

---

## Die Specifications

| | Volta GV100 | Turing TU102 | Turing TU104 | Turing T4 |
|:---|:---:|:---:|:---:|:---:|
| Process | 12nm FFN | **12nm FFN** | 12nm FFN | 12nm FFN |
| Transistors | 21.1B | **18.6B** | 13.6B | 13.6B |
| Die Area | 815mm² | **754mm²** | 545mm² | 545mm² |
| Full-die SMs | 80 | **72** | 48 | 40 |
| Representative | Tesla V100 | RTX 2080 Ti | RTX 2080 | Tesla T4 |
| Target | Datacenter HPC/AI | Consumer | Consumer | Inference |

The process node remains 12nm FFN — identical to Volta. The smaller die reflects the removal of FP64 units and the consumer GPU power envelope target.

---

## RT Core: Hardware Ray Tracing

### The Traversal Bottleneck

A single ray trace follows this path:

```
Camera → Ray generation → BVH traversal → Intersection test → Shading → Reflection/refraction → Recurse
```

A **BVH (Bounding Volume Hierarchy)** organizes scene triangles into nested Axis-Aligned Bounding Boxes (AABBs). When a ray misses a parent AABB, all triangles within it are skipped — turning an O(n) exhaustive search into O(log n) average traversal.

On a GPU, BVH traversal is branch-heavy and data-dependent: different rays in the same warp diverge to different BVH nodes, causing severe warp divergence. A software-only implementation occupies FP32 cores for hundreds of cycles per ray, blocking all other work.

### What RT Core Does

One **RT Core** is placed per SM as a fixed-function unit. When a shader calls `TraceRay()`, the RT Core takes over:

```
SM (shader execution)
│
├─ TraceRay() issued ──→ RT Core
│   └─ Warp suspended              │
│                                  ├─ Traverse TLAS (scene-level BVH)
│   (Switch to other warps)        ├─ Traverse BLAS (object-level BVH)
│                                  ├─ Ray-AABB intersection tests
│                                  ├─ Ray-triangle intersection tests
│                                  └─ Return hit record (t, barycentrics)
│
└─ Result received → Warp resumes → ClosestHitShader / MissShader
```

RT Core handles: TLAS/BLAS traversal, ray-AABB and ray-triangle intersection, barycentric coordinate computation.

RT Core does **not** handle: `ClosestHitShader`, `MissShader`, `AnyHitShader`, or recursive `TraceRay()` calls — all of which execute on the SM's programmable cores.

### Latency Hiding via Warp Switching

While the RT Core traverses the BVH (potentially hundreds to thousands of cycles), the warp scheduler suspends the requesting warp and switches to ready warps. This is the same latency-hiding mechanism used for memory accesses. High occupancy is critical: if no other warps are ready when the RT Core is working, the SM stalls.

---

## 2nd-Generation Tensor Cores: INT8 and INT4

### Volta's Gap

Volta's 1st-generation Tensor Cores supported only FP16 inputs with FP32/FP16 accumulation. For inference, FP16 often carries more precision than needed. **Quantization** — representing weights and activations in INT8 or INT4 — reduces memory footprint and computation in exchange for a small accuracy trade-off.

Pascal's `__dp4a` instruction handled INT8 dot products on FP32 cores. Turing integrates INT8 and INT4 directly into Tensor Core hardware, multiplying throughput.

### Precision Throughput Ladder

| Precision | Input | Accumulator | RTX 2080 Ti | T4 |
|:---|:---:|:---:|---:|---:|
| FP16 Tensor Core | FP16 | FP32 | 107.9 TFLOPS | 65 TFLOPS |
| INT8 Tensor Core | INT8 | INT32 | 215.2 TOPS | 130 TOPS |
| INT4 Tensor Core | INT4 | INT32 | 430.3 TOPS | 260 TOPS |
| FP32 (CUDA Core) | FP32 | FP32 | 13.4 TFLOPS | 8.1 TFLOPS |

Each halving of bit-width doubles throughput: two INT8 values pack into the space of one FP16 value, so the same matrix-multiply circuit processes twice as many operations per cycle.

![Volta V100 vs Turing RTX 2080 Ti throughput comparison](/assets/img/posts/gpu-arch-5/perf-compare.png)

The V100's FP16 TC advantage (125.3 vs 107.9 TFLOPS) comes from its larger SM count (80 vs 68 active). Turing's INT8 TC (215 TOPS) has no Volta equivalent — V100's `__dp4a` path peaks around 62 TOPS for INT8 dot products.

### WMMA INT8 Example

```cuda
#include <mma.h>
using namespace nvcuda::wmma;

// INT8 inputs, INT32 accumulation — 16×16×16 tile
fragment<matrix_a, 16, 16, 16, int8_t, row_major> a_frag;
fragment<matrix_b, 16, 16, 16, int8_t, col_major> b_frag;
fragment<accumulator, 16, 16, 16, int32_t>         c_frag;

fill_fragment(c_frag, 0);
load_matrix_sync(a_frag, a_ptr, 16);
load_matrix_sync(b_frag, b_ptr, 16);
mma_sync(c_frag, a_frag, b_frag, c_frag);
store_matrix_sync(c_ptr, c_frag, 16, mem_row_major);
```

Pascal's `__dp4a` grouped four INT8 values for a dot product on FP32 cores. Turing's Tensor Core INT8 operates on full 16×16×16 matrices in dedicated hardware.

---

## Turing SM Structure

### Overview

The Turing SM preserves Volta's 4 sub-core layout: 4 warp schedulers, 4 pairs of dispatch units, 64 FP32, 64 INT32, and 8 Tensor Cores per SM. The key additions and removals:

```
Turing TU102 SM (changes from Volta marked)
┌──────────────────────────────────────────────────────┐
│  L0 Instruction Cache                                │
├───────────────────┬──────────────────────────────────┤
│  Sub-core 0       │  Sub-core 1                      │
│  Warp Scheduler   │  Warp Scheduler                  │
│  Dispatch ×2      │  Dispatch ×2                     │
│  16 FP32          │  16 FP32                         │
│  16 INT32         │  16 INT32                        │
│  [removed: FP64]  │  [removed: FP64]  ← vs Volta     │
│  2 TC (2nd gen)   │  2 TC (2nd gen)   ← INT8/INT4   │
│  8 LD/ST  4 SFU   │  8 LD/ST  4 SFU                  │
├───────────────────┴──────────────────────────────────┤
│  Sub-core 2       │  Sub-core 3 (same as 0, 1)       │
├──────────────────────────────────────────────────────┤
│  RT Core × 1      ← new in Turing                    │
├──────────────────────────────────────────────────────┤
│  Unified L1 + Shared Memory: 96KB                    │
│  (Volta GV100: 128KB — reduced in Turing)            │
│  Max Shared Memory: 64KB   (Volta: 96KB)             │
└──────────────────────────────────────────────────────┘
```

### Volta vs Turing Comparison

| Feature | Volta GV100 | Turing TU102 |
|:---|:---:|:---:|
| Process | 12nm FFN | 12nm FFN |
| FP32 / SM | 64 | 64 |
| INT32 / SM | 64 | 64 |
| FP64 / SM | **32** | **none** |
| Tensor Core generation | 1st | **2nd** |
| TC precision support | FP16 | FP16 + **INT8 + INT4** |
| RT Core / SM | none | **1** |
| Unified L1 + Shared | **128KB** | **96KB** |
| Max Shared Memory | **96KB** | **64KB** |
| Thread scheduling | Per-thread PC | Per-thread PC (inherited) |
| Memory | HBM2 900 GB/s | GDDR6 616 GB/s |

FP64 removal reflects the consumer and inference positioning: the 32 FP64 cores per SM in GV100 consumed significant die area for HPC double-precision workloads that gaming and AI inference do not need.

The reduction from 128KB to 96KB unified L1/Shared partially offset the RT Core area addition while staying on the same 12nm process. Maximum shared memory per SM drops from 96KB to 64KB.

---

## Scheduling: Inherited from Volta

Turing (CC 7.5) inherits Volta's (CC 7.0) thread scheduling without modification. Each thread maintains an independent Program Counter and call stack. `__syncwarp()` is required to synchronize threads within a warp after potential divergence.

The only new scheduling behavior is RT Core dispatch:

```
Warp execution timeline (with RT Core)
─────────────────────────────────────────────────────

Cycles 0–N:   Warp A executes (general CUDA)
Cycle N:      Warp A issues TraceRay()
Cycle N+1:    RT Core begins BVH traversal
              Warp Scheduler: suspend Warp A, select Warp B
Cycles N+1–M: Warps B, C, D execute (hiding RT Core latency)
Cycle M:      RT Core returns hit record
              Warp Scheduler: Warp A transitions to ready
Cycle M+1:    Warp A resumes → ClosestHitShader executes
```

RT Core latency ranges from hundreds to thousands of cycles depending on BVH depth and ray coherence. Adequate warp occupancy is the primary lever for hiding this cost.

---

## Software

### CUDA 10.0

CUDA 10.0 (2018) is the first release with full Turing support. Additions include:

- `nvcuda::wmma::experimental::precision::s4` — INT4 Tensor Core fragments
- `nvcuda::wmma::experimental::precision::u4` — unsigned INT4
- RT Core access via OptiX 7 (CUDA-side) and DXR/Vulkan (graphics-side)

### DirectX Raytracing (DXR)

DXR is Microsoft's ray tracing extension to DirectX 12. It defines five programmable shader types:

```
DXR shader pipeline
├─ RayGeneration: one invocation per pixel, calls TraceRay()
├─ Intersection:  custom geometry (spheres, procedural surfaces)
├─ AnyHit:        called per candidate hit — used for alpha testing
├─ ClosestHit:    shading at the confirmed nearest intersection
└─ Miss:          executes when no geometry is hit (skybox, etc.)
```

```hlsl
[shader("raygeneration")]
void RayGen() {
    RayDesc ray;
    ray.Origin    = g_camera.position;
    ray.Direction = ComputeRayDirection(DispatchRaysIndex());
    ray.TMin      = 0.001;
    ray.TMax      = 10000.0;

    RayPayload payload = { float4(0, 0, 0, 0) };
    TraceRay(g_scene, RAY_FLAG_NONE, 0xFF, 0, 1, 0, ray, payload);
    g_output[DispatchRaysIndex().xy] = payload.color;
}
```

Vulkan provides equivalent functionality through `VK_KHR_ray_tracing_pipeline`, with `vkCmdTraceRaysKHR()` as the dispatch entry point.

### OptiX 7

**OptiX 7** is NVIDIA's CUDA-based ray tracing framework targeting scientific and offline rendering workloads. Unlike DXR/Vulkan, OptiX integrates with CUDA streams and memory allocations directly.

### DLSS 1.0

**DLSS (Deep Learning Super Sampling)** uses Tensor Cores to run a neural network that upscales a low-resolution rendered frame to the target display resolution. Version 1.0 required per-game trained models. The network runs in INT8 on Turing's Tensor Cores.

```
DLSS 1.0 pipeline
Render at:  1080p  →  Tensor Core neural upscaler  →  Output: 4K
Render cost: ~1080p workload
Image quality: approaching native 4K
```

---

## Summary

| | Volta GV100 | Turing TU102 |
|:---|:---:|:---:|
| Process | 12nm FFN | 12nm FFN |
| Target market | Datacenter HPC/AI | **Consumer + inference** |
| FP64 / SM | **32** | **none** |
| Tensor Core precision | FP16 | FP16 + **INT8 + INT4** |
| RT Core | none | **1 / SM** |
| Memory | HBM2 900 GB/s | GDDR6 616 GB/s |
| Max Shared Memory | **96KB** | **64KB** |
| Thread scheduling | Per-thread PC | Per-thread PC (identical) |
| Key new APIs | WMMA, Cooperative Groups | **DXR, Vulkan RT, OptiX 7, DLSS** |

Turing made two bets. The RT Core opened the door to real-time ray tracing — hardware that had been computationally infeasible for decades. The INT8/INT4 Tensor Cores brought inference acceleration into consumer hands for the first time, enabling DLSS and TensorRT deployments on gaming GPUs. Volta's FP64 HPC focus was replaced by a graphics-and-inference intersection.

The next post covers Ampere — 3rd-generation Tensor Cores with structured sparsity, A100's Multi-Instance GPU (MIG), and NVLink 3.0.

---

## References

- NVIDIA. *NVIDIA Turing GPU Architecture Whitepaper*, 2018. [PDF](https://images.nvidia.com/akamai/technology/turing/NVIDIA-Turing-Architecture-Whitepaper.pdf)
- NVIDIA. *NVIDIA Turing Architecture In-Depth*. NVIDIA Developer Blog, 2018. [Link](https://developer.nvidia.com/blog/nvidia-turing-architecture-in-depth/)
- NVIDIA. *Introduction to Real-Time Ray Tracing with Vulkan*. NVIDIA Developer Blog, 2018.
- Microsoft. *DirectX Raytracing (DXR) Functional Spec*. GitHub, 2018.
- NVIDIA. *OptiX 7 Programming Guide*. NVIDIA Developer Documentation.
- NVIDIA. *TensorRT Developer Guide: INT8 Inference*. NVIDIA Developer Documentation.
