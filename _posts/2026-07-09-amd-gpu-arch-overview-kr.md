---
layout: post
title: "AMD GPU 아키텍처 계보: RDNA와 CDNA"
subtitle: "소비자용 RDNA와 데이터센터용 CDNA, 출시 순서로 정리"
tags: [GPU, Architecture, AMD, RDNA, CDNA, ROCm, HPC, Computer-Architecture]
lang: kr
translation-url: /2026-07-09-amd-gpu-arch-overview-en/
readtime: true
mathjax: false
---

2019년 AMD는 GPU 아키텍처를 두 계열로 분리했다. **RDNA**는 소비자 그래픽을, **CDNA**는 데이터센터 컴퓨팅을 전담한다. 이전 세대인 GCN(Graphics Core Next, 2011-2019)이 그래픽과 컴퓨트를 하나의 아키텍처로 처리하던 방식에서 탈피한 것이다.

---

## 전체 타임라인

```
연도  | RDNA (소비자)                | CDNA (데이터센터)
------|------------------------------|--------------------------
2019  | RDNA 1 — Navi 10, RX 5700   |
2020  | RDNA 2 — Navi 21, RX 6000   | CDNA 1 — Arcturus, MI100
2021  |                              | CDNA 2 — Aldebaran, MI200
2022  | RDNA 3 — Navi 31, RX 7000   |
2023  |                              | CDNA 3 — Aqua Vanjaram, MI300
2024  |                              | CDNA 3 — MI325X (HBM3e 탑재)
2025  | RDNA 4 — Navi 48, RX 9000   | CDNA 4 — MI350 (발표)
```

---

## RDNA 1 (2019) — Navi 10

**출시**: 2019년 7월 | **공정**: TSMC 7nm | **플래그십**: RX 5700 XT

GCN의 가장 큰 문제는 캐시 계층이었다. GCN은 CU 간 L1 캐시를 공유하지 않아 스레드 간 데이터 공유 비용이 높았다.

RDNA 1은 **WGP(Work Group Processor)**를 도입했다. CU 2개를 묶어 L1 캐시(128KB)를 공유하는 단위다.

```
GCN                         RDNA 1
┌──┐ ┌──┐ ┌──┐ ┌──┐        ┌────────────┐ ┌────────────┐
│CU│ │CU│ │CU│ │CU│        │    WGP     │ │    WGP     │
│L1│ │L1│ │L1│ │L1│        │ CU0 | CU1 │ │ CU0 | CU1 │
└──┘ └──┘ └──┘ └──┘        │  L1 128KB  │ │  L1 128KB  │
각 CU 전용 L1, 공유 없음       └────────────┘ └────────────┘
```

주요 특징:
- 소비자 GPU 최초 **PCIe 4.0** 채택
- L2: 4MB (셰이더 엔진당 분리)
- RX 5700 XT: 40 CU, 2560 SP, GDDR6 8GB 256-bit

---

## RDNA 2 (2020) — Navi 21

**출시**: 2020년 11월 | **공정**: TSMC 7nm | **플래그십**: RX 6900 XT

RDNA 2의 두 가지 핵심 추가는 레이 트레이싱과 Infinity Cache다.

### Ray Accelerator

AMD 소비자 GPU 최초의 하드웨어 레이 트레이싱 가속 유닛. CU당 1개 탑재. 박스 교차 판정(BVH 순회)을 고정 기능 하드웨어로 처리한다.

### Infinity Cache

128MB의 온다이 L3 캐시(Navi 21 기준). 목적은 외부 GDDR6 대역폭을 아끼는 것이다.

```
GDDR6 실제 대역폭: 512 GB/s (256-bit × 16 Gbps)
Infinity Cache 유효 대역폭: ~1,664 GB/s (128MB 히트 시 내부 로컬 읽기)
→ 히트율에 따라 유효 대역폭이 3배 이상 올라감
```

Infinity Cache는 대역폭이 부족한 GDDR6를 보완해 당시 HBM2를 쓰는 경쟁 제품과 비슷한 실효 대역폭을 확보했다.

주요 특징:
- DirectX 12 Ultimate 지원 (Mesh Shader, VRS, Sampler Feedback 포함)
- Smart Access Memory(SAM): CPU가 GPU VRAM 전체를 직접 주소 지정 (Resizable BAR)
- Xbox Series X, PlayStation 5 SoC도 RDNA 2 기반
- RX 6900 XT: 80 CU, 5120 SP, 128MB Infinity Cache, GDDR6 16GB

---

## CDNA 1 (2020) — Arcturus, MI100

**출시**: 2020년 11월 | **공정**: TSMC 7nm | **제품**: Instinct MI100

CDNA 1은 GCN에서 그래픽 파이프라인을 완전히 제거한 컴퓨트 전용 아키텍처다.

### Matrix Core

**Matrix Core**는 CDNA 1의 핵심 추가다. NVIDIA의 Tensor Core와 같은 역할로, INT8, INT4, BF16, FP16 행렬 연산을 전용 하드웨어로 가속한다.

```
CDNA 1 CU 구조:
┌──────────────────────────────────────┐
│  4 × SIMD32 (FP32/FP64 벡터 연산)    │
│  4 × Matrix Core (INT8/BF16 행렬)    │
│  LDS (Local Data Share)              │
└──────────────────────────────────────┘
```

주요 특징:
- 그래픽 파이프라인 없음 (디스플레이 출력 없음)
- FP64 벡터: 11.5 TFLOPS
- BF16 Matrix (Matrix Core): 184.6 TFLOPS
- HBM2: 32GB, 1.23 TB/s
- Infinity Fabric 2.0 (노드 간 연결)

---

## CDNA 2 (2021) — Aldebaran, MI200

**출시**: 2021년 11월 | **공정**: TSMC N6(6nm) | **제품**: Instinct MI250X

CDNA 2는 AMD GPU 최초의 **MCM(Multi-Chip Module)** 설계다. 두 개의 GPU 다이를 하나의 OAM 패키지에 집적한다.

```
MI250X OAM 패키지:
┌─────────────────────────────────────┐
│  ┌────────────┐    ┌────────────┐   │
│  │  GCD Die 0 │◄──►│  GCD Die 1 │   │
│  │  110 CU    │    │  110 CU    │   │
│  │  HBM2e ×2  │    │  HBM2e ×2  │   │
│  └────────────┘    └────────────┘   │
│      Infinity Fabric (다이 간)       │
└─────────────────────────────────────┘
         총 220 CU, 128GB HBM2e
```

주요 특징:
- 2-다이 MCM: 다이당 110 CU, 합산 220 CU
- HBM2e: 128GB, 3.2 TB/s 총 대역폭
- **FP64 Matrix Core** 추가 (CDNA 1 대비 FP64 행렬 가속 지원)
- FP64 벡터: 47.9 TFLOPS, FP64 행렬: 95.7 TFLOPS, BF16: 383 TFLOPS
- **Frontier** 슈퍼컴퓨터 채택: MI250X 기반 세계 최초 엑사스케일 시스템 (2022년 6월, Top500 1위)

---

## RDNA 3 (2022) — Navi 31

**출시**: 2022년 12월 | **공정**: GCD 5nm / MCD 6nm | **플래그십**: RX 7900 XTX

RDNA 3은 AMD 소비자 GPU 최초의 **칩렛(Chiplet)** 설계다. 단일 다이 대신 역할에 따라 다이를 분리했다.

```
Navi 31 패키지 구성:
┌─────────────────────────────────────────────────────┐
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │          GCD (Graphics Compute Die, 5nm)      │  │
│  │   Shader Engine × 12, Compute Unit × 96       │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐  │
│  │ MCD 0 │ │ MCD 1 │ │ MCD 2 │ │ MCD 3 │ │ MCD 4 │ │ MCD 5 │  │
│  │16MB IC│ │16MB IC│ │16MB IC│ │16MB IC│ │16MB IC│ │16MB IC│  │
│  │MC 64b │ │MC 64b │ │MC 64b │ │MC 64b │ │MC 64b │ │MC 64b │  │
│  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘  │
│      Infinity Fabric로 GCD와 각 MCD 연결                        │
└─────────────────────────────────────────────────────────────────┘
```

- **GCD**: 컴퓨트 전담. RDNA 3 셰이더 코어, Ray Accelerator, 지오메트리 엔진
- **MCD(Memory Cache Die)**: Infinity Cache 16MB + 64-bit 메모리 컨트롤러. 6개 합산 96MB Infinity Cache, 384-bit 인터페이스

이 분리의 장점은 수율이다. 5nm 공정의 고수율이 필요한 컴퓨트 다이를 작게 유지하고, 캐시와 메모리 컨트롤러는 6nm로 저비용 생산한다.

주요 특징:
- **Dual-Issue 셰이더**: SIMD32당 클럭당 2개 명령 동시 발행 (단순 연산 + 복잡 연산 조합)
- 2세대 Ray Accelerator (처리량 향상)
- 2세대 AI Accelerator
- DisplayPort 2.1, AV1 하드웨어 인코드
- RX 7900 XTX: 96 CU, 6144 SP, 96MB Infinity Cache, 24GB GDDR6

---

## CDNA 3 (2023) — Aqua Vanjaram, MI300 시리즈

**출시**: 2023년 12월 | **공정**: XCD 5nm / IOD 6nm | **제품**: Instinct MI300X, MI300A

CDNA 3의 핵심은 CPU, GPU, HBM을 **하나의 패키지에 집적**하는 통합 칩렛 설계다.

### MI300X: 순수 GPU 구성

8개의 XCD(eXelerate Compute Die)와 4개의 IOD(I/O Die)를 조합한다.

```
MI300X 패키지 (OAM):
┌─────────────────────────────────────────────────┐
│  XCD XCD XCD XCD   HBM3 HBM3 HBM3 HBM3         │
│  ─── ─── ─── ───   ─── ─── ─── ───             │
│       IOD IOD                                   │
│       IOD IOD                                   │
│  ─── ─── ─── ───   ─── ─── ─── ───             │
│  XCD XCD XCD XCD   HBM3 HBM3 HBM3 HBM3         │
└─────────────────────────────────────────────────┘
  8 XCD × 40 CU = ~304 활성 CU
  HBM3 × 8 스택 = 192GB, 5.3 TB/s
```

### MI300A: CPU+GPU 통합 HPC APU

GPU XCD 3개와 CPU CCD(Zen 4) 3개를 동일 패키지에 집적한다. 데이터센터용 APU로는 최초다.

```
MI300A 패키지:
┌─────────────────────────────────────────────────┐
│  GPU XCD × 3   │  CPU CCD(Zen 4) × 3           │
│  HBM3 × 8 스택 (128GB, 5.3 TB/s)               │
└─────────────────────────────────────────────────┘
```

CPU와 GPU가 동일 HBM3 풀을 공유하므로 데이터 복사 없이 CPU 계산 결과를 GPU에서 직접 사용할 수 있다.

주요 특징 (MI300X):
- FP8: ~1307 TFLOPS, BF16: 1307 TFLOPS, FP64: ~163 TFLOPS
- HBM3: 192GB, 5.3 TB/s
- **El Capitan** 슈퍼컴퓨터 채택: 2024년 Top500 1위 (>2 EFlop/s)

### MI325X (2024) — CDNA 3 메모리 업그레이드

동일한 CDNA 3 아키텍처에 HBM3 → **HBM3e**로 교체한 제품이다.

| 항목 | MI300X | MI325X |
|:---|:---:|:---:|
| 아키텍처 | CDNA 3 | CDNA 3 |
| GPU 메모리 | HBM3 192GB | HBM3e 288GB |
| 메모리 대역폭 | 5.3 TB/s | 6.0 TB/s |

용량 192GB → 288GB, 대역폭 5.3 → 6.0 TB/s로 LLM 추론 컨텍스트 확장에 직접적인 영향을 준다.

---

## RDNA 4 (2025) — Navi 48

**출시**: 2025년 3월 | **공정**: TSMC 4nm(N4P) | **플래그십**: RX 9070 XT

RDNA 4는 플래그십 없이 성능(퍼포먼스) 티어에 집중한 세대다. Navi 48 다이 기반 RX 9070 XT가 최상위 제품이다.

주요 특징:
- **4세대 Ray Accelerator**: 전 세대 대비 레이 트레이싱 처리량 2배 향상(AMD 공식)
- **AI Accelerator**: FSR 4(기계 학습 기반 업스케일링)를 온칩 AI 가속기로 처리
- DisplayPort 2.1a, AV1 인코드 개선
- RDNA 3 대비 전력 효율 개선

---

## CDNA 4 — MI350 시리즈 (2025)

CDNA 4 아키텍처 기반 제품이다. White paper가 공개됐으며, MI350X와 MI355X는 출하 중이다.

**다이 구성**

CDNA 3와 동일한 XCD 칩렛 방식이다. XCD를 5nm에서 **TSMC N3P(3nm)**으로 전환했다.

```
MI350 시리즈 패키지:
┌──────────────────────────────────────────────────────────────┐
│  XCD XCD XCD XCD    HBM3E HBM3E HBM3E HBM3E                │
│  ─── ─── ─── ───    ───── ───── ───── ─────                 │
│        IOD  IOD   (CDNA 3의 4 IOD → 2 IOD로 통합)           │
│        IOD         ← 아님, 2 IOD                            │
│  ─── ─── ─── ───    ───── ───── ───── ─────                 │
│  XCD XCD XCD XCD    HBM3E HBM3E HBM3E HBM3E                │
└──────────────────────────────────────────────────────────────┘
  8 XCD(N3P) + 2 IOD(N6) | 총 트랜지스터 1,850억
  CU: 32/XCD × 8 = 256 CU | Matrix Core: 1,024
```

**새 정밀도 포맷: MXFP**

CDNA 4의 핵심 추가 기능이다. **MXFP(Microscaling Floating Point)** 포맷을 도입했다.

- `MXFP8` / `MXFP6` / `MXFP4`: 블록 단위 스케일 팩터를 공유하는 저정밀도 행렬 포맷
- AI 추론에서 웨이트·활성화값을 더 작은 비트폭으로 표현, 처리량 극대화

**제품 라인업**

| 제품 | 냉각 | TBP | 클럭 |
|:---|:---:|:---:|:---:|
| MI355X | 액체 냉각 | 1,400W | 2,400 MHz |
| MI350X | 공냉 지원 | 1,000W | 2,200 MHz |
| MI350P | PCIe 카드 | - | - |

**MI355X 주요 스펙**

| 항목 | 값 |
|:---|:---|
| 공정 | TSMC N3P (XCD) + N6 (IOD) |
| 다이 구성 | 8 XCD + 2 IOD |
| 트랜지스터 | 1,850억 |
| CU | 256 (32/XCD × 8) |
| 메모리 | HBM3E 288GB (8스택 × 36GB) |
| 메모리 대역폭 | 8 TB/s |
| FP64 | ~79 TFLOPS |
| FP16 | ~5 PFLOPS |
| FP8 / MXFP8 | ~10 PFLOPS |
| FP4 / MXFP4 | ~20 PFLOPS |

---

## CDNA 세대별 성능 비교

![CDNA 세대별 연산 성능 비교](/assets/img/posts/amd-gpu-arch-overview/cdna-perf.png)

| | CDNA 1 (MI100) | CDNA 2 (MI250X) | CDNA 3 (MI300X) | CDNA 4 (MI355X) |
|:---|:---:|:---:|:---:|:---:|
| 공정 | 7nm | N6 (6nm) | XCD 5nm / IOD 6nm | XCD N3P / IOD N6 |
| 다이 구성 | 단일 | 2-다이 MCM | 8 XCD + 4 IOD | 8 XCD + 2 IOD |
| HBM | HBM2 32GB | HBM2e 128GB | HBM3 192GB | HBM3E 288GB |
| 메모리 대역폭 | 1.23 TB/s | 3.2 TB/s | 5.3 TB/s | 8 TB/s |
| FP64 | 11.5 TFLOPS | 47.9 TFLOPS | ~163 TFLOPS | ~79 TFLOPS |
| BF16/FP16 | 184.6 TFLOPS | 383 TFLOPS | 1,307 TFLOPS | ~5,000 TFLOPS |
| FP8 | - | - | ~2,610 TFLOPS | ~10,000 TFLOPS |
| FP4 / MXFP4 | - | - | - | ~20,000 TFLOPS |
| 주요 혁신 | Matrix Core | MCM, FP64 Matrix | XCD 칩렛, CPU+GPU 통합 | MXFP 포맷, N3P |
| 슈퍼컴 채택 | - | Frontier (1st 엑사스케일) | El Capitan (현 Top500 1위) | - |

---

## RDNA 세대별 비교

| | RDNA 1 | RDNA 2 | RDNA 3 | RDNA 4 |
|:---|:---:|:---:|:---:|:---:|
| 출시 | 2019 | 2020 | 2022 | 2025 |
| 공정 | 7nm | 7nm | GCD 5nm + MCD 6nm | 4nm |
| 다이 구성 | 단일 | 단일 | 칩렛 (GCD+MCD) | 단일 |
| Ray Tracing | 없음 | 1세대 RA | 2세대 RA | 4세대 RA |
| Infinity Cache | 없음 | 128MB (Navi 21) | 96MB (Navi 31) | - |
| 플래그십 | RX 5700 XT | RX 6900 XT | RX 7900 XTX | RX 9070 XT |
| 특징 | WGP, PCIe 4.0 | IC, DX12U | 칩렛, Dual-Issue | AI 가속, 4nm |

두 계열 모두 칩렛 방향으로 수렴하고 있다. RDNA 3에서 GCD+MCD로, CDNA 2에서 MCM 2-다이로, CDNA 3에서 XCD × 8 + IOD 통합 패키지로 진화했다.

---

## 세대별 심화 포스트

| # | 주제 | 링크 |
|:--:|:---|:---:|
| 1 | RDNA 1 - Wave32, WGP, Turing 비교 | [보기](/2026-07-09-amd-gpu-arch-1-rdna1-kr/) |
| 2 | RDNA 2 - Ray Accelerator, Infinity Cache, Ampere 비교 | [보기](/2026-07-13-amd-gpu-arch-2-rdna2-kr/) |
