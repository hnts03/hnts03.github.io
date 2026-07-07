---
layout: post
title: "GPU 아키텍처 #4: Volta - Tensor Core와 독립 스레드 스케줄링"
subtitle: "GV100 SM 재설계, FP32/INT32 분리 실행, 독립 스레드 스케줄링, WMMA API"
tags: [GPU, Architecture, CUDA, NVIDIA, Volta, TensorCore, Computer-Architecture]
lang: kr
translation-url: /2026-07-07-gpu-arch-4-volta-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 |
|:--:|:---|
| 1 | [GPU의 출발과 SIMT의 탄생 - Tesla, Fermi](/2026-04-12-gpu-arch-1-tesla-fermi-kr/) |
| 2 | [Kepler와 Maxwell - 효율성의 탐구](/2026-07-06-gpu-arch-2-kepler-maxwell-kr/) |
| 3 | [Pascal - 16nm, HBM2, NVLink](/2026-07-07-gpu-arch-3-pascal-kr/) |
| **4** | **Volta - Tensor Core와 독립 스레드 스케줄링** |
| 5 | [Turing - RT Core와 2세대 Tensor Core](/2026-07-07-gpu-arch-5-turing-kr/) |
| 6 | GPU 메모리 시스템과 최적화 |

---

## Pascal이 드러낸 한계

Pascal GP100은 HBM2(732 GB/s)와 NVLink(160 GB/s)로 메모리 병목을 완화했고, native FP16으로 딥러닝 추론 처리량을 FP32의 2배로 끌어올렸다. 그러나 2016년 이후 AI 워크로드의 핵심 연산이 무엇인지 분명해졌다. **행렬 곱셈(GEMM, General Matrix Multiply)** 이다.

Transformer의 Multi-Head Attention, 합성곱 신경망의 im2col 변환, 완전 연결 레이어 모두 `D = A × B + C` 형태의 행렬 곱으로 귀결된다. Pascal의 FP32 CUDA Core는 클럭당 1개의 스칼라 FMA(Fused Multiply-Add)를 처리한다. FP16 half2 벡터 연산으로 처리량을 2배로 높여도, 연산 단위는 원소 하나씩의 곱셈이다.

`M × K` 행렬과 `K × N` 행렬을 곱할 때, 결과 행렬의 각 원소는 K번의 FMA가 필요하다. 이 K번의 루프를 하드웨어로 옮기는 것이 Volta(GV100, 2017)의 핵심 설계 목표였다.

---

## Tensor Core: 행렬 연산 전용 가속

### 4×4 MMA 연산 원리

**Tensor Core**는 4×4 행렬 곱셈-누산(MMA, Matrix Multiply-Accumulate)을 단일 클럭에 수행하는 전용 연산 유닛이다.

```
D[4×4] = A[4×4] × B[4×4] + C[4×4]

입력:  A, B (FP16 4×4 행렬)
누산:  C    (FP32 4×4 행렬)
출력:  D    (FP32 4×4 행렬)
```

4×4 행렬 곱의 각 원소는 크기-4 벡터 내적이다. 출력 원소 16개 × 내적 4회 FMA = 클럭당 64 FP16 FMA = **128 FP16 FLOPS**다.

CUDA Core의 FP16 FMA가 클럭당 2 FLOPS(곱셈 1 + 덧셈 1)인 것과 비교하면, Tensor Core 1개의 처리량은 64배다.

GV100 SM에는 Tensor Core가 8개다. SM당 클럭당 FP16 처리량:

| 유닛 | SM당 수량 | 클럭당 FP16 FLOPS |
|:---|:---:|:---:|
| FP32 CUDA Core (half2 기준) | 64 | 128 |
| Tensor Core | 8 | **1,024** |

GV100 전체(80 SM, 1.53 GHz 부스트 클럭) 기준:

```
CUDA Core FP16:  128 × 80 × 1.53 GHz = 15.7 TFLOPS
Tensor Core FP16: 1,024 × 80 × 1.53 GHz = 125.3 TFLOPS
```

Pascal P100의 native FP16이 21.2 TFLOPS였던 것과 비교하면 약 **6배** 향상이다.

![Pascal P100 vs Volta V100 처리량 비교 (SXM2)](/assets/img/posts/gpu-arch-4/perf-compare.png)

### 혼합 정밀도 데이터 타입

첫 세대 Tensor Core(GV100, Compute Capability 7.0)가 지원하는 데이터 타입 조합:

| 입력 (A, B) | 누산 (C, D) |
|:---:|:---:|
| FP16 | FP32 |
| FP16 | FP16 |

FP32 누산을 사용하면 중간 계산의 수치 범위가 FP16보다 넓어 언더플로우와 오버플로우 위험이 줄어든다. 이것이 **혼합 정밀도 학습(Mixed-Precision Training)** 의 하드웨어 기반이다. Gradient가 FP16 범위를 벗어나지 않도록 Loss Scaling을 적용하고, 가중치 업데이트는 FP32 Master Copy에 누산한다. cuDNN과 cuBLAS는 FP16 행렬 크기가 16의 배수일 때 자동으로 Tensor Core를 사용한다.

---

## GV100 SM: 4 Sub-core 구조

### Sub-core 분할

Pascal GP100 SM은 2개의 Processing Block으로 구성됐다. 각 블록에 Warp Scheduler 1개(Dispatch Unit **2개**, dual-issue)와 32 FP32, 16 FP64 코어가 있었다.

Volta GV100은 이를 4개의 **Sub-core**로 재편했다. 각 Sub-core에 Warp Scheduler 1개(Dispatch Unit **1개**, single-issue)와 연산 유닛이 균등 배분된다.

```
GV100 SM (4 Sub-core)
┌──────────────────────────────────────────────────────┐
│  Sub-core 0                                          │
│  ┌──────────────────────────────────────────────┐    │
│  │ L0 Instruction Cache (신규)                  │    │
│  │ Warp Scheduler  │  Dispatch Unit (×1)        │    │
│  ├─────────────────┼──────────────────────────  ┤    │
│  │  16 FP32 Cores  │  16 INT32 Cores (신규)     │    │
│  │   8 FP64 Cores  │   2 Tensor Cores (신규)    │    │
│  │   8 LD/ST Units │   4 SFU                    │    │
│  └─────────────────┴──────────────────────────  ┘    │
├──────────────────────────────────────────────────────┤
│  Sub-core 1  (동일 구성)                             │
├──────────────────────────────────────────────────────┤
│  Sub-core 2  (동일 구성)                             │
├──────────────────────────────────────────────────────┤
│  Sub-core 3  (동일 구성)                             │
├──────────────────────────────────────────────────────┤
│  Unified L1 / Shared Memory  128KB                   │
│  Register File  256KB (65,536 × 32-bit)              │
└──────────────────────────────────────────────────────┘

SM 합산: FP32 64개, INT32 64개, FP64 32개, Tensor Core 8개,
         LD/ST 32개, SFU 16개
```

### Pascal GP100과의 구조 비교

| | Pascal GP100 | Volta GV100 |
|:---|:---:|:---:|
| 구성 단위 | Processing Block × 2 | **Sub-core × 4** |
| FP32 / SM | 64 | 64 |
| FP64 / SM | 32 | 32 |
| INT32 / SM | FP32와 공용 | **64 (전용)** |
| Tensor Core / SM | 없음 | **8** |
| Warp Scheduler / SM | 2 | **4** |
| Dispatch Unit / Scheduler | 2 (dual-issue) | 1 (single-issue) |
| LD/ST Units / SM | 16 | **32** |
| SFU / SM | 8 | **16** |
| L0 Instruction Cache | 없음 | **Sub-core당 1개** |
| L1 + Shared Memory | 64KB + 64KB (분리) | **Unified 128KB** |
| Shared Memory 최대 | 64KB | **96KB** |

총 dispatch 슬롯 수는 Pascal GP100(2 × 2 = 4)과 Volta GV100(4 × 1 = 4) 모두 SM당 4로 동일하다. Volta는 이를 4개의 독립 Sub-core에 분산해 스레드별 유연한 스케줄링의 기반을 만들었다.

### FP32/INT32 분리 실행

Pascal까지는 FP32 실행 유닛이 INT32 연산도 담당했다. 루프 카운터 증가(`i++`)나 배열 인덱스 계산 같은 정수 연산이 FP32 파이프라인과 슬롯을 공유했다.

GV100은 **INT32 전용 실행 유닛**을 별도로 두었다. FP32 연산과 INT32 연산이 **동시에** 실행된다.

```
Pascal GP100: FP32와 INT32가 같은 유닛 사용
Cycle 1: FP32 FMA(A[i] × B[i] + C)   →  INT32 IADD(i++) 대기
Cycle 2: INT32 IADD 완료              →  FP32 대기

Volta GV100: FP32와 INT32 병렬 실행
Cycle 1: FP32 FMA(A[i] × B[i] + C)   ║  INT32 IADD(i++)
Cycle 2: FP32 FMA(A[i+1] × B[i+1])   ║  INT32 CMP / BRANCH
```

GEMM 내부 K-loop처럼 FP 연산과 정수 루프 제어가 혼재하는 패턴에서 실질적인 IPC 향상이 발생한다.

### L0 Instruction Cache

Pascal까지는 SM 전체가 L1 Instruction Cache 하나를 공유했다. Volta는 각 Sub-core에 **L0 Instruction Cache**를 추가했다. 최근에 디코딩된 명령어를 Sub-core별로 캐시해 L1 접근 횟수를 줄인다. 타이트한 루프에서 매 사이클 instruction fetch 없이 L0에서 직접 공급된다.

### Unified L1/Shared Memory

Pascal GP100은 L1(+Texture Cache)와 Shared Memory가 각각 전용 뱅크를 사용했다. Volta는 이를 **128KB 통합 온칩 메모리**로 합쳤다. 분할 비율을 커널마다 설정할 수 있다.

```
Shared Memory  │  L1 Cache
───────────────────────────
      0KB      │  128KB
     32KB      │   96KB
     64KB      │   64KB
     96KB      │   32KB   ← 최대 Shared Memory
```

Pascal의 최대 Shared Memory가 64KB였던 것과 비교해, 96KB까지 확장 가능하다. 대형 행렬 타일링(tiling) GEMM 커널에서 L2 및 HBM2 접근 횟수를 줄이는 데 직접 활용된다.

```cuda
cudaFuncSetAttribute(my_kernel,
    cudaFuncAttributeMaxDynamicSharedMemorySize,
    96 * 1024);
```

---

## 독립 스레드 스케줄링

Volta에서 가장 중요한 마이크로아키텍처 변화다.

### Pascal까지의 SIMT 실행 모델

Tesla 이후 Pascal까지 Warp의 32개 스레드는 단일 Program Counter를 공유했다. 분기 발생 시 컴파일러가 삽입한 재수렴 지점(IPDOM, Immediate Post-Dominator)까지 Active Mask로 각 경로를 순차 실행하고, 재수렴 지점에서 32개 스레드가 다시 합류했다.

이 모델의 구조적 한계: **Warp 내 스레드 간 세밀한 동기화가 불가능**하다. 32개 스레드가 항상 함께 진행하거나 함께 멈추기 때문에, Warp 내 Producer-Consumer 구조를 만들 수 없다.

Pascal 이전 코드 중 일부는 같은 Warp 내 스레드들이 lock-step으로 실행된다는 사실을 암묵적으로 활용했다. `__shared__` 메모리에 쓴 뒤 `__syncthreads()` 없이 인접 스레드의 값을 읽는 코드가 우연히 동작한 경우다. 이는 정의되지 않은 동작(undefined behavior)이었다.

### Volta: Thread 단위 PC와 Call Stack

Volta는 각 스레드에 독립적인 **Program Counter**와 **Call Stack**을 부여했다.

```
Pascal: Warp 단위 단일 PC
┌─────────────────────────────┐
│  Warp PC                    │
│  T0 T1 T2 ... T31           │
│  모두 같은 명령어 실행       │
└─────────────────────────────┘
         │ 분기 발생
    ┌────┴────┐
  Path A   Path B  (순차 실행)
    └────┬────┘
      재수렴 (IPDOM)

Volta: Thread 단위 PC
┌─────────────────────────────┐
│  T0:  PC_0,  Stack_0        │
│  T1:  PC_1,  Stack_1        │
│  ...                        │
│  T31: PC_31, Stack_31       │
│                             │
│  수렴 구간: lock-step 묶음  │
│  발산 구간: 독립 진행       │
└─────────────────────────────┘
```

수렴 구간(convergent section)에서는 여전히 32개 스레드를 lock-step으로 묶어 실행 효율을 유지한다. 발산 구간에서는 각 스레드가 독립적으로 진행할 수 있다. Pascal의 고정된 컴파일러 삽입 IPDOM 방식과 달리, Volta 스케줄러는 **런타임에 수렴 여부를 동적으로 감지**한다. 같은 PC에 도달한 스레드들을 자동으로 묶어 lock-step으로 전환한다.

독립 스레드 스케줄링의 실질적 이점: 메모리 접근으로 stall된 스레드와 실행 가능한 스레드가 같은 Warp에 있을 때, 실행 가능한 스레드가 stall 없이 진행할 수 있다. Pascal에서는 Warp 전체가 대기해야 했다.

### `__syncwarp()` 도입

독립 스레드 스케줄링으로 인해, Pascal에서 암묵적 lock-step에 의존하던 코드는 Volta에서 오동작할 수 있다. CUDA 9.0은 Warp 내 명시적 동기화를 위해 `__syncwarp(mask)`를 도입했다.

```cuda
// ❌ Pascal에서 우연히 작동하던 코드 (Volta에서 오동작 가능)
shmem[threadIdx.x] = val;
// lock-step을 암묵적으로 가정: Volta에서는 보장되지 않음
other = shmem[(threadIdx.x + 1) % 32];

// ✅ Volta 안전 코드
shmem[threadIdx.x] = val;
__syncwarp();          // Warp 내 모든 쓰기 완료 대기 + 메모리 펜스
other = shmem[(threadIdx.x + 1) % 32];
```

`mask` 파라미터(uint32_t 비트마스크)로 동기화에 참여할 스레드를 지정한다. `__syncwarp()`는 `__syncwarp(0xffffffff)`와 동일하다.

### Warp 내 Producer-Consumer 패턴

독립 스레드 스케줄링으로 Pascal에서 불가능했던 패턴이 가능해진다.

```cuda
// Volta에서 가능: Warp 내 Producer-Consumer
__shared__ float buf[16];

if (threadIdx.x < 16) {
    // 스레드 0~15: producer
    buf[threadIdx.x] = heavy_compute(threadIdx.x);
    __syncwarp(0x0000ffff);   // producer 16개 완료 신호
} else {
    __syncwarp(0xffff0000);   // consumer도 fence에 참여
    float val = buf[threadIdx.x - 16];
    consume(val);
}
```

Warp 내 두 그룹이 비대칭 작업을 처리하고 경계에서만 동기화하는 구조다. Pascal에서 이 패턴은 데드락을 일으킬 수 있었다.

---

## NVLink 2.0과 메모리 시스템

### NVLink 2.0

| | NVLink 1.0 (GP100) | NVLink 2.0 (GV100) |
|:---|:---:|:---:|
| 링크 수 / GPU | 4 | **6** |
| 링크당 양방향 대역폭 | 20 GB/s | **25 GB/s** |
| 총 양방향 대역폭 | 160 GB/s | **300 GB/s** |
| NVSwitch 지원 | 없음 | **있음** |

**NVSwitch**는 V100 기반 DGX-2(2018)에 도입된 GPU 간 스위치 ASIC이다. DGX-2는 16개의 V100을 12개의 NVSwitch로 완전 연결(all-to-all)한다. 어떤 GPU 쌍도 300 GB/s로 직접 통신한다. DGX-1(P100 기반)의 ring 토폴로지에서 AllReduce 시 일부 GPU가 중계 역할을 해야 했던 것과 달리, 16 GPU가 모두 직접 통신한다.

### HBM2와 L2

| | Pascal P100 SXM2 | Volta V100 SXM2 |
|:---|:---:|:---:|
| VRAM | 16 GB | 16 GB / **32 GB** |
| 버스 폭 | 4096-bit | 4096-bit |
| HBM2 대역폭 | 732 GB/s | **900 GB/s** |
| L2 Cache | 4 MB | **6 MB** |

Tensor Core 투입으로 연산 처리량이 급증하면 메모리 대역폭이 새로운 병목이 된다. HBM2 대역폭 23% 향상과 L2 1.5배 확장이 메모리 서브시스템을 함께 보강한다.

---

## CUDA 9.0: Volta와 함께 출시된 소프트웨어

### Cooperative Groups

기존 `__syncthreads()`는 Thread Block 전체를 동기화했다. **Cooperative Groups**(CUDA 9.0)는 동기화 범위를 명시적으로 지정하는 API다.

```cuda
#include <cooperative_groups.h>
namespace cg = cooperative_groups;

__global__ void warp_reduce(float *in, float *out) {
    auto block = cg::this_thread_block();
    
    // Warp 크기 Tile 생성 (32개 스레드)
    auto warp = cg::tiled_partition<32>(block);
    
    float val = in[blockIdx.x * blockDim.x + threadIdx.x];
    
    // Warp 내 reduction
    for (int i = warp.size() / 2; i > 0; i /= 2)
        val += warp.shfl_down(val, i);
    
    if (warp.thread_rank() == 0)
        atomicAdd(out, val);
}
```

`tiled_partition<N>()`은 N개 스레드 Tile을 생성한다(N은 2의 거듭제곱, 32 이하). Tile 내에서 `sync()`, `shfl_*()`, `vote()`, `match_*()` 등을 사용할 수 있다.

**Grid-level 동기화:**

```cuda
__global__ void two_phase_kernel(float *data) {
    auto grid = cg::this_grid();
    
    phase_one(data);
    grid.sync();       // 모든 Thread Block 동기화
    phase_two(data);   // 1단계 결과에 의존
}

// 실행 시: cudaLaunchCooperativeKernel() 사용
// Grid의 모든 Block이 동시에 SM에 상주해야 함
```

`grid.sync()`를 사용하려면 Grid 크기가 `SM 수 × SM당 최대 Block 수` 이하여야 한다.

### WMMA API: Tensor Core 직접 접근

CUDA 9.0의 `nvcuda::wmma` 네임스페이스는 Warp 수준의 Tensor Core 접근 API를 제공한다. Warp 전체(32 스레드)가 협력해 16×16×16 FP16 행렬 연산을 수행한다.

```cuda
#include <mma.h>
using namespace nvcuda::wmma;

__global__ void wmma_matmul(half *A, half *B, float *C,
                             int M, int N, int K) {
    // Warp당 16×16 출력 타일 담당
    int warpRow = (blockIdx.y * blockDim.y + threadIdx.y);
    int warpCol = (blockIdx.x * blockDim.x + threadIdx.x) / warpSize;

    fragment<matrix_a, 16, 16, 16, half, row_major> a_frag;
    fragment<matrix_b, 16, 16, 16, half, col_major> b_frag;
    fragment<accumulator, 16, 16, 16, float>         acc;

    fill_fragment(acc, 0.0f);

    for (int k = 0; k < K; k += 16) {
        load_matrix_sync(a_frag, A + warpRow * 16 * K + k, K);
        load_matrix_sync(b_frag, B + k * N + warpCol * 16,  N);
        mma_sync(acc, a_frag, b_frag, acc);  // Tensor Core 발동
    }

    store_matrix_sync(C + warpRow * 16 * N + warpCol * 16,
                      acc, N, mem_row_major);
}
```

`mma_sync()` 실행 시, Warp 내 32개 스레드가 Fragment의 조각을 레지스터에 분산 보유하고 Tensor Core가 이를 조합해 4×4 MMA를 반복 수행한다. 16×16×16 WMMA는 내부적으로 4×4 Tensor Core 연산의 조합으로 구현된다.

프로덕션에서는 cuBLAS `cublasGemmEx()` 또는 cuDNN이 자동으로 Tensor Core를 활용한다. 행렬 크기가 16의 배수이고 FP16 타입일 때 Tensor Core가 자동 활성화된다.

---

## 정리

| | Pascal GP100 | Volta GV100 |
|:---|:---:|:---:|
| 공정 | 16nm FinFET | **12nm FFN** |
| 트랜지스터 | 15.3B | **21.1B** |
| 다이 크기 | 610mm² | 815mm² |
| SM 수 | 60 | **80** |
| SM 구성 단위 | Processing Block × 2 | **Sub-core × 4** |
| Tensor Core / SM | 없음 | **8** |
| INT32 실행 파이프 | FP32와 공용 | **전용 (FP32와 병렬)** |
| FP16 처리량 (V100) | 21.2 TFLOPS | **125.3 TFLOPS** |
| FP32 처리량 (V100) | 10.6 TFLOPS | 15.7 TFLOPS |
| FP64 처리량 (V100) | 5.3 TFLOPS | 7.8 TFLOPS |
| LD/ST / SM | 16 | **32** |
| L0 Instruction Cache | 없음 | **있음 (Sub-core당)** |
| Shared Memory 최대 | 64KB | **96KB** |
| HBM2 대역폭 | 732 GB/s | **900 GB/s** |
| L2 Cache | 4MB | **6MB** |
| NVLink | 1.0, 160 GB/s | **2.0, 300 GB/s** |
| 스레드 스케줄링 | Warp 단위 PC | **Thread 단위 PC** |
| TDP (SXM2) | 300W | 300W |

Volta의 변화는 두 방향으로 요약된다. Tensor Core와 FP32/INT32 분리 실행은 기존 CUDA Core 파이프라인의 연산 처리량을 확장하는 하드웨어 추가다. 독립 스레드 스케줄링은 Tesla 이후 이어온 SIMT 모델의 구조적 제약을 해소하는 마이크로아키텍처 변화다. 이 두 방향은 이후 Turing과 Ampere가 각각 RT Core/INT8 Tensor Core와 3세대 Tensor Core로 확장하는 설계 기반이 된다.

다음 포스트에서는 Turing을 다룬다: RT Core의 등장, INT8/INT4 Tensor Core, 그리고 소비자 GPU에서의 AI 가속 시작.

---

## References

- NVIDIA. *NVIDIA Tesla V100 GPU Architecture Whitepaper*. 2017. [PDF](https://images.nvidia.com/content/volta-architecture/pdf/volta-architecture-whitepaper.pdf)
- NVIDIA. *Inside Volta: The World's Most Advanced Data Center GPU*. NVIDIA Developer Blog, 2017.
- NVIDIA. *Programming Tensor Cores in CUDA 9*. NVIDIA Developer Blog, 2017.
- NVIDIA. *CUDA 9 Features Revealed: Volta, Cooperative Groups and More*. NVIDIA Developer Blog, 2017.
- Jia, Z. et al. *Dissecting the NVIDIA Volta GPU Architecture via Microbenchmarking*. arXiv:1804.06826, 2018.
- NVIDIA. *CUDA C++ Best Practices Guide*. Developer Documentation.
