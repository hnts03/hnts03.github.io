---
layout: post
title: "GPU 아키텍처 #9: Blackwell - FP4 Tensor Core와 멀티다이 설계"
subtitle: "MXFP8 미세조정, NV-HBI 2-다이 MCM, DLSS 4 다중 프레임 생성"
tags: [GPU, Architecture, CUDA, NVIDIA, Blackwell, TensorCore, NVLink, Computer-Architecture]
lang: kr
translation-url: /2026-07-08-gpu-arch-9-blackwell-en/
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
| 6 | [Ampere - Sparsity 가속과 MIG](/2026-07-07-gpu-arch-6-ampere-kr/) |
| 7 | [Hopper - Transformer Engine과 FP8](/2026-07-07-gpu-arch-7-hopper-kr/) |
| 8 | [Ada Lovelace - 3세대 RT Core와 96MB L2](/2026-07-07-gpu-arch-8-ada-lovelace-kr/) |
| **9** | **Blackwell - FP4 Tensor Core와 멀티다이 설계** |
| 10 | GPU 메모리 시스템과 최적화 |

---

## Hopper/Ada 이후의 과제

Hopper H100은 FP8 Transformer Engine으로 LLM 학습 처리량을 극적으로 높였다. 그러나 두 가지 한계가 남았다.

첫 번째는 추론 비용이다. FP8은 학습과 추론 모두에서 유효하지만, 100B 이상 파라미터 모델이 표준이 되면서 더 낮은 비트폭 없이는 단일 가속기에서 처리할 수 있는 모델 크기에 한계가 있었다. 4비트 양자화(INT4, FP4)는 소프트웨어 수준에서 시도됐지만, 하드웨어 TC 지원이 없어 속도 이득이 제한적이었다.

두 번째는 HBM 용량 한계다. H100 SXM5는 80GB HBM3를 탑재한다. GPT-4급 모델을 추론하려면 여러 장의 H100이 텐서 병렬로 협력해야 했다. 단일 가속기에서 더 큰 모델을 처리하려면 메모리 용량을 2배 이상 늘려야 했다.

Blackwell(2024)은 데이터센터와 소비자 양쪽에서 동시에 접근했다. 데이터센터용 **GB100**은 2-다이 MCM(Multi-Chip Module)으로 기존의 단일 다이 한계를 넘어섰다. 소비자용 **GB202**는 GDDR7과 DLSS 4 다중 프레임 생성으로 소비자 GPU의 새 기준을 세웠다.

---

## 다이 스펙

### 데이터센터: GB100 vs GH100

| | GH100 (Hopper, H100 SXM5) | GB100 (Blackwell, B200 SXM) |
|:---|:---:|:---:|
| 공정 | TSMC 4nm (N4) | **TSMC 4NP** |
| 다이 구성 | 단일 다이 | **2-다이 MCM** |
| 트랜지스터 | 80B | **208B** |
| 활성 SM (H100/B200) | 132 | **~168** |
| FP32/SM | 128 | 128 |
| TC 세대 | 4세대 | **5세대** |
| HBM 세대 | HBM3 | **HBM3e** |
| VRAM | 80GB | **192GB** |
| 메모리 대역폭 | 3.35 TB/s | **~8 TB/s** |
| NVLink | 4.0 (900 GB/s) | **5.0 (1,800 GB/s)** |

### 소비자: GB202 vs AD102

| | AD102 (Ada, RTX 4090) | GB202 (Blackwell, RTX 5090) |
|:---|:---:|:---:|
| 공정 | TSMC 4N | **TSMC 4NP** |
| 전체 SM 수 | 144 | **~170** |
| 활성 SM (RTX 기준) | 128 | **~170** |
| FP32/SM | 128 | 128 |
| TC 세대 | 4세대 | **5세대** |
| RT Core 세대 | 3세대 | **4세대** |
| DRAM 타입 | GDDR6X | **GDDR7** |
| 메모리 버스 | 384-bit | **512-bit** |
| VRAM | 24GB | **32GB** |
| 메모리 대역폭 | 1,008 GB/s | **1,792 GB/s** |

---

## 2-다이 MCM 아키텍처 (데이터센터 GB100)

Blackwell 데이터센터 GPU의 가장 큰 구조적 변화다. GB100은 두 개의 Blackwell 다이를 하나의 패키지 안에 집적한 **MCM(Multi-Chip Module)** 설계를 채택했다.

```
GB100 패키지 레이아웃
┌─────────────────────────────────────────────────────┐
│  Blackwell Die 0           Blackwell Die 1          │
│  (SM 절반 + HBM3e 절반)    (SM 절반 + HBM3e 절반)   │
│                                                     │
│         ◄──── NV-HBI ────►                          │
│       (칩 간 인터커넥트)                              │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │  HBM3e ×4            HBM3e ×4               │   │
│  │  (96GB)              (96GB)                 │   │
│  └──────────────────────────────────────────────┘   │
│  총 HBM3e: 192GB / 8,192-bit 버스 / ~8 TB/s         │
└─────────────────────────────────────────────────────┘
```

**NV-HBI(NVIDIA High Bandwidth Interconnect)**는 두 다이 사이의 칩 간 연결이다. 소프트웨어 관점에서 두 다이는 하나의 통합 GPU로 보인다. CUDA 커널은 다이 경계를 인식하지 않으며, 메모리 주소 공간도 단일 192GB 공간이다.

이 설계의 이점:
- 단일 다이로는 도달하기 어려운 메모리 용량(192GB)과 대역폭(~8 TB/s)을 달성
- 수율(yield) 측면에서 작은 다이 두 개가 큰 단일 다이보다 생산 효율이 높음

비교: Ada AD102는 76.3B 트랜지스터의 단일 다이다. GB100은 2-다이로 208B 트랜지스터를 달성해 단일 다이 대비 2.7배 트랜지스터를 확보했다.

![Blackwell B200 vs Hopper H100 SXM5 주요 지표 비교](/assets/img/posts/gpu-arch-9/dc-compare.png)

---

## 5세대 Tensor Core: FP4와 MXFP8

### FP4 (E2M1)

**FP4**는 Blackwell이 처음 하드웨어 TC에서 지원하는 4비트 부동소수점 형식이다.

```
FP32  (32비트): 부호 1 | 지수 8 | 가수 23
FP16  (16비트): 부호 1 | 지수 5 | 가수 10
FP8 E4M3 (8비트): 부호 1 | 지수 4 | 가수 3
FP4 E2M1 (4비트): 부호 1 | 지수 2 | 가수 1   ← Blackwell 신규
```

FP4 E2M1은 표현 가능한 값의 수가 극히 제한적이다(부호당 8가지 비영 값). 따라서 모델의 가중치를 FP4로 양자화할 때 표현 범위를 잘 맞춰야 한다. 이를 위해 MXFP4(microscaling FP4)가 함께 사용된다.

처리량 관계:
```
FP32 (비TC)  : 기준
FP16 TC Dense: ~4× FP32
FP8 TC Dense : ~8× FP32 (Hopper부터)
FP4 TC Dense : ~16× FP32 (Blackwell 신규)
```

FP4 TC는 같은 하드웨어에서 FP8 대비 2배, FP16 대비 4배의 처리량을 낸다. 대규모 추론에서 모델이 FP4로 충분히 정확하게 양자화될 수 있다면, 단일 가속기에서 처리할 수 있는 모델 크기가 FP8 대비 2배 늘어난다.

### MXFP8 - 미세 조정 스케일링

Hopper의 Transformer Engine은 텐서 단위로 하나의 스케일 팩터(scaling factor)를 적용했다. 값의 범위가 넓은 텐서에서 일부 값이 FP8 표현 범위를 벗어나면 오차가 커진다.

**MXFP(MicroScaling Floating Point)**는 OCP(Open Compute Project) 표준 형식이다. 고정된 크기의 블록(32개 요소 단위)마다 별도의 스케일 팩터를 사용한다.

```
기존 FP8 (Hopper Transformer Engine):
┌────────────────────────────────┐
│  텐서 전체 → 스케일 팩터 1개   │
│  값 범위가 넓으면 오차 증가    │
└────────────────────────────────┘

MXFP8 (Blackwell):
┌────────┐┌────────┐┌────────┐
│ 블록 0  ││ 블록 1  ││ 블록 2  │  ← 각 블록 32요소
│ scale 0 ││ scale 1 ││ scale 2 │  ← 블록마다 별도 스케일
└────────┘└────────┘└────────┘
→ 지역적 값 분포에 최적화된 정밀도 유지
```

MXFP8은 MXFP4, MXFP6도 포함한다. 블록 단위 스케일링이므로 Hopper Transformer Engine의 동적 스케일 탐색보다 안정적이며, 소프트웨어 구현도 단순해진다.

5세대 TC는 FP4, MXFP4, MXFP6, MXFP8, FP8, FP16, BF16, TF32, INT8을 모두 지원한다.

---

## SM 구조

Blackwell SM의 기본 구조는 Ada와 동일한 4-서브코어 설계를 유지한다. 변경은 TC와 RT Core 세대다.

```
Blackwell SM (GB202, CC 10.0)
┌─────────────────────────────────────────────────┐
│  서브코어 0               서브코어 1             │
│  Warp Scheduler × 1       Warp Scheduler × 1    │
│  FP32 × 16 + FP32/INT32 × 16  (서브코어당 32)  │
│  Tensor Core × 1 (5세대)  Tensor Core × 1       │
│  LD/ST × 8 | SFU × 4     LD/ST × 8 | SFU × 4  │
├─────────────────────────────────────────────────┤
│  서브코어 2               서브코어 3             │
│  (위와 동일 구조)         (위와 동일 구조)       │
├─────────────────────────────────────────────────┤
│  RT Core × 1 (4세대, SM 전체에 1개)             │
├─────────────────────────────────────────────────┤
│  L1 캐시 + Shared Memory  (설정 가능)           │
│  레지스터 파일             256KB                 │
└─────────────────────────────────────────────────┘

SM 전체 합산:
  FP32: 128개 | TC: 4개 (5세대) | RT Core: 1개 (4세대)
  LD/ST: 32개 | SFU: 16개
```

Ada에서 Blackwell으로의 SM 변경 사항:

| 항목 | AD102 (Ada, CC 8.9) | GB202 (Blackwell, CC 10.0) |
|:---|:---:|:---:|
| FP32/SM | 128 | 128 |
| TC 세대 | 4세대 | **5세대 (FP4, MXFP8)** |
| RT Core 세대 | 3세대 | **4세대** |
| FP4 TC | 없음 | **있음** |
| LD/ST | 32 | 32 |
| 레지스터 파일 | 256KB | 256KB |

---

## 소비자 혁신: DLSS 4와 Neural Rendering

### DLSS 4 Multi-Frame Generation

Ada DLSS 3는 렌더링된 프레임 사이에 AI 프레임 1개를 삽입했다. Blackwell DLSS 4는 **Multi-Frame Generation(MFG)**으로 최대 3개의 AI 프레임을 삽입한다.

```
DLSS 3 (Ada):
렌더 → [AI×1] → 렌더 → [AI×1] → 렌더 ...
표시 프레임: 렌더 1 + AI 1 = 2배

DLSS 4 MFG (Blackwell):
렌더 → [AI×3] → 렌더 → [AI×3] → 렌더 ...
표시 프레임: 렌더 1 + AI 3 = 4배
```

DLSS SR(해상도 업스케일링)까지 합산하면, 예를 들어 1080p를 네이티브로 렌더링해 4K로 업스케일링한 뒤 MFG로 4배 하면 실제 렌더링 부하는 1080p 25fps에 불과하지만 화면에는 4K 100fps가 표시된다.

MFG 배율이 높아지면 AI 생성 프레임의 비율이 늘어나므로, 입력 지연이 누적된다. NVIDIA Reflex와 함께 사용해 렌더링 큐 깊이를 줄여야 한다.

### Neural Shaders

Blackwell에서 처음 도입된 렌더링 개념이다. HLSL 셰이더 코드 내에서 소형 신경망(tiny neural network) 추론을 직접 실행할 수 있다. SM의 Tensor Core가 셰이더 실행 도중 호출된다.

```
기존 렌더링 파이프라인:
  래스터화 → 셰이더(CUDA Core) → 출력

Neural Shader (Blackwell):
  래스터화 → 셰이더(CUDA Core) ─┐
                                 ├─ Tensor Core (소형 NN 추론)
                                 └─ 출력
```

활용 예시:
- 픽셀당 조명 모델을 신경망으로 근사 (전통적 BRDF보다 복잡한 재질 표현)
- 노이즈 제거(denoising)를 셰이더 패스 안으로 통합

### Neural Texture Compression

기존 텍스처는 BC7, ASTC 같은 블록 압축 형식으로 저장한다. Neural Texture Compression은 소형 신경망이 디코더 역할을 한다. 같은 VRAM 용량에 더 높은 품질의 텍스처를 담거나, 동일 품질을 더 적은 VRAM으로 유지할 수 있다.

디코딩은 텍스처 샘플링 시 Tensor Core가 담당한다. 소프트웨어 관점에서는 기존 텍스처 API와 동일하게 사용한다.

---

## 스케줄링

Blackwell SM의 Warp 스케줄링 모델은 Ada와 동일하다. 4개의 독립 Warp 스케줄러, 독립 스레드 스케줄링(Volta에서 도입), SER(Ada에서 도입)을 모두 계승한다.

Compute Capability 10.0의 점유율 한계는 공개 문서 기준 이전 세대와 유사한 수준이다.

---

## 인터커넥트 및 외부 채널

### NVLink 5.0 (데이터센터 GB100)

| 세대 | BW (양방향 / GPU) | 최초 아키텍처 |
|:---|:---:|:---:|
| NVLink 1.0 | 160 GB/s | Pascal GP100 |
| NVLink 2.0 | 300 GB/s | Volta GV100 |
| NVLink 3.0 | 600 GB/s | Ampere GA100 |
| NVLink 4.0 | 900 GB/s | Hopper GH100 |
| **NVLink 5.0** | **1,800 GB/s** | **Blackwell GB100** |

NVLink 5.0은 이전 세대 대비 2배 대역폭을 제공한다. GB200 NVL72 구성에서는 72개의 B200 GPU가 NVLink 5.0 스위치로 연결된다. 72-GPU 도메인 내에서 AllReduce 통신이 PCIe를 거치지 않고 NVLink 패브릭 위에서 처리된다.

### PCIe

| 아키텍처 | PCIe | 비고 |
|:---|:---:|:---|
| Ada (RTX 4090) | 4.0 x16 | - |
| Hopper (H100) | 5.0 x16 | 데이터센터 최초 PCIe 5.0 |
| **Blackwell (RTX 5090)** | **5.0 x16** | **소비자 최초 PCIe 5.0** |

Blackwell 소비자 GPU는 Ada의 PCIe 4.0에서 PCIe 5.0으로 전환했다. Hopper가 데이터센터에서 먼저 PCIe 5.0을 도입한 데 이어, Blackwell이 소비자 GPU에 처음 적용했다.

### 메모리 서브시스템

| 제품 | DRAM | 버스 폭 | 대역폭 | 용량 |
|:---|:---:|:---:|:---:|:---:|
| RTX 4090 (AD102) | GDDR6X | 384-bit | 1,008 GB/s | 24GB |
| **RTX 5090 (GB202)** | **GDDR7** | **512-bit** | **1,792 GB/s** | **32GB** |
| H100 SXM5 (GH100) | HBM3 | 5,120-bit | 3.35 TB/s | 80GB |
| **B200 SXM (GB100)** | **HBM3e** | **8,192-bit** | **~8 TB/s** | **192GB** |

RTX 5090의 GDDR7 1,792 GB/s는 RTX 4090 GDDR6X 대비 1.78배다.

![Blackwell RTX 5090 vs Ada RTX 4090 소비자 주요 지표 비교](/assets/img/posts/gpu-arch-9/consumer-compare.png)

B200 SXM의 ~8 TB/s 메모리 대역폭은 H100 SXM5(3.35 TB/s) 대비 2.4배다. 2-다이 MCM이 HBM3e 스택을 8개(4개씩)로 늘릴 수 있었기 때문이다.

### NVENC / NVDEC 및 디스플레이

| 제품 | NVENC 수 | AV1 인코딩 | 디스플레이 |
|:---|:---:|:---:|:---|
| RTX 4090 (AD102) | 2 (dual) | 지원 | DP 1.4a ×3, HDMI 2.1 ×1 |
| **RTX 5090 (GB202)** | **2 (dual)** | 지원 | **DP 2.1b ×3, HDMI 2.1 ×1** |
| B200 SXM (GB100) | 없음 | - | 없음 |

RTX 5090은 DisplayPort 2.1b로 업그레이드됐다. DP 2.1b는 DSC 없이 8K@60Hz를 단일 케이블로 지원한다. NVENC 수는 AD102와 동일하게 2개다.

---

## 정리

| 항목 | GH100 / AD102 | GB100 / GB202 |
|:---|:---:|:---:|
| 공정 | TSMC 4nm (N4) | **TSMC 4NP** |
| 다이 구성 | 단일 | **2-다이 MCM (GB100)** |
| TC 세대 | 4세대 | **5세대 (FP4, MXFP8)** |
| FP4 TC | 없음 | **있음** |
| RT Core 세대 | 3세대 (Ada) | **4세대** |
| 메모리 대역폭 | 3.35 TB/s / 1,008 GB/s | **~8 TB/s / 1,792 GB/s** |
| VRAM | 80GB / 24GB | **192GB / 32GB** |
| NVLink | 4.0 (900 GB/s) | **5.0 (1,800 GB/s)** |
| PCIe (소비자) | 4.0 x16 (Ada) | **5.0 x16** |
| DLSS | 3 (Frame Gen ×1) | **4 (Frame Gen ×3)** |
| Neural Shaders | 없음 | **있음** |

Blackwell은 데이터센터에서 2-다이 MCM으로 단일 가속기의 물리적 한계를 넘어섰고, FP4 TC로 추론 처리량을 FP8 대비 2배 높였다. 소비자 측에서는 GDDR7, PCIe 5.0, DLSS 4 MFG(×3)로 Ada 대비 전 영역에서 성능을 끌어올렸다.

---

## 참고 자료

- NVIDIA. *NVIDIA Blackwell Architecture Technical Brief*. 2024.
- NVIDIA. *NVIDIA GB200 NVL72 Platform Overview*. 2024.
- NVIDIA. *GeForce RTX 5090 Product Specifications*. 2025.
- NVIDIA. *DLSS 4 with Multi Frame Generation Technical Overview*. 2025.
- OCP. *MX Microscaling Formats Specification*. Open Compute Project, 2023.
