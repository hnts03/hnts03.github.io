---
layout: post
title: "AMD GPU 아키텍처 #6: CDNA 2"
subtitle: "AMD 최초 GPU MCM, FP64 Matrix Core, 그리고 세계 최초 엑사스케일 Frontier"
tags: [GPU, Architecture, AMD, CDNA, ROCm, HPC, Computer-Architecture]
lang: kr
translation-url: /2026-07-15-amd-gpu-arch-6-cdna2-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 개요 | [RDNA / CDNA 전 세대 타임라인](/2026-07-09-amd-gpu-arch-overview-kr/) | ✅ |
| 4 | [RDNA 4 - 모놀리식 복귀, FSR 4](/2026-07-13-amd-gpu-arch-4-rdna4-kr/) | ✅ |
| 5 | [CDNA 1 - GCN 계승, Matrix Core, A100 대결](/2026-07-15-amd-gpu-arch-5-cdna1-kr/) | ✅ |
| 6 | CDNA 2 - MCM 2-die, FP64 Matrix, Frontier | ✅ |
| 7 | CDNA 3 - XCD 칩렛, MI300A APU, El Capitan | 🔲 |

---

## CDNA 1이 남긴 두 과제

CDNA 1(MI100)은 GCN의 컴퓨트 기반을 계승하고 Matrix Core로 행렬 가속을 시작했다. FP64/FP32 벡터에서 A100을 앞섰다. 그러나 두 약점이 있었다.

- **FP64 행렬 연산 부재**: Matrix Core는 FP16/BF16/FP32만 가속했다. FP64는 벡터 파이프라인으로만 처리됐다. 배정밀도 밀집 선형대수가 중심인 과학 계산에서 A100의 FP64 텐서 코어에 대응하지 못했다.
- **단일 다이의 한계**: MI100은 120 CU 모놀리식이었다. 더 큰 성능을 위해서는 다이를 키워야 하는데, 대형 다이는 수율이 급락한다.

**CDNA 2(Aldebaran, MI250/MI250X, 2021년 11월)**는 두 문제를 정면으로 해결했다. MCM으로 다이 한계를 넘고, FP64 Matrix Core로 HPC 성능을 완성했다.

---

## MCM: AMD 최초의 GPU 멀티 다이

CDNA 2의 헤드라인은 **MCM(Multi-Chip Module)** 이다. AMD 최초로 하나의 패키지에 GPU 다이 2개를 집적했다.

![MI250X MCM 구조](/assets/img/posts/amd-gpu-arch-6-cdna2/mcm-structure.png)

MI250X는 **GCD(Graphics Compute Die) 2개**를 OAM 패키지에 담는다. 각 GCD는 독립적인 컴퓨트 유닛과 HBM2e 메모리를 가진다.

- **GCD당**: 110 CU, 7,040 SP, 64GB HBM2e
- **MI250X 합계**: 220 CU, 14,080 SP, 128GB HBM2e, 3.2 TB/s
- **다이 간 연결**: Infinity Fabric, 양방향 400 GB/s (방향당 200 GB/s)

### 통합 GPU가 아니다: 핵심 뉘앙스

MI250X의 2개 GCD는 하나의 논리적 GPU로 합쳐지지 않는다. **운영체제와 프로그래머에게 2개의 별도 GPU로 보인다.**

```
MI250X 1개를 소프트웨어가 보는 방식:
┌──────────────────────────────────────────┐
│  MI250X (물리적으로 1개 카드)              │
│                                          │
│  GPU 0 (GCD 0)  ←→  GPU 1 (GCD 1)       │
│  64GB           IF   64GB               │
│  독립 주소공간        독립 주소공간          │
│                                          │
│  → 프로그램은 2개 GPU로 인식하고           │
│    명시적으로 데이터를 나눠야 한다          │
└──────────────────────────────────────────┘
```

Frontier의 노드 하나에는 MI250X 4개가 들어간다. 소프트웨어는 이를 **8개 GPU(GCD 8개)** 로 인식한다. 한 GCD가 다른 GCD의 메모리에 접근하려면 Infinity Fabric을 경유하며, 이는 NUMA(비균일 메모리 접근)와 유사한 특성을 만든다.

이 설계는 다이 크기 한계를 우회하는 실용적 선택이었다. 그러나 프로그래머가 두 다이를 명시적으로 다뤄야 하는 부담을 남긴다. 두 다이를 하나의 논리적 GPU로 통합하는 것은 다음 세대 CDNA 3(MI300)의 과제가 된다.

---

## FP64 Matrix Core: HPC 성능의 완성

CDNA 2의 두 번째 핵심은 **FP64 Matrix Core** 추가다.

CDNA 1의 Matrix Core는 FP64 행렬 연산을 지원하지 않았다. CDNA 2는 이를 추가하고, 동시에 FP64 벡터 연산도 풀레이트(full-rate)로 끌어올렸다.

```
FP64 성능 진화 (per 카드):
  MI100 (CDNA 1)  : FP64 벡터 11.5 TFLOPS,  FP64 Matrix 없음
  MI250X (CDNA 2) : FP64 벡터 47.9 TFLOPS,  FP64 Matrix 95.7 TFLOPS
                    ↑ 벡터 ~4× (다이 2개 + 다이당 풀레이트 FP64)
                    ↑ Matrix 신규 (벡터의 2배)
```

FP64 성능이 MI100 대비 약 4배로 뛴 것은 두 요인의 곱이다. 다이가 2개(2배)가 됐고, 다이당 FP64 처리율도 풀레이트로 2배가 됐다. 여기에 FP64 Matrix Core가 벡터의 2배(95.7 TFLOPS)를 더한다.

이 배정밀도 성능이 CDNA 2를 HPC 시장의 강자로 만들었다. 과학 계산의 밀집 선형대수는 FP64 행렬 곱이 지배적이다. A100의 FP64 텐서 코어(19.5 TFLOPS) 대비 MI250X의 FP64 Matrix(95.7 TFLOPS)는 약 5배 앞선다.

---

## 메모리와 인터커넥트

**HBM2e 메모리**

MI250X는 GCD당 4스택 HBM2e, 합계 8스택 128GB를 8192-bit 인터페이스로 연결한다. 대역폭은 3.2 TB/s로, CDNA 1(1.23 TB/s) 대비 약 2.6배다.

**3세대 Infinity Fabric: CPU까지 확장**

CDNA 2의 Infinity Fabric은 GPU 간 연결을 넘어 **CPU-GPU 코히런트 연결**로 확장됐다.

```
Frontier 노드 구성:
┌────────────────────────────────────────────────┐
│  EPYC CPU (64코어, 3세대)                        │
│     │  Coherent Infinity Fabric (36+36 GB/s/GCD) │
│     ├── MI250X #1 (GCD 0, GCD 1)                │
│     ├── MI250X #2 (GCD 2, GCD 3)                │
│     ├── MI250X #3 (GCD 4, GCD 5)                │
│     └── MI250X #4 (GCD 6, GCD 7)                │
│  → 노드당 8 GCD, CPU-GPU 통합 메모리 공간         │
└────────────────────────────────────────────────┘
```

CPU와 GPU가 Infinity Fabric으로 코히런트하게 연결된다. PCIe를 경유하지 않고 CPU와 GPU가 캐시 일관성을 유지하며 메모리를 공유한다. 이는 CPU-GPU 데이터 이동이 잦은 HPC 워크로드의 병목을 완화한다. NVIDIA가 Grace-Hopper에서 NVLink-C2C로 구현한 것과 유사한 방향을, AMD는 CDNA 2 시기에 Infinity Fabric으로 앞서 실현했다.

**MI250X 스펙:**

| 항목 | 값 |
|:---|:---|
| 코드명 | Aldebaran |
| 공정 | TSMC 6nm (N6) |
| 다이 구성 | 2 GCD (MCM) |
| CU | 220 (GCD당 110) |
| 스트림 프로세서 | 14,080 |
| 부스트 클럭 | 1,700 MHz |
| FP64 벡터 | 47.9 TFLOPS |
| FP64 Matrix | 95.7 TFLOPS |
| FP32 벡터 | 47.9 TFLOPS |
| FP16/BF16 Matrix | 383 TFLOPS |
| 메모리 | HBM2e 128GB, 8192-bit |
| 메모리 대역폭 | 3.2 TB/s |
| TDP | 500W (560W 피크) |

---

## Frontier: 세계 최초 엑사스케일

CDNA 2의 의의는 벤치마크 수치를 넘어선다. MI250X는 **Frontier**의 연산 엔진이다.

Frontier는 미국 오크리지 국립연구소(ORNL)의 슈퍼컴퓨터로, 2022년 6월 Top500에서 세계 최초로 **엑사스케일(1 EFlop/s 초과)** 을 달성하며 1위에 올랐다.

- **노드 구성**: EPYC CPU 1개 + MI250X 4개(GCD 8개)
- **규모**: 9,000개 이상 노드
- **성능**: HPL 벤치마크 1.1 EFlop/s 초과
- **효율**: Green500(전력 효율)에서도 상위권

Frontier는 AMD가 데이터센터 컴퓨트에서 최정상 시스템을 확보했음을 입증했다. 같은 MI250X 기반으로 유럽의 **LUMI** 슈퍼컴퓨터도 구축됐다. NVIDIA가 지배하던 최상위 HPC 시장에서 AMD가 실질적 대안임을 보인 전환점이었다.

---

## NVIDIA A100과의 비교

MI250X 출시 시점(2021년 11월)의 경쟁자는 NVIDIA **A100(Ampere)** 이다. H100(Hopper)은 이듬해 등장한다.

### 핵심 사양 비교

![MI250X (CDNA 2) vs A100 80GB (Ampere)](/assets/img/posts/amd-gpu-arch-6-cdna2/spec-compare.png)

| | MI250X (CDNA 2) | A100 80GB (Ampere) |
|:---|:---:|:---:|
| 공정 | TSMC 6nm | TSMC 7nm |
| 다이 구성 | 2 GCD (MCM) | 단일 |
| FP64 벡터 | 47.9 TFLOPS | 9.7 TFLOPS |
| FP64 Matrix/Tensor | 95.7 TFLOPS | 19.5 TFLOPS |
| FP16 Matrix/Tensor | 383 TFLOPS | 312 TFLOPS |
| Sparsity 가속 | 없음 | 2배 (624 TFLOPS) |
| TF32 | 미지원 | 지원 |
| 메모리 | HBM2e 128GB | HBM2e 80GB |
| 메모리 대역폭 | 3.2 TB/s | 2.0 TB/s |
| 프로그래밍 모델 | 2 GPU (분리) | 1 GPU (통합) |
| TDP | 500W | 400W |

### 영역별 우열

**HPC (FP64)**

MI250X가 압도한다. FP64 Matrix 95.7 TFLOPS는 A100의 5배에 가깝다. 메모리 용량(128 vs 80GB)과 대역폭(3.2 vs 2.0 TB/s)도 앞선다. Frontier 엑사스케일 달성이 이 우위의 실증이다.

**AI/딥러닝**

혼재된 양상이다. FP16 밀집 연산은 MI250X(383)가 A100(312)를 앞선다. 그러나 A100은 **구조적 희소성**으로 624 TFLOPS까지 확장하고, **TF32** 학습 포맷을 지원한다. 실효 AI 성능에서는 A100이 우위를 점하는 경우가 많았다.

**프로그래밍 모델**

A100이 유리하다. A100은 단일 논리적 GPU로 프로그래밍이 단순하다. MI250X는 2개 GCD를 명시적으로 다뤄야 하며, 다이 간 데이터 이동을 프로그래머가 관리해야 한다. 이 복잡성은 소프트웨어 이식과 최적화의 부담을 키웠다.

**소프트웨어**

여전히 CUDA 생태계가 앞선다. 다만 Frontier 도입으로 ROCm이 대형 실전 시스템에서 검증되기 시작했고, HPC 라이브러리 지원이 개선됐다.

---

## 요약

| 항목 | CDNA 1 대비 변화 |
|:---|:---|
| 다이 구성 | 모놀리식 → MCM 2-die (AMD 최초 GPU MCM) |
| 공정 | 7nm → 6nm (N6) |
| FP64 Matrix | 없음 → 95.7 TFLOPS (신규) |
| FP64 벡터 | 11.5 → 47.9 TFLOPS (~4×) |
| 메모리 | HBM2 32GB → HBM2e 128GB |
| 메모리 대역폭 | 1.23 → 3.2 TB/s |
| Infinity Fabric | GPU 간 → CPU-GPU 코히런트 |
| 슈퍼컴 | - → Frontier (세계 최초 엑사스케일) |

| | MI250X (CDNA 2) | A100 (Ampere) |
|:---|:---:|:---:|
| FP64 Matrix | 95.7 TFLOPS (압도) | 19.5 TFLOPS |
| FP16 Matrix | 383 TFLOPS (우세) | 312 TFLOPS |
| AI 실효 (sparsity/TF32) | 열세 | 우세 |
| 메모리 | 128GB, 3.2 TB/s (우세) | 80GB, 2.0 TB/s |
| 프로그래밍 | 2 GPU 분리 (복잡) | 1 GPU (단순) |

CDNA 2는 AMD를 HPC 최정상으로 끌어올렸다. MCM으로 다이 한계를 넘고, FP64 Matrix Core로 배정밀도 성능을 완성했으며, Frontier로 세계 최초 엑사스케일을 달성했다. 그러나 2개 GCD가 별도 GPU로 보이는 분리형 MCM은 프로그래밍 복잡성을 남겼다. 이 다이들을 하나의 논리적 GPU로 통합하고 CPU까지 한 패키지에 넣는 것이 다음 세대의 도전이 된다.

다음 글: CDNA 3 - XCD 칩렛, CPU+GPU 통합 APU(MI300A), 그리고 El Capitan (예정)
