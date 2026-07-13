---
layout: post
title: "AMD GPU 아키텍처 #4: RDNA 4"
subtitle: "모놀리식 복귀, 3세대 Ray Accelerator, FSR 4의 ML 전환, 그리고 Blackwell과의 대결"
tags: [GPU, Architecture, AMD, RDNA, Computer-Architecture]
lang: kr
translation-url: /2026-07-13-amd-gpu-arch-4-rdna4-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 개요 | [RDNA / CDNA 전 세대 타임라인](/2026-07-09-amd-gpu-arch-overview-kr/) | ✅ |
| 1 | [RDNA 1 - Wave32, WGP, 7nm](/2026-07-09-amd-gpu-arch-1-rdna1-kr/) | ✅ |
| 2 | [RDNA 2 - Ray Accelerator, Infinity Cache, Ampere 대결](/2026-07-13-amd-gpu-arch-2-rdna2-kr/) | ✅ |
| 3 | [RDNA 3 - 칩렛(GCD+MCD), Dual-Issue, Ada 대결](/2026-07-13-amd-gpu-arch-3-rdna3-kr/) | ✅ |
| 4 | RDNA 4 - 모놀리식 복귀, 3세대 RA, FSR 4, Blackwell 대결 | ✅ |

---

## RDNA 3가 남긴 두 가지 과제

RDNA 3는 칩렛으로 제조 경제학을 바꿨다. 그러나 두 약점이 명확했다.

- **레이 트레이싱**: 2세대 Ray Accelerator는 NVIDIA Ada의 3세대 RT Core에 크게 뒤졌다. RT 활성화 게임에서 격차가 컸다.
- **AI 업스케일링**: FSR 3는 여전히 비-ML 방식이었다. DLSS(딥러닝 기반)와 화질 격차가 좁혀지지 않았다.

칩렛의 전력 오버헤드도 부담이었다. RDNA 4(Navi 48, 2025년 3월)는 전략을 바꿨다. 최상위 플래그십을 포기하고, 퍼포먼스 티어에서 두 약점을 집중적으로 개선했다.

---

## 모놀리식 복귀와 전략 전환

RDNA 4는 칩렛을 버리고 **모놀리식 다이**로 돌아왔다.

```
RDNA 세대별 다이 전략:
  RDNA 1 (Navi 10)  : 모놀리식 7nm
  RDNA 2 (Navi 21)  : 모놀리식 7nm  (Big Navi)
  RDNA 3 (Navi 31)  : 칩렛 (GCD N5 + 6 MCD N6)
  RDNA 4 (Navi 48)  : 모놀리식 N4P  ← 복귀
```

Navi 48은 TSMC **N4P(4nm)** 공정, 357mm² 다이에 539억 트랜지스터를 집적했다. RDNA 3의 칩렛 분리가 겨냥했던 것은 대형 고성능 다이의 원가였다. RDNA 4는 퍼포먼스 티어(중형 다이)에 집중하므로, 칩렛 통신 오버헤드를 감수하기보다 모놀리식이 전력 효율과 레이턴시에서 유리하다.

이 세대에는 최상위 플래그십(RX 7900 XTX급 후속)이 없다. 최상위 제품은 Navi 48 기반 **RX 9070 XT**다.

| 항목 | Navi 31 (RDNA 3) | Navi 48 (RDNA 4) |
|:---|:---:|:---:|
| 다이 구성 | 칩렛 (GCD + 6 MCD) | 모놀리식 |
| 공정 | GCD N5 / MCD N6 | N4P (4nm) |
| 다이 면적 | GCD 304mm² + 6 MCD | 357mm² (단일) |
| 트랜지스터 | ~578억 | 539억 |
| 최상위 제품 | RX 7900 XTX (96 CU) | RX 9070 XT (64 CU) |

---

## 3세대 Ray Accelerator: RT 격차 좁히기

RDNA 4의 핵심 개선은 레이 트레이싱이다. **3세대 Ray Accelerator**를 도입했다.

```
Ray Accelerator 세대:
  RDNA 2 : 1세대 - BVH 순회 + 박스/삼각형 교차 (기본)
  RDNA 3 : 2세대 - ~1.5× 처리량, ray box sorting
  RDNA 4 : 3세대 - 삼각형 교차 2.5×, 처리량 2×,
                   Instance transform + 스택 관리 전용 HW
```

3세대 Ray Accelerator의 개선점:

- **Ray-Triangle 교차 판정 2.5배 향상** (RDNA 3 대비)
- **BVH 순회 처리량 2배**
- **Instance transform 전용 하드웨어**: 오브젝트 인스턴싱(같은 지오메트리 반복 배치)의 좌표 변환을 하드웨어가 처리
- **스택 관리 가속**: BVH 순회 중 스택 push/pop을 하드웨어로 처리해 셰이더 부담 경감

RDNA 2에서 소프트웨어 폴백으로 시작한 AMD의 RT는, RDNA 4에서 BVH 순회의 핵심 병목(교차 판정, 스택 관리)을 대부분 고정 기능 하드웨어로 옮겼다. NVIDIA와의 절대 격차는 남았지만, 무거운 RT 워크로드에서의 붕괴는 크게 완화됐다.

---

## 2세대 AI Accelerator와 FSR 4

RDNA 3가 WMMA로 처음 도입한 AI 가속을 RDNA 4는 **2세대 AI Accelerator**로 강화했다.

- **FP8, INT4 포맷 지원 추가**: 저정밀도 추론 가속
- **온칩 스케줄링 개선**
- **희소성(sparsity) 활용 시 전 세대 대비 최대 8배 AI 성능**

이 하드웨어가 RDNA 4의 소프트웨어 헤드라인인 **FSR 4**를 가능하게 한다.

![FSR 진화: 공간 기반에서 ML 기반으로](/assets/img/posts/amd-gpu-arch-4-rdna4/fsr-evolution.png)

**FSR 4는 AMD 최초의 머신러닝 기반 업스케일링이다.** FSR 1~3는 공간·시간적 알고리즘으로, AI 추론을 사용하지 않았다. 이 때문에 NVIDIA DLSS(딥러닝 기반)와 화질 격차가 존재했다.

FSR 4는 이 접근을 근본적으로 바꿨다. AMD가 학습시킨 게임 ML 모델을 RDNA 4 AI Accelerator에서 실행한다. FP8 모델을 온칩 AI 가속기로 추론해 업스케일링 품질을 DLSS 수준으로 끌어올렸다.

| 항목 | FSR 3 이하 | FSR 4 |
|:---|:---:|:---:|
| 방식 | 공간/시간적 알고리즘 | ML 기반 추론 |
| AI 하드웨어 | 불필요 | RDNA 4 AI Accelerator 필요 |
| 타 GPU 호환 | 가능 (NVIDIA 포함) | RDNA 4 전용 |
| DLSS 대비 화질 | 열세 | 대등 목표 |

FSR 4의 대가는 하드웨어 종속성이다. FSR 3까지는 모든 GPU에서 동작했으나, FSR 4는 RDNA 4 AI 가속기를 요구한다. 이는 DLSS가 Tensor Core를 요구하는 것과 같은 구조다. AMD는 개방성을 일부 포기하고 화질을 택했다.

---

## 기타 개선

- **3세대 Infinity Cache**: Navi 48 기준 64MB
- **PCIe 5.0** 인터페이스
- **DisplayPort 2.1a(UHBR13.5)**, HDMI 2.1b
- RDNA 3 대비 성능당 전력 개선 (모놀리식 + N4P 공정)

**RX 9070 XT 스펙:**

| 항목 | 값 |
|:---|:---|
| 공정 | TSMC N4P (4nm) |
| 다이 | Navi 48 모놀리식, 357mm² |
| 트랜지스터 | 539억 |
| CU | 64 |
| 스트림 프로세서 | 4,096 |
| Ray Accelerator | 64 (3세대) |
| AI Accelerator | 128 (2세대) |
| Infinity Cache | 64MB (3세대) |
| VRAM | GDDR6 16GB, 256-bit |
| 메모리 대역폭 | 640 GB/s |
| 게임 클럭 / 부스트 | 2,400 / 2,970 MHz |
| FP32 | 48.7 TFLOPS |
| TBP | 304W |
| 출시가 | $599 |

하위 모델 **RX 9070**은 56 CU, 3,584 SP, 36.1 TFLOPS, TBP 220W, $549다.

---

## NVIDIA Blackwell과의 비교

RDNA 4의 경쟁 상대는 NVIDIA **Blackwell(RTX 50)** 세대다. RX 9070 XT($599)의 직접 대결 상대는 **RTX 5070 Ti($749)** 다.

### 핵심 사양 비교

![RX 9070 XT (RDNA 4) vs RTX 5070 Ti (Blackwell)](/assets/img/posts/amd-gpu-arch-4-rdna4/spec-compare.png)

| | RX 9070 XT (RDNA 4) | RTX 5070 Ti (Blackwell) |
|:---|:---:|:---:|
| 공정 | TSMC N4P | TSMC 4N |
| 다이 | Navi 48 (357mm²) | GB203 (~378mm²) |
| 셰이더 | 4,096 SP | 8,960 CUDA |
| FP32 | 48.7 TFLOPS | ~43.9 TFLOPS |
| 메모리 | GDDR6 16GB 256-bit | GDDR7 16GB 256-bit |
| 메모리 대역폭 | 640 GB/s | 896 GB/s |
| RT | 3세대 RA | 4세대 RT Core |
| ML 업스케일 | FSR 4 | DLSS 4 |
| TBP | 304W | 300W |
| 출시가 | $599 | $749 |

### 영역별 우열

**래스터라이제이션**

55개 게임 평균 기준, RX 9070 XT는 RTX 5070 Ti보다 약 5% 뒤진다. 다수 타이틀에서 6% 이내로 접전이다. 가격이 20% 저렴($599 vs $749)하므로 가성비에서 명확히 앞선다.

**레이 트레이싱**

3세대 Ray Accelerator로 크게 개선됐으나, Blackwell의 4세대 RT Core와는 여전히 격차가 있다. 무거운 RT 타이틀(F1 25 등)에서 RTX 5070 Ti가 20~24% 앞선다. 패스 트레이싱처럼 극단적인 RT 워크로드에서는 격차가 더 벌어진다.

**ML 업스케일링**

FSR 4는 AMD 최초의 ML 업스케일링으로 FSR 3 대비 화질이 크게 향상됐다. DLSS 4는 멀티 프레임 생성을 포함해 여전히 기능 폭에서 앞서지만, 업스케일 화질 자체의 격차는 이전 세대보다 크게 좁혀졌다.

**포지셔닝**

RDNA 4는 최상위 성능 경쟁을 포기하고 가성비 티어에 집중했다. RTX 5070 Ti에 근접한 래스터 성능을 20% 낮은 가격에 제공하는 것이 핵심 전략이다.

---

## 소프트웨어

**FSR 4와 FSR Redstone**

FSR 4는 RDNA 4 AI 가속기 기반 ML 업스케일링이다. 이후 **FSR Redstone**으로 AI 기반 업스케일링과 프레임 생성이 확장됐다.

FSR 4.1은 RDNA 3에도 일부 업스케일링을 제공하는 방향으로 확장됐다. 다만 완전한 화질 패리티는 RDNA 4 전용이다.

**ROCm**

RDNA 4는 소비자 카드로서 ROCm 컴퓨트 지원이 이어진다. 2세대 AI Accelerator의 FP8 지원으로 로컬 LLM 추론 등 소비자용 ML 워크로드 활용도가 높아졌다. 대규모 학습·HPC의 주력은 여전히 CDNA(MI 시리즈)다.

---

## 요약

| 항목 | RDNA 3 대비 변화 |
|:---|:---|
| 다이 구성 | 칩렛 → 모놀리식 복귀 |
| 공정 | GCD N5 / MCD N6 → N4P (4nm) |
| Ray Accelerator | 2세대 → 3세대 (삼각형 교차 2.5×) |
| AI Accelerator | 1세대(WMMA) → 2세대 (FP8/INT4) |
| 업스케일링 | FSR 3 (비-ML) → FSR 4 (ML 기반) |
| 포지셔닝 | 플래그십 포함 → 퍼포먼스 티어 집중 |
| 인터페이스 | PCIe 4.0 → PCIe 5.0 |

| | RX 9070 XT (RDNA 4) | RTX 5070 Ti (Blackwell) |
|:---|:---:|:---:|
| FP32 | 48.7 TFLOPS | ~43.9 TFLOPS |
| 메모리 BW | 640 GB/s | 896 GB/s |
| 래스터 (55게임 평균) | -5% | 기준 |
| 레이 트레이싱 | 3세대, 열세 | 4세대, 우세 |
| ML 업스케일 | FSR 4 | DLSS 4 |
| 출시가 | $599 | $749 |

RDNA 4는 최상위 경쟁을 포기하는 대신 RDNA 3의 두 약점을 정면으로 공략했다. 3세대 Ray Accelerator로 RT 붕괴를 완화하고, FSR 4로 AMD 최초의 ML 업스케일링을 실현했다. 모놀리식 복귀는 퍼포먼스 티어에 최적화된 선택이었다. 절대 성능에서 Blackwell 최상위를 넘지는 못했으나, 가성비 티어에서 명확한 경쟁력을 확보했다.

이것으로 RDNA 1부터 4까지 소비자 GPU 계보를 마친다. 다음은 데이터센터 CDNA 계열의 심화로 이어진다. (예정)
