---
layout: post
title: "GPU 아키텍처 #3: Pascal - 16nm, HBM2, NVLink"
subtitle: "FinFET 공정 전환, GP100 SM 재설계, Unified Memory의 도약"
tags: [GPU, Architecture, CUDA, NVIDIA, Pascal, Computer-Architecture]
lang: kr
translation-url: /2026-07-07-gpu-arch-3-pascal-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 |
|:--:|:---|
| 1 | [GPU의 기원과 SIMT의 탄생 - Tesla, Fermi](/2026-04-12-gpu-arch-1-tesla-fermi-kr/) |
| 2 | [Kepler과 Maxwell - 효율의 추구](/2026-07-06-gpu-arch-2-kepler-maxwell-kr/) |
| **3** | **Pascal - 16nm FinFET과 NVLink의 등장** |
| 4 | Volta와 Ampere - Tensor Core와 딥러닝 전용 가속 |
| 5 | GPU 메모리 시스템과 최적화 |
| 6 | GPU 내부 구조 - 파이프라인과 실행 유닛 |

---

## Maxwell이 남긴 과제

28nm 공정 위에서 Maxwell은 Kepler 대비 코어당 성능을 40% 끌어올렸다. 하지만 28nm 자체의 물리적 한계는 넘을 수 없었다. GM200의 다이 면적은 601mm², TDP 250W. 더 이상 코어를 늘려도 성능이 비례하지 않는 지점이었다.

두 번째 한계는 메모리 대역폭이었다. Maxwell Titan X의 대역폭은 336 GB/s, PCIe 3.0 x16의 양방향 대역폭은 약 31 GB/s. 멀티 GPU 워크로드에서 GPU 간 데이터 교환은 이 병목을 통과해야 했다.

Pascal(2016)은 두 문제를 동시에 공략했다: TSMC 16nm FinFET 공정 전환, HBM2 적층 메모리, NVLink 인터커넥트.

---

## 공정 전환과 SM 재설계

### 다이 스펙 비교

| | GM200 (Maxwell) | GP100 | GP102 | GP104 |
|:---|:---:|:---:|:---:|:---:|
| 공정 | 28nm | **16nm FinFET** | 16nm FinFET | 16nm FinFET |
| 트랜지스터 | 8.0B | **15.3B** | ~12B | ~7.2B |
| 다이 크기 | 601mm² | 610mm² | ~471mm² | ~314mm² |
| CUDA Core/SM | 128 | **64** | 128 | 128 |
| SM 수 | 24 | 60 | 28 | 20 |
| Compute Capability | 5.2 | **6.0** | 6.1 | 6.1 |
| 대표 제품 | Titan X '15 | Tesla P100 | GTX 1080 Ti | GTX 1080 |

같은 다이 면적에 트랜지스터를 거의 2배 집적했다.

### GP100: 2 Processing Block 구조

Maxwell SMM의 4 Quadrant 구조와 달리, GP100 SM은 **2개의 Processing Block**으로 구성된다. 각 블록은 Warp Scheduler 1개 + Dispatch Unit 2개 + 32 FP32 코어 + 16 FP64 코어를 독립적으로 포함한다.

```
GP100 SM (64 FP32 + 32 FP64)
┌──────────────────────────────────────────┐
│  Processing Block 0                      │
│  Warp Scheduler  │  Dispatch Unit ×2    │
│  32 FP32 Cores   │  16 FP64 Cores      │
│  8 LD/ST Units   │  8 SFU              │
├──────────────────────────────────────────┤
│  Processing Block 1                      │
│  Warp Scheduler  │  Dispatch Unit ×2    │
│  32 FP32 Cores   │  16 FP64 Cores      │
│  8 LD/ST Units   │  8 SFU              │
├──────────────────────────────────────────┤
│  Shared Memory 64KB  │  L1+Tex (완전 분리) │
│  Register File 256KB (65K×32b)           │
└──────────────────────────────────────────┘
```

스케줄러당 FP32 코어 비율은 32:1로, Maxwell Quadrant와 동일하다. 핵심 변화는 **FP64 코어 비율**이다. GM200은 FP32의 1/32(4 FP64/SM)였으나 GP100은 FP32의 1/2(32 FP64/SM)다. HPC 과학 계산의 FP64 요구를 직접 겨냥한 설계 선택이다.

GP102/GP104는 Maxwell SMM의 4 Quadrant 128코어 구조를 그대로 유지했다. FP64 코어는 4개/SM(32:1). 소비자 GPU로서의 성격에 맞게 FP64 성능을 제한했다.

![SM 구조 비교: Maxwell → Pascal](/assets/img/posts/gpu-arch-3/sm-compare.png)

---

## HBM2와 NVLink: 대역폭의 재정의

### HBM2 (GP100 전용)

GP100은 GDDR 메모리 대신 패키지 내부에 **HBM2** 스택을 직접 탑재했다.

```
GP100 패키지 레이아웃
┌────────────────────────────────────────────┐
│  GPU Die ──┬── HBM2 Stack 0 (4GB)          │
│            ├── HBM2 Stack 1 (4GB)          │
│            ├── HBM2 Stack 2 (4GB)          │
│            └── HBM2 Stack 3 (4GB)          │
│                                            │
│  버스 폭: 4,096-bit (스택당 1,024-bit)     │
│  총 VRAM:  16 GB                           │
│  대역폭:   732 GB/s                        │
└────────────────────────────────────────────┘
```

Maxwell GM200(336 GB/s) 대비 2.2배, GP104 GDDR5X(320 GB/s) 대비 2.3배다.

### NVLink 1.0 (GP100 전용)

| | PCIe 3.0 x16 | NVLink 1.0 (GP100) |
|:---|:---:|:---:|
| 링크 수 | - | 4 |
| 링크당 대역폭 | - | 20 GB/s 양방향 |
| 총 대역폭 | **~31 GB/s** | **160 GB/s** |
| PCIe 대비 | 1× | **약 5×** |

**NVLink**는 PCIe를 대체하는 GPU 간 인터커넥트다. DGX-1 서버의 8개 P100은 NVLink 메시 토폴로지로 연결된다. AllReduce 통신이 PCIe 병목 없이 GPU 간 직접 진행된다.

---

## FP16: 딥러닝 가속의 발판

GP100은 `half2` 벡터 타입으로 하나의 32-bit 레지스터에 FP16 값 2개를 패킹하고, 한 클록에 2개를 동시 처리한다.

| | FP64 | FP32 | FP16 |
|:---|:---:|:---:|:---:|
| P100 SXM2 (TFLOPS) | 5.3 | 10.6 | **21.2** |
| FP32 대비 비율 | 0.5× | 1× | **2×** |

```cuda
#include <cuda_fp16.h>
__global__ void fp16_fma(half2 *a, half2 *b, half2 *c, half2 *d) {
    int i = threadIdx.x;
    d[i] = __hfma2(a[i], b[i], c[i]);  // FMA 2개를 한 클록에
}
```

GP102/GP104(CC 6.1)의 FP16 처리량은 FP32의 **1/64**로, 소프트웨어 에뮬레이션 수준이다. 반면 INT8 dot product(`__dp4a`)는 CC 6.1 전체에서 FP32와 동등한 처리량을 제공한다.

GP100의 native FP16은 2017년 Volta Tensor Core가 등장하기 전까지 혼합 정밀도 학습의 유일한 하드웨어 기반이었다.

---

## Unified Memory의 도약

### Maxwell의 한계

`cudaMallocManaged()`로 할당된 메모리는 커널 실행 전 모든 페이지를 GPU로 미리 이동했다(eager migration). GPU 메모리 용량을 초과하는 데이터셋은 불가능했다. CPU와 GPU가 동시에 같은 managed 메모리에 접근하면 segfault였다.

### Pascal: Page Migration Engine

GPU 스레드가 non-resident 페이지에 접근하면 **Page Migration Engine**이 OS에 fault를 발생시킨다. OS는 해당 페이지를 GPU로 이동하고 스레드를 재개한다.

```
Maxwell: Eager Migration             Pascal: On-demand Migration
────────────────────────             ────────────────────────────────
커널 launch 전:                       커널 실행 중:
  전체 managed pages을                  스레드 → non-resident 페이지 접근
  GPU로 일괄 이동                          → Page Migration Engine 개입
                                           → OS fault → 해당 페이지만 GPU로 이동
                                           → 스레드 재개

GPU 용량 초과:  불가              →   가능 (oversubscription)
CPU 동시 접근:  불가              →   가능
가상 주소 공간: GPU 메모리 크기   →   49-bit (512 TB, CPU+GPU 전체)
```

CUDA 8.0은 두 가지 API를 추가했다.

```cuda
// 비동기 prefetch - 컴퓨트 스트림과 overlap 가능
cudaMemPrefetchAsync(data, size, device_id, stream);

// 메모리 접근 패턴 힌트
cudaMemAdvise(data, size, cudaMemAdviseSetReadMostly, device_id);
// read-mostly 표시 데이터는 CPU/GPU 양쪽에 자동 복제
```

NVLink가 있는 P100 시스템에서 GPU 메모리 초과 데이터셋을 처리할 때, hint + prefetch를 활용하면 default 대비 성능이 약 2배 향상된다. NVLink의 넓은 대역폭이 page migration 비용을 흡수하기 때문이다. PCIe 시스템에서는 손실이 더 크다.

---

## Compute Preemption

Maxwell은 CUDA 블록 경계에서만 컨텍스트 전환이 가능했다. 수초 단위의 컴퓨트 커널이 실행되는 동안 그래픽 렌더링은 완전히 차단됐다.

Pascal(CC 6.x, GP100/GP102/GP104 전체)은 **instruction-level preemption**을 도입했다. 임의의 instruction 경계에서 커널을 중단하고 컨텍스트를 저장한다. 컴퓨트와 그래픽이 하나의 GPU에서 타임슬라이싱으로 공존한다. 인터랙티브 커널 디버깅도 가능해졌다.

---

## 정리

| | Maxwell GM200 | Pascal GP100 | Pascal GP104 |
|:---|:---:|:---:|:---:|
| 공정 | 28nm | **16nm FinFET** | 16nm FinFET |
| CUDA Core/SM | 128 (4 Quad) | **64** (2 PB) | 128 (4 Quad) |
| FP64 비율 | 1/32 | **1/2** | 1/32 |
| 메모리 | GDDR5 336 GB/s | **HBM2 732 GB/s** | GDDR5X 320 GB/s |
| GPU 간 인터커넥트 | PCIe ~31 GB/s | **NVLink 160 GB/s** | PCIe ~31 GB/s |
| native FP16 | 없음 | **FP32의 2×** | 없음 |
| Unified Memory | Eager migration | **Page fault engine** | Page fault engine |
| Compute Preemption | Block 단위 | **Instruction 단위** | Instruction 단위 |

Pascal은 두 갈래로 분기했다. GP100은 HBM2, NVLink, native FP16, FP64를 갖춘 HPC/AI 전용 가속기다. GP102/GP104는 Maxwell의 Quadrant 구조를 계승해 소비자 시장을 겨냥했다.

다음 포스트에서는 Volta를 다룬다: Tensor Core의 등장, NVLink 2.0, 그리고 현대 AI 가속기 설계의 기반이 완성되는 과정이다.

---

## References

- NVIDIA. *Inside Pascal: NVIDIA's Newest Computing Platform*. NVIDIA Developer Blog, 2016. [Link](https://developer.nvidia.com/blog/inside-pascal/)
- NVIDIA. *NVIDIA Tesla P100 GPU Architecture Whitepaper*, 2016. [PDF](https://images.nvidia.com/content/pdf/tesla/whitepaper/pascal-architecture-whitepaper.pdf)
- NVIDIA. *Beyond GPU Memory Limits with Unified Memory on Pascal*. NVIDIA Developer Blog, 2016. [Link](https://developer.nvidia.com/blog/beyond-gpu-memory-limits-unified-memory-pascal/)
- NVIDIA. *Pascal Tuning Guide*. CUDA Toolkit Documentation. [Link](https://docs.nvidia.com/cuda/pascal-tuning-guide/)
- NVIDIA. *CUDA 8 Features Revealed*. NVIDIA Developer Blog, 2016. [Link](https://developer.nvidia.com/blog/parallelforall/cuda-8-features-revealed/)
- NVIDIA. *Mixed-Precision Programming with CUDA 8*. NVIDIA Developer Blog, 2016. [Link](https://developer.nvidia.com/blog/mixed-precision-programming-cuda-8/)
