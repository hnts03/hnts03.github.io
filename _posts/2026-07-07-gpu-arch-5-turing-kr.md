---
layout: post
title: "GPU 아키텍처 #5: Turing - RT Core와 2세대 Tensor Core"
subtitle: "실시간 레이트레이싱 전용 하드웨어, INT8/INT4 Tensor Core, 그리고 소비자 GPU의 AI 가속"
tags: [GPU, Architecture, CUDA, NVIDIA, Turing, RayTracing, TensorCore, Computer-Architecture]
lang: kr
translation-url: /2026-07-07-gpu-arch-5-turing-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 |
|:--:|:---|
| 1 | [GPU의 출발과 SIMT의 탄생 - Tesla, Fermi](/2026-04-12-gpu-arch-1-tesla-fermi-kr/) |
| 2 | [Kepler와 Maxwell - 효율성의 탐구](/2026-07-06-gpu-arch-2-kepler-maxwell-kr/) |
| 3 | [Pascal - 16nm, HBM2, NVLink](/2026-07-07-gpu-arch-3-pascal-kr/) |
| 4 | [Volta - Tensor Core와 독립 스레드 스케줄링](/2026-07-07-gpu-arch-4-volta-kr/) |
| **5** | **Turing - RT Core와 2세대 Tensor Core** |
| 6 | GPU 메모리 시스템과 최적화 |

---

## Volta 이후의 과제

2017년 V100은 데이터센터 전용 제품이었다. GV100 다이는 815mm²에 21.1B 트랜지스터, TDP 300W로 소비자 GPU 시장에 투입할 수 없었다. Volta의 Tensor Core와 독립 스레드 스케줄링은 연구소 서버 안에 갇혀 있었다.

동시에 그래픽 렌더링의 오랜 문제가 있었다. **레이트레이싱**은 물리적으로 정확한 조명을 계산하지만, 광선 하나가 장면의 수백만 개 삼각형 중 어느 것과 교차하는지 탐색하는 비용이 너무 컸다. 오프라인 렌더링에서는 수 시간을 투자할 수 있지만, 실시간 게임에서는 16ms(60 fps) 안에 한 프레임을 완성해야 한다.

Turing(2018)은 두 방향을 동시에 열었다. 레이트레이싱 전용 하드웨어(RT Core)로 실시간 레이트레이싱을 가능하게 하고, 2세대 Tensor Core로 INT8/INT4 추론을 소비자 GPU에 처음 가져왔다.

---

## 다이 스펙

| | Volta GV100 | Turing TU102 | Turing TU104 | Turing T4 |
|:---|:---:|:---:|:---:|:---:|
| 공정 | 12nm FFN | **12nm FFN** | 12nm FFN | 12nm FFN |
| 트랜지스터 | 21.1B | **18.6B** | 13.6B | 13.6B |
| 다이 면적 | 815mm² | **754mm²** | 545mm² | 545mm² |
| SM 수 (전체) | 80 | **72** | 48 | 40 |
| 대표 제품 | Tesla V100 | RTX 2080 Ti | RTX 2080 | Tesla T4 |
| 포지셔닝 | 데이터센터 | 소비자 | 소비자 | 추론 전용 |

공정 노드는 12nm FFN으로 Volta와 동일하다. 다이 크기가 줄어든 이유는 FP64 코어 제거와 RT Core 추가 사이의 면적 균형 때문이다.

---

## RT Core: 레이트레이싱 전용 하드웨어

### 레이트레이싱의 병목

레이트레이싱에서 광선 하나는 다음 단계를 거친다.

```
카메라 → 광선 생성 → BVH 탐색 → 교차 테스트 → 셰이딩 → 반사/굴절 → 재귀
```

**BVH(Bounding Volume Hierarchy)**는 장면의 삼각형들을 계층적 AABB(Axis-Aligned Bounding Box)로 묶은 가속 구조다. 광선이 BVH의 상위 노드와 교차하지 않으면 그 하위 삼각형 전체를 건너뛴다.

GPU에서 BVH 탐색은 분기가 많고 데이터 의존적이다. 한 warp 안에서도 광선마다 다른 BVH 노드를 탐색하므로 divergence가 심하다. 소프트웨어로만 구현하면 FP32 코어를 수백 사이클 독점하면서 다른 작업을 차단한다.

### RT Core가 하는 일

**RT Core**는 SM당 1개 배치된 고정 기능 유닛이다. SM에서 `TraceRay()` 명령을 받으면 RT Core가 독립적으로 동작한다.

```
SM (쉐이더 실행)
│
├─ TraceRay() 호출 ──→ RT Core
│   └─ Warp 일시 정지             │
│                                  ├─ BVH 노드 탐색 (TLAS → BLAS)
│   (다른 Warp 실행으로 전환)      ├─ Ray-AABB 교차 테스트
│                                  ├─ Ray-Triangle 교차 테스트
│                                  └─ 결과 반환
│
└─ 결과 수신 → Warp 재개 → ClosestHitShader / MissShader 실행
```

RT Core가 처리하는 것:
- TLAS(Top-Level Acceleration Structure): 장면 내 오브젝트 레벨 BVH 탐색
- BLAS(Bottom-Level Acceleration Structure): 오브젝트 내 삼각형 레벨 BVH 탐색
- Ray-AABB 교차 테스트: 각 BVH 노드 AABB와의 교차 여부
- Ray-Triangle 교차 테스트: 최종 교차 삼각형 확정 및 barycentric 좌표 계산

RT Core가 처리하지 않는 것:
- `ClosestHitShader`: 가장 가까운 교차점에서의 셰이딩 (SM 실행)
- `MissShader`: 교차 없을 때의 처리 (SM 실행)
- `AnyHitShader`: 교차 도중 호출 (SM 실행, 투명도 처리 등)
- 반사/굴절로 인한 재귀적 `TraceRay()` (다시 RT Core로 dispatch)

### Warp 일시 정지와 지연 은닉

RT Core가 BVH를 탐색하는 동안 SM은 해당 warp를 일시 정지하고 다른 ready warp로 전환한다. 메모리 접근의 지연을 warp 전환으로 숨기는 것과 동일한 원리다. 충분한 warp가 있으면 RT Core의 수백 사이클 지연이 다른 작업으로 채워진다.

---

## 2세대 Tensor Core: INT8과 INT4

### Volta Tensor Core의 한계

1세대 Tensor Core(Volta)는 FP16 입력과 FP32/FP16 누산만 지원했다. 딥러닝 추론에서는 FP16보다 낮은 정밀도로 충분한 경우가 많다. 정수 양자화(INT8, INT4)는 가중치와 활성값의 표현 비트 수를 줄여 계산량과 메모리를 동시에 절감한다.

Pascal에서는 `__dp4a` 명령어로 INT8 dot product를 FP32 코어에서 처리했다. Turing은 INT8과 INT4를 Tensor Core 자체에 통합해 처리량을 대폭 늘렸다.

### 정밀도별 처리량

| 연산 | 입력 타입 | 누산 | RTX 2080 Ti | T4 |
|:---|:---:|:---:|---:|---:|
| FP16 Tensor Core | FP16 | FP32 | 107.9 TFLOPS | 65 TFLOPS |
| INT8 Tensor Core | INT8 | INT32 | 215.2 TOPS | 130 TOPS |
| INT4 Tensor Core | INT4 | INT32 | 430.3 TOPS | 260 TOPS |
| FP32 (CUDA Core) | FP32 | FP32 | 13.4 TFLOPS | 8.1 TFLOPS |

FP16 Tensor Core 대비 INT8은 2배, INT4는 4배다. 비트 폭이 절반으로 줄 때마다 동일 회로에 두 배의 값을 패킹할 수 있기 때문이다.

![Volta V100 vs Turing RTX 2080 Ti 처리량 비교](/assets/img/posts/gpu-arch-5/perf-compare.png)

V100의 FP16 TC(125.3 TFLOPS)가 RTX 2080 Ti(107.9 TFLOPS)보다 높은 이유는 SM 수 차이다(V100 80 SM vs RTX 2080 Ti 68 SM). 반면 RTX 2080 Ti의 INT8 TC(215 TOPS)는 V100에 없는 기능이다.

### WMMA INT8 코드 예시

```cuda
#include <mma.h>
using namespace nvcuda::wmma;

// INT8 입력, INT32 누산: 16×16×16 행렬 곱
fragment<matrix_a, 16, 16, 16, int8_t, row_major> a_frag;
fragment<matrix_b, 16, 16, 16, int8_t, col_major> b_frag;
fragment<accumulator, 16, 16, 16, int32_t>         c_frag;

fill_fragment(c_frag, 0);
load_matrix_sync(a_frag, a_ptr, 16);
load_matrix_sync(b_frag, b_ptr, 16);
mma_sync(c_frag, a_frag, b_frag, c_frag);  // INT8 × INT8 → INT32
store_matrix_sync(c_ptr, c_frag, 16, mem_row_major);
```

Pascal의 `__dp4a`는 4개의 INT8을 묶어 FP32 코어에서 처리한 것이었다. Turing Tensor Core의 INT8은 전용 하드웨어에서 16×16×16 행렬 단위로 처리한다.

---

## Turing SM 구조

### Volta와의 비교

Turing SM의 기본 골격은 Volta와 동일하다. 4개의 Sub-core 구조, 각 Sub-core에 Warp Scheduler 1개, Dispatch Unit 2개, 16 FP32 + 16 INT32 + 2 TC가 배치된다.

```
Turing TU102 SM (Volta 대비 변경사항 표시)
┌────────────────────────────────────────────────────┐
│  L0 Instruction Cache                              │
├──────────────────┬─────────────────────────────────┤
│  Sub-core 0      │  Sub-core 1                     │
│  Warp Scheduler  │  Warp Scheduler                 │
│  Dispatch ×2     │  Dispatch ×2                    │
│  16 FP32         │  16 FP32                        │
│  16 INT32        │  16 INT32                       │
│  [없음: FP64]    │  [없음: FP64]   ← Volta와 차이 │
│  2 TC (2세대)    │  2 TC (2세대)   ← INT8/INT4 추가│
│  8 LD/ST  4 SFU  │  8 LD/ST  4 SFU                 │
├──────────────────┴─────────────────────────────────┤
│  Sub-core 2      │  Sub-core 3                     │
│  (Sub-core 0, 1과 동일 구성)                       │
├────────────────────────────────────────────────────┤
│  RT Core × 1     ← Turing에서 새로 추가            │
├────────────────────────────────────────────────────┤
│  Unified L1 + Shared Memory: 96KB                  │
│  (Volta GV100: 128KB에서 축소)                     │
│  Shared Memory 최대: 64KB   (Volta: 96KB)          │
└────────────────────────────────────────────────────┘
```

### Volta와의 상세 비교

| 항목 | Volta GV100 | Turing TU102 |
|:---|:---:|:---:|
| 공정 | 12nm FFN | 12nm FFN |
| SM당 FP32 | 64 | 64 |
| SM당 INT32 | 64 | 64 |
| SM당 FP64 | **32** | **없음** |
| Tensor Core 세대 | 1세대 | **2세대** |
| TC 지원 정밀도 | FP16 | FP16, **INT8, INT4** |
| SM당 RT Core | 없음 | **1개** |
| Unified L1+Shared | **128KB** | **96KB** |
| 최대 Shared Memory | **96KB** | **64KB** |
| 스레드 스케줄링 | Thread 단위 PC | Thread 단위 PC (계승) |

FP64 코어 제거는 면적 절감과 소비자 GPU 포지셔닝 때문이다. GV100의 32 FP64/SM은 HPC 과학 계산을 위한 설계 선택이었고, 게임/AI 추론 GPU에서는 불필요하다.

---

## 스케줄링: Volta 계승

Turing의 스레드 스케줄링은 Volta(CC 7.0)와 동일하다. CC 7.5인 Turing은 Volta의 독립 스레드 스케줄링을 그대로 이어받았다. 각 스레드가 독립적인 PC(Program Counter)와 콜스택을 유지한다. `__syncwarp()`로 warp 내 스레드를 동기화한다.

새로운 스케줄링 요소는 RT Core 연동이다.

```
Warp 실행 흐름 (RT Core 포함)
────────────────────────────────────────────────────

Cycle 0~N:   Warp A 실행 (일반 CUDA 코드)
Cycle N:     Warp A → TraceRay() 호출
Cycle N+1:   RT Core: BVH 탐색 시작
             Warp Scheduler: Warp A 일시 정지, Warp B 선택
Cycle N+1~M: Warp B, C, D 실행 (RT Core 지연 은닉)
Cycle M:     RT Core: 결과 반환
             Warp Scheduler: Warp A ready 상태로 전환
Cycle M+1:   Warp A 재개 → ClosestHitShader 실행
```

RT Core의 지연(수백~수천 사이클)은 warp 전환으로 은닉된다. 점유율(occupancy)이 충분히 높아야 이 은닉 효과가 발휘된다. RT Core 지연 동안 처리할 warp가 없으면 SM이 idle 상태가 된다.

---

## 소프트웨어

### CUDA 10.0과 API

CUDA 10.0(2018)은 Turing을 지원하는 첫 버전이다. INT8/INT4 WMMA API가 추가됐고, `nvcuda::wmma::experimental::precision::s4`(INT4) 타입이 도입됐다.

### DirectX Raytracing (DXR)

Microsoft는 DirectX 12에 DXR을 추가했다. 레이트레이싱 파이프라인은 기존 래스터라이제이션 파이프라인과 별개로 동작한다.

```
DXR 쉐이더 종류
├─ RayGeneration Shader: 픽셀당 광선 생성, TraceRay() 호출
├─ Intersection Shader:  커스텀 기하(구, 곡면) 교차 테스트
├─ AnyHit Shader:        교차 도중 호출 (투명도, 알파 테스트)
├─ ClosestHit Shader:    가장 가까운 교차에서 셰이딩
└─ Miss Shader:          교차 없을 때 (스카이박스 등)
```

```hlsl
// DXR RayGeneration Shader 예시
[shader("raygeneration")]
void RayGen() {
    RayDesc ray;
    ray.Origin    = g_camera.position;
    ray.Direction = ComputeRayDirection(DispatchRaysIndex());
    ray.TMin      = 0.001;
    ray.TMax      = 10000.0;

    RayPayload payload = { float4(0, 0, 0, 0) };
    TraceRay(g_scene,        // acceleration structure
             RAY_FLAG_NONE,
             0xFF,
             0, 1, 0,        // hit group offsets
             ray, payload);

    g_output[DispatchRaysIndex().xy] = payload.color;
}
```

Vulkan은 `VK_KHR_ray_tracing_pipeline` 확장으로 동등한 기능을 제공한다.

### OptiX 7

**OptiX 7**은 CUDA 기반 레이트레이싱 API다. DXR/Vulkan이 그래픽 렌더링을 대상으로 한다면, OptiX는 과학 시뮬레이션, 오프라인 렌더링, 물리 기반 시뮬레이션에 쓰인다.

```cuda
// OptiX 7: 광선 추적 커널 파이프라인 설정 (호스트)
OptixPipelineCompileOptions pco = {};
pco.usesMotionBlur        = false;
pco.traversableGraphFlags = OPTIX_TRAVERSABLE_GRAPH_FLAG_ALLOW_SINGLE_GAS;
pco.numPayloadValues      = 3;
pco.numAttributeValues    = 3;

OptixPipeline pipeline;
optixPipelineCreate(context, &pco, &plo, &program_groups[0],
                    num_groups, log, &log_size, &pipeline);
```

### DLSS 1.0

**DLSS(Deep Learning Super Sampling)**는 Tensor Core를 활용한 AI 업스케일링이다. 낮은 해상도로 렌더링한 뒤, 사전 학습된 신경망으로 고해상도로 업스케일한다. DLSS 1.0은 게임별 학습 모델을 사용했다.

```
DLSS 1.0 파이프라인
게임 해상도: 1080p → DLSS 업스케일 → 출력: 4K
렌더링 비용: 1080p 수준
화질:        4K에 근접

Tensor Core 사용: INT8 추론으로 업스케일 네트워크 실행
```

---

## 정리

| | Volta GV100 | Turing TU102 |
|:---|:---:|:---:|
| 공정 | 12nm FFN | 12nm FFN |
| 포지셔닝 | 데이터센터 HPC/AI | **소비자 + 추론** |
| 대표 제품 | Tesla V100 | RTX 2080 Ti |
| SM당 FP32 | 64 | 64 |
| SM당 FP64 | **32** | **없음** |
| Tensor Core 지원 | FP16 | FP16 + **INT8 + INT4** |
| RT Core | 없음 | **1개/SM** |
| 메모리 | HBM2 900 GB/s | GDDR6 616 GB/s |
| Unified L1+Shared | 128KB | **96KB** |
| 스레드 스케줄링 | 독립 Thread PC | 독립 Thread PC (동일) |
| 주요 API 추가 | WMMA FP16, CG | **DXR, OptiX 7, DLSS** |

Turing의 핵심은 두 가지다. RT Core로 실시간 레이트레이싱의 문을 열었고, INT8/INT4 Tensor Core로 AI 추론 가속을 소비자 GPU에 가져왔다. Volta의 FP64 HPC 특화 설계를 걷어내고, 그래픽과 AI의 교차점을 겨냥한 것이 Turing의 선택이었다.

다음 포스트에서는 Ampere를 다룬다: 3세대 Tensor Core의 Sparsity 가속, A100의 MIG(Multi-Instance GPU), 그리고 NVLink 3.0.

---

## References

- NVIDIA. *NVIDIA Turing GPU Architecture Whitepaper*, 2018. [PDF](https://images.nvidia.com/akamai/technology/turing/NVIDIA-Turing-Architecture-Whitepaper.pdf)
- NVIDIA. *NVIDIA Turing Architecture In-Depth*. NVIDIA Developer Blog, 2018. [Link](https://developer.nvidia.com/blog/nvidia-turing-architecture-in-depth/)
- NVIDIA. *Introduction to Real-Time Ray Tracing with Vulkan*. NVIDIA Developer Blog, 2018.
- Microsoft. *DirectX Raytracing (DXR) Functional Spec*. GitHub, 2018.
- NVIDIA. *OptiX 7 Programming Guide*. NVIDIA Developer Documentation.
- NVIDIA. *TensorRT Developer Guide: INT8 Inference*. NVIDIA Developer Documentation.
