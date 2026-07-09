---
layout: post
title: "Grace CPU 아키텍처: NVIDIA의 첫 데이터센터 CPU"
subtitle: "Neoverse V2 72코어, LPDDR5X, NVLink-C2C로 구현한 CPU-GPU 통합"
tags: [CPU, Architecture, ARM, NVIDIA, Grace, HPC, NVLink, Computer-Architecture]
lang: kr
translation-url: /2026-07-08-cpu-arch-1-grace-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 1 | Grace - NVIDIA의 첫 데이터센터 CPU | ✅ |
| 2 | [Vera / Rubin - GTC 2025 공개 내용](/2026-07-09-cpu-arch-2-rubin-vera-kr/) | ✅ |
| 3 | (미정) | 🔲 |

---

## PCIe 병목

전통적인 서버 구성에서 CPU와 GPU는 PCIe로 연결된다. PCIe 5.0 x16 기준 대역폭은 약 64 GB/s다. GPU HBM 대역폭(H100 SXM5 기준 3.35 TB/s)과 비교하면 약 50분의 1 수준이다.

GPU가 CPU 메모리의 데이터를 처리하려면 명시적 복사 단계를 거쳐야 한다.

```
기존 PCIe 구성:
[CPU DRAM] --cudaMemcpy--> [GPU DRAM] --compute--> [GPU DRAM] --cudaMemcpy--> [CPU DRAM]
               ~64 GB/s                                              ~64 GB/s
```

LLM 추론 파이프라인에서 입력 토큰 전달, KV cache 관리, 결과 반환이 모두 이 병목을 통과한다. GPU 연산 자체보다 데이터 이동이 지연의 원인이 되는 상황이 발생한다.

NVIDIA는 이 문제를 인터커넥트 개선이 아닌 CPU 직접 설계로 해결했다. **Grace**는 NVIDIA의 첫 데이터센터 CPU다.

---

## 코어 구조: Neoverse V2

Grace CPU는 ARM **Neoverse V2** (코드명 Demeter) 마이크로아키텍처를 기반으로 한다. ARMv9.0-A ISA를 구현하며, 72코어를 TSMC 4N 공정 단일 다이에 집적한다.

### 명령 스케줄링 및 실행 파이프라인

Neoverse V2는 비순서 실행(OOO) 슈퍼스칼라 코어다. 프론트엔드에서 인출 및 디코드한 명령을 통합 발행 큐(Unified Reservation Station)에 적재하고, 준비된 명령을 각 실행 유닛에 비순서로 발행한다. 커밋은 재정렬 버퍼(ROB)를 통해 프로그램 순서대로 이루어진다.

```
Frontend                         Backend
┌─────────────┐                 ┌────────────────────────────────────┐
│ Fetch       │                 │     Unified Reservation Station    │
│ Decode      │────────────────>│                                    │
│ Rename      │                 │  INT ALU ×4   │  FP/SIMD/SVE2 ×2  │
│ Dispatch    │                 │  INT MUL ×2   │  Load/Store   ×2   │
└─────────────┘                 │  Branch   ×1  │                    │
                                └────────────┬───────────────────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  ROB (in-order  │
                                    │  commit)        │
                                    └─────────────────┘
```

| 실행 유닛 | 수량 |
|:---|:---:|
| 정수 ALU | 4 |
| 정수 곱셈 | 2 |
| 분기 처리 | 1 |
| FP/SIMD/SVE2 | 2 |
| 로드/스토어 | 2 |

분기 예측기는 TAGE 계열 다단계 예측기를 사용한다. 넓은 히스토리 테이블로 복잡한 분기 패턴을 커버한다.

**SVE2** (Scalable Vector Extension 2): Grace에서 256-bit 구현. FP16, BF16, INT8 등 AI 추론에서 자주 쓰이는 정밀도를 네이티브 벡터 연산으로 처리한다. BF16 누산 명령을 포함해 소규모 CPU 측 행렬 연산에도 활용된다.

### 캐시 계층

72개 코어는 온다이 메시(Mesh) 인터커넥트로 연결된다. 각 코어는 전용 L1/L2를 보유하고, 모든 코어가 공유 LLC(Last-Level Cache)에 접근한다.

```
[Core 0] [Core 1] [Core 2] ... [Core 11]
   │        │        │               │
  L2       L2       L2             L2
   │        │        │               │
   └────────┴────────┴───────────────┘
                     │
          [공유 L3 LLC (~114MB)]
                     │
         [LPDDR5X 메모리 컨트롤러]
```

| 레벨 | 크기 | 범위 |
|:---|:---:|:---:|
| L1 I-cache | 64KB | 코어당 |
| L1 D-cache | 64KB | 코어당 |
| L2 | 1MB | 코어당 (비공유) |
| L3 (공유 LLC) | ~114MB | 72코어 공유 |

L3를 114MB 대형으로 설계한 이유는 LLM 추론 시 여러 요청의 working set을 LLC에 수용해 DRAM 접근 횟수를 줄이기 위해서다.

---

## 메모리 서브시스템: LPDDR5X

서버 CPU는 통상 DDR5를 사용한다. Grace는 **LPDDR5X**를 채택했다. 원래 모바일 기기용으로 설계된 규격이지만, 고대역폭과 저전력이라는 특성이 AI 서버에 유리하다.

Grace CPU 한 다이의 메모리 대역폭은 약 **480 GB/s**다.

![대역폭 비교: CPU 메모리 / CPU-GPU 인터커넥트](/assets/img/posts/cpu-arch-1-grace/bandwidth-compare.png)

| CPU | 메모리 규격 | 메모리 대역폭 |
|:---|:---:|:---:|
| Intel Xeon Sapphire Rapids | DDR5-4800 8ch | ~307 GB/s |
| AMD EPYC Genoa | DDR5-4800 12ch | ~461 GB/s |
| **NVIDIA Grace** | **LPDDR5X** | **~480 GB/s** |
| Grace CPU Superchip (2다이) | LPDDR5X | ~960 GB/s |

LPDDR5X는 단위 전력당 대역폭(BW/W)이 DDR5보다 유리하다. AI 서버에서 메모리 서브시스템은 전체 소비전력의 상당 부분을 차지하는데, LPDDR5X는 이 부분에서 DDR5 대비 이점을 제공한다.

Grace CPU 한 다이에 탑재되는 LPDDR5X 용량은 96GB다. GH200에서 Grace 96GB + Hopper 80/96GB HBM3을 합산하면 단일 패키지에서 최대 192GB 메모리 공간을 확보할 수 있다.

---

## 패키지 통합: Monolithic Die와 Multi-Die 구성

Grace는 단일 다이(Monolithic Die) 설계다. AMD EPYC처럼 다수의 CCD를 연결한 chiplet 구조가 아니다. 72코어가 단일 실리콘 위에 집적돼 있고, 코어 간 일관성을 로컬 패브릭이 처리한다.

NVIDIA는 이 단일 Grace 다이를 두 가지 패키지로 제공한다.

### Grace CPU Superchip

두 개의 Grace 다이를 NVLink-C2C로 연결한 144코어 구성이다.

```
┌─────────────────────────────────────────────┐
│              Grace CPU Superchip            │
│  ┌───────────────┐       ┌───────────────┐  │
│  │  Grace Die 0  │       │  Grace Die 1  │  │
│  │  72코어        │◄─────►│  72코어        │  │
│  │  96GB LPDDR5X │       │  96GB LPDDR5X │  │
│  └───────────────┘       └───────────────┘  │
│            NVLink-C2C: 900 GB/s             │
└─────────────────────────────────────────────┘
              총 144코어, 192GB, ~960 GB/s
```

### GH200 Grace-Hopper Superchip

Grace CPU 한 다이와 Hopper GPU(H100 SXM5)를 동일 패키지에 집적한 구성이다. NVIDIA의 주력 AI 서버 구성 단위다.

```
┌──────────────────────────────────────────────────┐
│                  GH200 Superchip                 │
│  ┌────────────────┐          ┌─────────────────┐ │
│  │   Grace CPU    │          │   Hopper GPU    │ │
│  │   72코어        │◄────────►│   H100 SXM5     │ │
│  │   96GB LPDDR5X │          │   80/96GB HBM3  │ │
│  └────────────────┘          └─────────────────┘ │
│             NVLink-C2C: 900 GB/s (양방향)         │
└──────────────────────────────────────────────────┘
```

---

## NVLink-C2C

**NVLink-C2C** (Chip-to-Chip)는 동일 패키지 내 다이 간 연결을 위한 NVLink 변형이다. GPU 사이를 연결하는 표준 NVLink(NVLink 4.0/5.0)와 구분되며, 패키지 내 초단거리 SerDes 링크로 구현된다.

| 항목 | NVLink-C2C | PCIe 5.0 x16 |
|:---|:---:|:---:|
| 총 대역폭 | 900 GB/s | ~64 GB/s |
| 단방향 대역폭 | 450 GB/s | ~32 GB/s |
| 캐시 일관성 | 있음 | 없음 |
| 연결 범위 | 동일 패키지 내 | 시스템 버스 |

900 GB/s는 PCIe 5.0 x16 대비 약 14배다. 일반 NVLink 5.0(GPU 간, 1800 GB/s 양방향)보다는 낮지만, PCIe와 달리 하드웨어 캐시 일관성을 제공한다는 점이 핵심 차별점이다.

### NVL 랙 스케일 구성

여러 GH200을 NVLink Switch로 연결하면 단일 NVLink 도메인을 구성할 수 있다.

```
                NVLink Switch Fabric
         ┌──────────┬──────────┬──────────┐
         │          │          │          │
      GH200-0    GH200-1    GH200-2  ...GH200-31    (NVL32)
      ┌───────┐  ┌───────┐  ┌───────┐
      │Grace  │  │Grace  │  │Grace  │
      │+H100  │  │+H100  │  │+H100  │
      └───────┘  └───────┘  └───────┘
```

NVL32 구성에서는 32개 GH200의 모든 GPU가 서로의 HBM3과 Grace LPDDR5X에 직접 접근할 수 있다. NCCL은 이 토폴로지를 자동으로 감지하고 최적 통신 경로를 선택한다.

---

## GPU와의 연결 및 명령 체계

### 통합 가상 주소 공간

NVLink-C2C가 캐시 일관성을 제공하므로, Grace와 Hopper는 단일 가상 주소 공간을 공유한다.

```
기존 PCIe 시스템:
  CPU 주소 공간: [CPU DRAM 0x0000...]
  GPU 주소 공간: [GPU DRAM 0x0000...]  (별개 도메인)
  → 포인터 공유 불가. cudaMemcpy 필수

GH200 NVLink-C2C:
  통합 주소 공간: [Grace LPDDR5X | Hopper HBM3]
  → CPU ptr == GPU ptr. 포인터 직접 전달 가능
```

### CUDA 프로그래밍 모델 변화

| 동작 | PCIe 시스템 | GH200 (NVLink-C2C) |
|:---|:---|:---|
| CPU 메모리 - GPU 전달 | `cudaMemcpy` 필수 (~64 GB/s) | GPU가 직접 읽기 (~450 GB/s) |
| GPU 결과 - CPU 반환 | `cudaMemcpy` 필수 | CPU가 직접 읽기 |
| `cudaMallocManaged` | PCIe 대역폭 한계 | 풀 NVLink-C2C 대역폭 |
| 포인터 공유 | 불가 | 가능 |

`cudaMallocManaged()`로 할당한 메모리는 GH200에서 PCIe 병목 없이 CPU와 GPU 양쪽에서 네이티브 속도로 접근된다. 기존에 cudaMemcpy를 통해 스테이징 버퍼를 오가던 코드가 단순해진다.

### 캐시 일관성의 실질적 의미

GPU가 Grace LPDDR5X의 캐시 라인을 읽을 때 해당 라인이 Grace L3에 있으면 하드웨어가 일관성을 보장한다. GPU가 캐시 라인을 수정하면 Grace 캐시의 해당 라인이 자동으로 무효화된다. 소프트웨어가 캐시 플러시나 `__threadfence_system()` 을 명시적으로 호출해야 하는 범위가 좁아진다.

---

## 소프트웨어 지원

| 항목 | 지원 현황 |
|:---|:---|
| CUDA | 완전 지원. `cudaMallocManaged` 풀 NVLink-C2C 성능 |
| ARM SVE2 | GCC 11+, Clang 12+, Arm Compiler 22+ |
| OpenMP / OpenMPI | 완전 지원 |
| NCCL | 완전 지원 (다중 GH200 NVLink 통신 포함) |
| PyTorch / JAX / TensorFlow | ARM64 공식 빌드 |
| NVIDIA HPC SDK | Fortran/C/C++ Neoverse V2 최적화, OpenACC GPU 오프로드 |
| OS | Ubuntu 22.04+, RHEL 9+ (ARM64) |

NVIDIA HPC SDK는 SVE2 자동 벡터화와 OpenACC GPU 오프로드를 동시에 지원한다. 기존 Fortran/C HPC 코드를 수정 없이 Grace에서 실행하면서 GPU 가속도 활용할 수 있다.

Python 생태계에서는 ARM 빌드가 PyPI를 통해 배포되므로, `pip install torch` 만으로 Grace에서 PyTorch를 실행할 수 있다.

---

## 요약

| 항목 | 내용 |
|:---|:---|
| 공정 | TSMC 4N |
| 코어 | 72 x ARM Neoverse V2 (ARMv9.0-A) |
| SIMD | SVE2 256-bit |
| L3 캐시 | ~114MB (72코어 공유) |
| 메모리 | LPDDR5X ~480 GB/s, 96GB per 다이 |
| 온다이 인터커넥트 | Mesh NoC |
| GPU 연결 | NVLink-C2C 900 GB/s 양방향, 하드웨어 캐시 일관성 |
| 패키지 | Grace CPU Superchip (Grace x2) 또는 GH200 (Grace + H100) |

Grace의 설계 목표는 범용 고성능 CPU가 아니다. PCIe 병목을 제거하고 CPU-GPU를 단일 연산 도메인으로 통합하는 것이다. Neoverse V2 코어와 LPDDR5X는 그 통합을 뒷받침하는 수단이며, NVLink-C2C가 실제 통합을 실현하는 핵심 기술이다.

다음 글: [Vera CPU / Rubin GPU - GTC 2025 공개 내용 정리](/2026-07-09-cpu-arch-2-rubin-vera-kr/)
