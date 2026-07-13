---
layout: post
title: "AMD GPU 아키텍처 #3: RDNA 3"
subtitle: "칩렛으로 분리된 다이, Dual-Issue 셰이더, 그리고 NVIDIA Ada Lovelace와의 대결"
tags: [GPU, Architecture, AMD, RDNA, Computer-Architecture]
lang: kr
translation-url: /2026-07-13-amd-gpu-arch-3-rdna3-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 개요 | [RDNA / CDNA 전 세대 타임라인](/2026-07-09-amd-gpu-arch-overview-kr/) | ✅ |
| 1 | [RDNA 1 - Wave32, WGP, 7nm](/2026-07-09-amd-gpu-arch-1-rdna1-kr/) | ✅ |
| 2 | [RDNA 2 - Ray Accelerator, Infinity Cache, Ampere 대결](/2026-07-13-amd-gpu-arch-2-rdna2-kr/) | ✅ |
| 3 | RDNA 3 - 칩렛(GCD+MCD), Dual-Issue, Ada 대결 | ✅ |
| 4 | [RDNA 4 - 모놀리식 복귀, 3세대 RA, FSR 4, Blackwell 대결](/2026-07-13-amd-gpu-arch-4-rdna4-kr/) | ✅ |

---

## RDNA 2가 마주한 벽

RDNA 2는 Infinity Cache 128MB를 온다이에 집적해 GDDR6 대역폭 한계를 우회했다. 문제는 이 방식이 다음 세대에서 걸림돌이 된다는 데 있었다.

SRAM(캐시)은 공정 미세화의 혜택을 로직만큼 받지 못한다. 7nm에서 5nm로 넘어가도 로직 트랜지스터는 크게 줄지만 SRAM 셀 면적은 거의 줄지 않는다. Infinity Cache를 더 키우려면 비싼 5nm 다이 면적을 SRAM이 잠식하게 된다.

메모리 컨트롤러와 PHY도 마찬가지다. 아날로그 회로에 가까운 이 블록들은 미세 공정으로 옮겨도 면적 이득이 작다. 값비싼 5nm 웨이퍼에 축소되지 않는 회로를 얹는 것은 비효율이다.

**RDNA 3(Navi 31, 2022년 12월)**는 이 문제를 칩렛으로 해결했다.

---

## 칩렛: 소비자 GPU 최초의 다이 분리

RDNA 3는 AMD 최초의 **칩렛 기반 소비자 GPU**다. 하나의 큰 다이를 기능별로 분리했다.

![Navi 31 칩렛 패키지 구조](/assets/img/posts/amd-gpu-arch-3-rdna3/chiplet-layout.png)

- **GCD(Graphics Compute Die)**: 셰이더, Ray Accelerator, 지오메트리 엔진, 디스플레이 엔진, 미디어 엔진. 로직 집약적이므로 **TSMC N5(5nm)** 사용. Navi 31 기준 약 304mm².
- **MCD(Memory Cache Die)**: 각 16MB Infinity Cache + 64-bit GDDR6 메모리 컨트롤러. 축소 이득이 작으므로 저렴한 **TSMC N6(6nm)** 사용. 개당 약 37mm².

Navi 31은 GCD 1개와 MCD 6개로 구성된다.

```
분리 논리:
┌─────────────────────────────┬────────────────────────────────┐
│  GCD (N5, 5nm)              │  MCD × 6 (N6, 6nm)             │
│  - 로직 집약적 (셰이더)      │  - SRAM/아날로그 (캐시/PHY)     │
│  - 미세공정 이득 큼          │  - 미세공정 이득 작음           │
│  → 비싼 5nm에 집적           │  → 저렴한 6nm로 분리            │
└─────────────────────────────┴────────────────────────────────┘

MCD 6개 합산:
  Infinity Cache: 16MB × 6 = 96MB
  메모리 버스: 64-bit × 6 = 384-bit → GDDR6 960 GB/s
```

두 다이는 **Infinity Fanout Links**로 연결된다. 이는 온패키지 고밀도 인터커넥트로, GCD와 6개 MCD 사이 총 대역폭이 약 5.3 TB/s에 이른다. 온다이 배선만큼 빠르지는 않지만, 별도 다이로 분리하면서도 대역폭 페널티를 최소화한다.

칩렛의 실익:
- 값비싼 5nm 다이 면적을 로직에만 집중
- 축소되지 않는 캐시/IO를 저렴한 6nm로 이전
- MCD 개수 조절로 제품 세분화 (하위 모델은 MCD 5개 → 320-bit)

RDNA 2 Navi 21(모놀리식 520mm²)과 비교하면, RDNA 3는 총 실리콘 면적이 유사하면서도 값비싼 5nm는 GCD 304mm²만 사용한다.

---

## Dual-Issue 셰이더: 실행 유닛의 변화

RDNA 3는 CU 내부 연산 처리 방식을 바꿨다.

```
RDNA 2 SIMD32 (클럭당 1명령):
┌──────────────────────────────────┐
│  SIMD32: 32 레인 × FP32 1명령/클럭 │
└──────────────────────────────────┘

RDNA 3 SIMD32 (Dual-Issue, 조건부 2명령):
┌──────────────────────────────────────────┐
│  SIMD32: 32 레인 × FP32 최대 2명령/클럭    │
│  단일 명령(VOPD)로 두 연산 페어링 발행     │
└──────────────────────────────────────────┘
```

각 SIMD32가 특정 조건에서 클럭당 2개 명령을 발행한다. FP32 피크 처리량이 명목상 2배가 된다.

| 항목 | RDNA 2 (Navi 21) | RDNA 3 (Navi 31) |
|:---|:---:|:---:|
| CU 수 | 80 | 96 |
| 스트림 프로세서 | 5,120 | 6,144 |
| Dual-Issue | 없음 | 있음 |
| 명목 FP32 피크 | 5,120 FP32 | 6,144 × 2 = 12,288 FP32 상당 |

Dual-Issue는 두 명령이 특정 페어링 규칙을 만족해야 발동된다. NVIDIA Ampere/Ada가 SM당 FP32 유닛을 물리적으로 늘린 것과 달리, RDNA 3는 기존 유닛의 명령 발행을 이중화했다. 이 때문에 실효 성능 이득은 워크로드에 따라 편차가 크다. 컴파일러가 명령 페어를 얼마나 잘 구성하는지에 좌우된다.

---

## AI Accelerator: RDNA 최초의 행렬 가속

RDNA 3는 RDNA 계열 최초로 행렬 연산 가속을 도입했다.

**WMMA(Wave Matrix Multiply-Accumulate)** 명령이 추가됐다. BF16, FP16, INT8, INT4 행렬 연산을 가속한다. CDNA가 Matrix Core로 먼저 확보했던 기능이 소비자 RDNA에도 들어온 것이다.

```
연산 계층:
  RDNA 1/2: SIMD32 (벡터 FP32/INT32) 만
  RDNA 3:   SIMD32 + WMMA (행렬 BF16/FP16/INT8/INT4)
```

WMMA는 별도 물리 유닛이라기보다 SIMD 유닛을 활용하는 행렬 명령 경로에 가깝다. NVIDIA의 전용 Tensor Core와는 구현이 다르다. 그러나 소비자 카드에서 ML 추론과 업스케일링을 가속할 기반이 마련됐다.

---

## 2세대 Ray Accelerator와 기타 개선

**2세대 Ray Accelerator**

CU당 레이 트레이싱 처리량이 RDNA 2 대비 약 1.5배로 향상됐다. Ray box sorting과 traversal 최적화가 적용됐다. 절대 성능은 여전히 NVIDIA 대비 열세지만 세대 내 개선폭은 크다.

**클럭 디커플링**

RDNA 3는 프론트엔드 클럭과 셰이더 클럭을 분리했다. 프론트엔드(지오메트리, 래스터)는 약 2.5 GHz, 셰이더 어레이는 약 2.3 GHz로 동작한다. 셰이더를 약간 낮은 클럭으로 돌려 전력을 절감하는 설계다.

**미디어와 디스플레이**

- 듀얼 미디어 엔진, **AV1 하드웨어 인코드/디코드** 추가 (RDNA 2는 AV1 디코드만)
- **DisplayPort 2.1**(UHBR13.5) 지원, 8K 고주사율 대응

**RX 7900 XTX 스펙:**

| 항목 | 값 |
|:---|:---|
| GCD 공정 | TSMC N5 (5nm) |
| MCD 공정 | TSMC N6 (6nm) |
| 다이 구성 | GCD 1 + MCD 6 |
| 트랜지스터 | 약 578억 (전체 칩렛) |
| CU | 96 |
| 스트림 프로세서 | 6,144 |
| Infinity Cache | 96MB |
| VRAM | GDDR6 24GB, 384-bit |
| 메모리 대역폭 | 960 GB/s |
| FP32 (Dual-Issue 피크) | 약 61 TFLOPS |
| TBP | 355W |
| 출시가 | $999 |

---

## NVIDIA Ada Lovelace와의 비교

RDNA 3의 경쟁자는 2022년 10월 출시된 NVIDIA **Ada Lovelace(RTX 40)** 다. Ada는 TSMC 4nm 모놀리식 다이로, 3세대 RT Core와 DLSS 3 Frame Generation을 도입했다.

RTX 4090(AD102)은 별도 체급이다. RX 7900 XTX의 실질 경쟁 상대는 RTX 4080이다.

### 핵심 사양 비교

![RX 7900 XTX (RDNA 3) vs RTX 4080 (Ada Lovelace)](/assets/img/posts/amd-gpu-arch-3-rdna3/spec-compare.png)

| | RX 7900 XTX (RDNA 3) | RTX 4080 (Ada) | RTX 4090 (Ada) |
|:---|:---:|:---:|:---:|
| 공정 | GCD N5 / MCD N6 | 모놀리식 4nm | 모놀리식 4nm |
| 다이 | 칩렛 (GCD 304mm² + 6 MCD) | AD103 (379mm²) | AD102 (609mm²) |
| 셰이더 | 6,144 SP | 9,728 CUDA | 16,384 CUDA |
| FP32 (피크) | ~61 TFLOPS | ~48.7 TFLOPS | ~82.6 TFLOPS |
| 메모리 인터페이스 | GDDR6 384-bit | GDDR6X 256-bit | GDDR6X 384-bit |
| 메모리 대역폭 | 960 GB/s | 716.8 GB/s | 1,008 GB/s |
| VRAM | 24GB | 16GB | 24GB |
| RT 세대 | 2세대 | 3세대 | 3세대 |
| 프레임 생성 | FSR 3 (SW) | DLSS 3 (HW OFA) | DLSS 3 |
| TBP | 355W | 320W | 450W |
| 출시가 | $999 | $1,199 | $1,599 |

### 영역별 우열

**래스터라이제이션**

RX 7900 XTX는 4K 래스터에서 RTX 4080과 대등하며 일부 타이틀에서는 앞선다. 메모리 대역폭(960 vs 717 GB/s)과 24GB VRAM이 고해상도에서 유리하다. 가격도 $999로 $1,199인 RTX 4080보다 낮았다.

**레이 트레이싱**

Ada의 3세대 RT Core는 **SER(Shader Execution Reordering)**와 **OMM(Opacity Micromap)** 을 도입해 RT 효율을 크게 높였다. RDNA 3의 2세대 Ray Accelerator는 세대 내 개선에도 불구하고 격차를 좁히지 못했다. RT 활성화 게임에서 RX 7900 XTX는 대략 RTX 3090 Ti 수준으로, RTX 4080보다 뒤처졌다.

**프레임 생성과 업스케일링**

Ada는 **DLSS 3 Frame Generation**을 도입했다. Optical Flow Accelerator(OFA)라는 Ada 전용 하드웨어로 중간 프레임을 생성한다. RDNA 3에서는 사용 불가능하다.

AMD는 **FSR 3 Fluid Motion Frames**(2023)로 대응했다. 소프트웨어 기반 프레임 생성으로, 전용 하드웨어 없이 동작하며 구형 GPU와 NVIDIA GPU에서도 사용 가능하다. 반면 화질과 레이턴시 일관성에서 DLSS 3에 미치지 못했다.

**전력 효율**

Ada는 4nm 모놀리식으로 전력 효율에서 앞섰다. RDNA 3는 칩렛 간 통신 오버헤드와 상대적으로 낮은 공정 효율로 성능당 전력에서 열세였다.

---

## 소프트웨어

**FSR 계보**

| 버전 | 방식 | 출시 |
|:---|:---|:---|
| FSR 1 | 공간 업스케일링 | 2021 |
| FSR 2 | 시간적(temporal) 업스케일링 | 2022 |
| FSR 3 | 시간적 업스케일링 + Fluid Motion Frames (프레임 생성) | 2023 |

FSR 3는 DLSS 3의 프레임 생성에 대응한다. 모든 FSR은 하드웨어 비의존 오픈소스로, NVIDIA GPU에서도 동작한다는 점이 DLSS와 다르다.

**ROCm**

RDNA 3에서 RX 7900 XTX가 일부 ROCm 워크로드 공식 지원 대상에 진입했다. WMMA 명령으로 소비자 카드에서 ML 추론을 가속할 수 있게 됐다. 다만 HPC/대규모 학습의 주력은 여전히 CDNA 계열이다.

---

## 요약

| 항목 | RDNA 2 대비 변화 |
|:---|:---|
| 다이 구성 | 모놀리식 → 칩렛 (GCD N5 + 6 MCD N6) |
| 셰이더 | 클럭당 1명령 → Dual-Issue (조건부 2명령) |
| 행렬 가속 | 없음 → WMMA (AI Accelerator) |
| Ray Accelerator | 1세대 → 2세대 (~1.5×) |
| 클럭 | 단일 → 프론트엔드/셰이더 디커플링 |
| AV1 | 디코드만 → 인코드/디코드 |
| DisplayPort | 1.4 → 2.1 |
| CU (플래그십) | 80 → 96 |
| VRAM (플래그십) | 16GB → 24GB |

| | RX 7900 XTX (RDNA 3) | RTX 4080 (Ada) |
|:---|:---:|:---:|
| FP32 피크 | ~61 TFLOPS | ~48.7 TFLOPS |
| 메모리 BW | 960 GB/s | 716.8 GB/s |
| 래스터 4K | 대등~우세 | 기준 |
| 레이 트레이싱 | 2세대, 열세 | 3세대, 우세 |
| 프레임 생성 | FSR 3 (SW) | DLSS 3 (HW) |
| 전력 효율 | 열세 | 우세 |
| 출시가 | $999 | $1,199 |

RDNA 3는 칩렛으로 GPU 제조 경제학을 바꿨다. 로직과 캐시/IO를 공정별로 분리해 값비싼 5nm 면적을 절약했다. Dual-Issue와 WMMA로 연산 밀도를 높였다. 그러나 Ada의 3세대 RT Core와 DLSS 3 앞에서 레이 트레이싱과 프레임 생성의 격차는 좁혀지지 않았고, 칩렛 오버헤드로 전력 효율에서도 뒤처졌다.

다음 글: [RDNA 4 - Navi 48, 3세대 Ray Accelerator, FSR 4 ML 업스케일링](/2026-07-13-amd-gpu-arch-4-rdna4-kr/)
