---
layout: post
title: "GPU 아키텍처 #6: Ampere - Sparsity 가속과 MIG"
subtitle: "3세대 Tensor Core의 2:4 구조적 희소성, TF32/BF16, A100 MIG, cp.async 파이프라이닝"
tags: [GPU, Architecture, CUDA, NVIDIA, Ampere, TensorCore, Computer-Architecture]
lang: kr
translation-url: /2026-07-07-gpu-arch-6-ampere-en/
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
| 5 | [Turing - RT Core와 2세대 Tensor Core](/2026-07-07-gpu-arch-5-turing-kr/) |
| **6** | **Ampere - Sparsity 가속과 MIG** |
| 7 | GPU 메모리 시스템과 최적화 |

---

## Turing 이후의 과제

Turing은 소비자 GPU에 Tensor Core와 RT Core를 처음 가져왔다. 그러나 데이터센터 시장에서는 Volta V100이 그대로 유지됐다. 2018년부터 2020년 사이 LLM 연구가 급격히 커졌다. GPT-2(2019), GPT-3(2020) 수준의 모델을 학습하려면 이전과 다른 규모의 가속이 필요했다.

동시에 AI 추론 압축 연구가 성숙했다. 모델 가중치의 상당 비율을 0으로 만들어도 정확도 손실이 미미하다는 사실이 실험으로 검증됐다. 하드웨어가 이 희소성(sparsity)을 직접 가속할 수 있다면, 추론 처리량을 두 배로 늘릴 수 있었다.

Ampere(2020)는 세 가지로 이 문제를 공략했다. **3세대 Tensor Core**의 2:4 구조적 희소성 가속, **TF32**와 **BF16**이라는 새 정밀도 형식, A100에서 하드웨어로 GPU를 분리하는 **MIG(Multi-Instance GPU)**.

---

## 다이 스펙: 두 갈래의 Ampere

Ampere는 공정과 타깃 시장에 따라 두 개의 서로 다른 다이로 나뉜다.

| | Turing TU102 | Ampere GA100 (A100) | Ampere GA102 (RTX 30xx) |
|:---|:---:|:---:|:---:|
| 공정 | TSMC 12nm | **TSMC 7nm** | **Samsung 8nm** |
| 트랜지스터 | 18.6B | **54.2B** | **28.3B** |
| 다이 면적 | 754mm² | **826mm²** | **628mm²** |
| 전체 SM 수 | 72 | 128 (A100: 108 활성) | 84 (RTX 3090: 82 활성) |
| FP32/SM | 64 | **64** | **128** |
| FP64/SM | 없음 | **32** | 1 (형식적) |
| Tensor Core | 2세대 | **3세대** | **3세대** |
| 대표 제품 | RTX 2080 Ti | A100 SXM4 | RTX 3090 |
| 포지셔닝 | 소비자/추론 | HPC/대규모 AI | 소비자/게임/AI |

GA100은 TSMC 7nm로 공정 세대가 올라갔다. GA102는 수율 확보를 위해 Samsung 8nm를 택했다. Pascal과 Turing이 각각 GP100(고성능)과 GP102/TU102(소비자)로 나뉜 것처럼, Ampere도 두 갈래로 분기했다.

---

## 3세대 Tensor Core

### TF32: 코드 변경 없는 가속

**TF32(TensorFloat-32)**는 Ampere에서 처음 도입된 19비트 데이터 형식이다.

```
FP32 (32비트):  부호 1 | 지수 8 | 가수 23
TF32 (19비트):  부호 1 | 지수 8 | 가수 10   ← FP32와 지수 범위 동일
FP16 (16비트):  부호 1 | 지수 5 | 가수 10
BF16 (16비트):  부호 1 | 지수 8 | 가수 7
```

TF32는 FP32와 동일한 지수 범위(오버플로/언더플로 없음)를 유지하면서, 가수를 10비트로 줄여 FP16 수준의 정밀도를 갖는다. cuBLAS와 cuDNN은 A100에서 TC GEMM에 TF32를 기본으로 사용한다. FP32로 작성된 기존 학습 코드를 수정하지 않아도 A100에서 자동으로 TF32 가속이 적용된다.

```bash
# TF32 비활성화 (정밀도 검증 목적)
NVIDIA_TF32_OVERRIDE=0 python train.py
```

### BF16 Tensor Core

**BF16(Brain Float 16)**은 Google Brain에서 제안한 형식이다. FP32와 동일한 8비트 지수를 유지하므로 FP16의 지수 오버플로 문제가 없다. 분산 학습에서 gradient의 dynamic range가 넓어도 안전하다. Turing은 BF16을 CUDA Core에서 소프트웨어로만 처리했다. Ampere는 BF16을 Tensor Core에 직접 통합했다.

### FP64 Tensor Core (A100 전용)

GA100(A100)은 **FP64 Tensor Core**를 처음 도입했다. FP64 GEMM을 전용 TC 회로에서 처리해, FP64 CUDA Core 단독 처리 대비 2배 처리량을 얻는다.

| 정밀도 | A100 SXM4 Dense | V100 SXM2 |
|:---|---:|---:|
| FP64 CUDA Core | 9.7 TFLOPS | 7.8 TFLOPS |
| FP64 Tensor Core | **19.5 TFLOPS** | 없음 |

과학 시뮬레이션, 기후 모델링 등 FP64 정밀도가 필수인 HPC 워크로드가 주요 대상이다.

### 2:4 구조적 희소성: Sparsity 가속

3세대 Tensor Core의 가장 독창적인 추가는 **2:4 구조적 희소성(2:4 Structured Sparsity)**이다. 연속된 4개의 값 중 정확히 2개가 0인 패턴을 하드웨어가 직접 인식하고 건너뛴다.

```
원래 가중치 행 (8개 값):
  [0.3, 0.0, -0.5, 0.0, 0.8, 0.0, 0.2, 0.0]
      ↑    ↑                   ↑        ↑ (0으로 고정)

2:4 패턴 압축 저장:
  값:    [0.3, -0.5,  0.8,  0.2]        (50% 압축)
  인덱스: [0, 2,      0, 2]             (4-그룹 내 위치, 2비트씩)
```

추론 시 Tensor Core는 압축 값과 인덱스를 함께 로드해, 0 곱셈을 건너뛰며 동일한 결과를 생성한다. 연산량이 절반으로 줄면서 처리량이 2배가 된다.

희소성 처리 흐름:

```
학습 (sparsity 적용):
  일반 FP32/FP16 학습 → ASP 라이브러리로 2:4 패턴 pruning → fine-tuning → 정확도 복원

추론 (sparse inference):
  압축 가중치 로드 → Sparse Tensor Core가 dense output 생성 → 2× 처리량
```

실제로 ResNet-50, BERT, GPT 등 주요 모델에서 2:4 sparsity를 적용해도 정확도 손실이 0.5% 미만으로 보고됐다.

### 처리량 비교

![A100 SXM4 Tensor Core 처리량: Dense vs 2:4 Sparse](/assets/img/posts/gpu-arch-6/tc-throughput.png)

| 정밀도 | Turing RTX 2080 Ti | A100 Dense | A100 2:4 Sparse |
|:---|---:|---:|---:|
| FP16 TC | 107.9 TFLOPS | 312 TFLOPS | 624 TFLOPS |
| BF16 TC | 없음 | 312 TFLOPS | 624 TFLOPS |
| TF32 TC | 없음 | 156 TFLOPS | 312 TFLOPS |
| INT8 TC | 215 TOPS | 624 TOPS | 1,248 TOPS |
| FP64 TC | 없음 | 19.5 TFLOPS | - |

---

## Ampere SM 구조

### GA100과 GA102의 갈림

두 다이는 동일한 Tensor Core 세대를 쓰지만 SM 구성이 다르다.

```
GA100 Sub-core (A100)                  GA102 Sub-core (RTX 3090)
─────────────────────────────          ──────────────────────────────────
Warp Scheduler                         Warp Scheduler
Dispatch Unit ×2                       Dispatch Unit ×2
16 FP32           (전통)               16 FP32           (전통)
 8 FP64           (HPC용)              16 FP32/INT32     ← 이중 모드 (신규)
16 INT32          (별도)               [FP64 없음]
 1 TC (3세대)                           1 TC (3세대)
 8 LD/ST   4 SFU                        8 LD/ST   4 SFU

SM 합계 (4 Sub-core):                  SM 합계 (4 Sub-core):
  64 FP32 + 32 FP64 + 64 INT32           128 FP32 (+ 선택적 INT32) + 미미한 FP64
```

GA102의 핵심 변화는 INT32 파이프라인이 FP32도 실행할 수 있게 된 것이다. 클록당 FP32 연산이 Turing TU102의 2배다. 단, FP32와 INT32를 동시에 실행할 수는 없다. 한 사이클에 FP32 전용 64개 + FP32/INT32 듀얼 64개, 총 128개 FP32 연산이 가능하다.

### Volta/Turing/Ampere 비교

| 항목 | Volta GV100 | Turing TU102 | Ampere GA100 | Ampere GA102 |
|:---|:---:|:---:|:---:|:---:|
| FP32/SM | 64 | 64 | 64 | **128** |
| FP64/SM | 32 | 없음 | **32** | 1 |
| TC 세대 | 1세대 | 2세대 | **3세대** | **3세대** |
| TC 정밀도 | FP16 | FP16/INT8/4 | +TF32/BF16/**FP64 TC** | +TF32/BF16 |
| 2:4 Sparsity | 없음 | 없음 | **있음** | **있음** |
| RT Core | 없음 | 1세대 | **2세대** | **2세대** |
| Unified L1+Shared | 128KB | 96KB | **192KB** | 128KB |
| 최대 Shared Memory | 96KB | 64KB | **164KB** | 100KB |

GA100은 Unified L1+Shared를 192KB까지 늘렸다. 대형 행렬 연산에서 타일을 Shared Memory에 최대한 담을수록 전역 메모리 접근이 줄어들기 때문이다.

---

## MIG: Multi-Instance GPU

**MIG(Multi-Instance GPU)**는 A100 전용 기능이다. 하나의 물리 GPU를 최대 7개의 독립적인 GPU 인스턴스로 분리한다.

```
A100 SXM4 (108 SM 전체)
┌─────────────────────────────────────────────────────────┐
│  GPC 0 (14 SM) │ GPC 1 (14 SM) │ ... │ GPC 7 (14 SM)  │
│  L2 슬라이스   │ L2 슬라이스   │     │ L2 슬라이스    │
│  HBM2e 파티션  │ HBM2e 파티션  │     │ HBM2e 파티션   │
└─────────────────────────────────────────────────────────┘

MIG 7개 인스턴스 (각 1/7 A100):
  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
  │ 14SM │ │ 14SM │ │ 14SM │ │ 14SM │ │ 14SM │ │ 14SM │ │ 14SM │
  │  5GB │ │  5GB │ │  5GB │ │  5GB │ │  5GB │ │  5GB │ │  5GB │
  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
  각 인스턴스: 독립 SM 집합 + 전용 L2 캐시 슬라이스 + HBM 대역폭 파티션
```

MIG의 격리 수준:
- SM: 각 인스턴스는 자신에게 할당된 SM만 사용한다.
- L2 캐시: L2를 슬라이스로 분할해 인스턴스 간 캐시 간섭 없음.
- 메모리 대역폭: HBM2e 대역폭도 파티션 단위로 보장.
- 에러: 한 인스턴스의 오류가 다른 인스턴스에 영향을 주지 않음.

MIG 인스턴스 크기 옵션(A100 40GB 기준):

| 이름 | SM 수 | VRAM | 인스턴스 수 |
|:---|:---:|:---:|:---:|
| 1g.5gb | 14 | 5 GB | 최대 7 |
| 2g.10gb | 28 | 10 GB | 최대 3 |
| 3g.20gb | 42 | 20 GB | 최대 2 |
| 4g.20gb | 56 | 20 GB | 1 |
| 7g.40gb | 98 | 40 GB | 1 (전체) |

클라우드 서비스 제공자가 A100 하나를 여러 사용자에게 제공하거나, 소형 추론 작업을 다수 병렬 실행할 때 활용된다.

---

## NVLink 3.0과 메모리

### NVLink 3.0

| | Volta NVLink 2.0 | Turing (없음) | Ampere NVLink 3.0 |
|:---|:---:|:---:|:---:|
| 링크 수 (A100) | 6 | - | **12** |
| 링크당 대역폭 | 25 GB/s | - | **25 GB/s** |
| 총 대역폭 | 300 GB/s | - | **600 GB/s** |

DGX A100 시스템은 8개의 A100을 NVLink 3.0 + NVSwitch 2.0으로 연결한다. GPU당 NVLink 총 대역폭은 600 GB/s, NVSwitch 2.0은 스위치당 7.2 Tb/s 비전이선 대역폭을 제공한다.

### HBM2e와 GDDR6X

| 제품 | 메모리 | 대역폭 | VRAM |
|:---|:---:|---:|:---:|
| A100 SXM4 80GB | HBM2e | 2,000 GB/s | 80 GB |
| A100 SXM4 40GB | HBM2e | 1,555 GB/s | 40 GB |
| RTX 3090 | GDDR6X | 936 GB/s | 24 GB |
| RTX 3080 | GDDR6X | 760 GB/s | 10 GB |
| Turing V100 SXM2 (비교) | HBM2 | 900 GB/s | 32 GB |

A100 SXM4 80GB의 2 TB/s는 V100 대비 2.2배다. GDDR6X는 PAM4 시그널링으로 동일 클록에 두 배의 데이터를 전송한다.

### 확장된 L2 캐시

| 제품 | L2 캐시 |
|:---|---:|
| V100 (Volta) | 6 MB |
| RTX 2080 Ti (Turing) | 6 MB |
| A100 (Ampere GA100) | **40 MB** |
| RTX 3090 (Ampere GA102) | 6 MB |

A100의 40MB L2는 V100 대비 6.7배다. GEMM 타일, KV Cache(추론), 중간 활성값 등 자주 재사용되는 데이터를 L2에 유지해 HBM 접근을 줄인다.

---

## cp.async: 비동기 메모리 복사

Ampere는 `cp.async` PTX 명령어를 새로 도입했다. 전역 메모리에서 공유 메모리로 데이터를 복사할 때, 레지스터를 거치지 않고 직접 복사한다.

```
Turing 이전 (레지스터 경유):           Ampere cp.async (직접 복사):
Global Mem → 레지스터 → Shared Mem     Global Mem ──→ Shared Mem
(레지스터 소비, blocking)              (레지스터 없음, non-blocking)
```

`cp.async`는 비동기(non-blocking)다. 복사를 요청하고 즉시 다음 명령을 실행할 수 있다. 파이프라인을 명시적으로 구성해 현재 타일 계산과 다음 타일 데이터 적재를 겹친다.

```cuda
#include <cuda/pipeline>

__global__ void tiled_matmul(float *A, float *B, float *C, int N) {
    __shared__ float smA[2][TILE][TILE];
    __shared__ float smB[2][TILE][TILE];

    cuda::pipeline<cuda::thread_scope_thread> pipe = cuda::make_pipeline();
    int stage = 0;

    // 첫 타일 프리패치
    cuda::memcpy_async(smA[stage], A + ..., sizeof(smA[0]), pipe);
    cuda::memcpy_async(smB[stage], B + ..., sizeof(smB[0]), pipe);
    pipe.producer_commit();

    for (int tile = 0; tile < N / TILE; tile++) {
        int next = 1 - stage;
        // 다음 타일 비동기 적재 (현재 타일 계산 중 진행)
        cuda::memcpy_async(smA[next], A + ..., sizeof(smA[0]), pipe);
        cuda::memcpy_async(smB[next], B + ..., sizeof(smB[0]), pipe);
        pipe.producer_commit();

        pipe.consumer_wait();  // 현재 타일 적재 완료 대기
        __syncthreads();

        // 현재 타일로 TC GEMM 실행
        wmma::mma_sync(c_frag, a_frag, b_frag, c_frag);

        pipe.consumer_release();
        stage = next;
    }
}
```

CUTLASS 3.x와 cuBLAS 내부 커널은 이 패턴을 광범위하게 사용한다. Shared Memory I/O와 Tensor Core 연산이 겹쳐 SM이 idle 상태로 대기하는 시간이 줄어든다.

---

## 스케줄링 변화

Ampere의 스레드 스케줄링은 Volta/Turing과 동일하다. 독립 스레드 스케줄링(per-thread PC)을 그대로 유지한다. 새로운 요소는 비동기 파이프라인이다.

`cp.async`의 완료 여부는 커밋(commit)과 대기(wait) 명시적 API로 관리한다. 스케줄러는 이를 일반 메모리 의존성처럼 처리한다: 복사가 완료되기 전 해당 Shared Memory를 읽으면 정의되지 않은 동작이다. `pipe.consumer_wait()`는 완료 보장을 제공한다.

---

## CUDA 11과 소프트웨어

### CUDA 11 (2020)

CUDA 11.0은 Ampere GA100 지원으로 출시됐다.

- `cp.async` / `cuda::pipeline` API
- TF32, BF16 WMMA fragment 타입
- `cudaMemcpyAsync`의 내부 경로가 cp.async를 활용
- `cooperative_groups::memcpy_async()` (Cooperative Groups 기반 복사)
- MIG 관리: `nvidia-smi mig` 명령어 세트

### DLSS 2.0

DLSS 2.0은 Ampere와 함께 출시됐다. 1.0의 게임별 모델에서, 단일 범용 모델로 전환했다. 이전 프레임의 temporal 정보와 모션 벡터를 활용해 업스케일한다. Turing에서도 DLSS 2.0을 사용할 수 있다(Tensor Core가 있으면 동작).

### A100과 대규모 언어 모델

A100 SXM4 80GB는 GPT-3(175B 파라미터)를 FP16으로 단일 GPU에 올릴 수 없는 한계를 보여줬다(필요 VRAM: 약 350 GB). 텐서 병렬(Tensor Parallelism)과 파이프라인 병렬(Pipeline Parallelism)을 조합해 DGX A100 한 노드(8×A100) 또는 다중 노드에 분산하는 것이 표준 방법이 됐다. NVLink 3.0의 600 GB/s가 이 통신을 뒷받침한다.

---

## 정리

| | Turing TU102 | Ampere GA100 (A100) | Ampere GA102 (RTX 3090) |
|:---|:---:|:---:|:---:|
| 공정 | 12nm | **TSMC 7nm** | **Samsung 8nm** |
| FP32/SM | 64 | 64 | **128** |
| FP64 TC | 없음 | **있음 (19.5 TFLOPS)** | 없음 |
| TC 지원 정밀도 | FP16/INT8/INT4 | +**TF32/BF16/FP64 TC** | +TF32/BF16 |
| 2:4 Sparsity | 없음 | **있음 (2× 처리량)** | **있음** |
| MIG | 없음 | **최대 7 인스턴스** | 없음 |
| HBM2e/L2 | - | **2 TB/s / 40MB** | - |
| NVLink | 없음 | **NVLink 3.0 (600 GB/s)** | 없음 |
| cp.async | 없음 | **있음** | **있음** |

Ampere는 두 가지 방향을 동시에 열었다. GA100은 FP64 TC, MIG, NVLink 3.0, 40MB L2, 2 TB/s HBM2e로 대규모 AI 학습과 HPC의 교차점을 겨냥했다. GA102는 128 FP32/SM과 2:4 sparsity로 소비자 게임·AI 추론 처리량을 Turing 대비 크게 끌어올렸다. 2:4 구조적 희소성은 이후 Hopper, Blackwell에서도 계속 이어지는 TC 가속의 핵심 기법이 됐다.

다음 포스트에서는 GPU 메모리 시스템을 다룬다: 레지스터 파일, Shared Memory, L1/L2 캐시, DRAM 계층의 구조와 최적화 기법.

---

## References

- NVIDIA. *NVIDIA A100 GPU Architecture Whitepaper*, 2020. [PDF](https://images.nvidia.com/akamai/technology/ampere/NVIDIA-A100-GPU-Architecture-Whitepaper.pdf)
- NVIDIA. *NVIDIA Ampere Architecture In-Depth*. NVIDIA Developer Blog, 2020. [Link](https://developer.nvidia.com/blog/nvidia-ampere-architecture-in-depth/)
- NVIDIA. *Exploiting NVIDIA Ampere Structured Sparsity with cuSPARSELt*. NVIDIA Developer Blog, 2021.
- NVIDIA. *Programming Tensor Cores in CUDA 9*. NVIDIA Developer Blog, 2017.
- NVIDIA. *New Features in CUDA 11.1*. NVIDIA Developer Blog, 2020.
- NVIDIA. *Multi-Instance GPU User Guide*. NVIDIA Documentation.
- NVIDIA. *CUDA C++ Programming Guide: Asynchronous Data Copies*. NVIDIA Documentation.
