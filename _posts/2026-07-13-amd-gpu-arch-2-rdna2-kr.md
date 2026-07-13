---
layout: post
title: "AMD GPU 아키텍처 #2: RDNA 2"
subtitle: "Ray Accelerator, Infinity Cache, Big Navi - 그리고 NVIDIA Ampere와의 정면 대결"
tags: [GPU, Architecture, AMD, RDNA, Computer-Architecture]
lang: kr
translation-url: /2026-07-13-amd-gpu-arch-2-rdna2-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 개요 | [RDNA / CDNA 전 세대 타임라인](/2026-07-09-amd-gpu-arch-overview-kr/) | ✅ |
| 1 | [RDNA 1 - Wave32, WGP, 7nm](/2026-07-09-amd-gpu-arch-1-rdna1-kr/) | ✅ |
| 2 | RDNA 2 - Ray Accelerator, Infinity Cache, Ampere 대결 | ✅ |
| 3 | RDNA 3 - 칩렛(GCD+MCD), 듀얼-이슈 셰이더 | 🔲 |

---

## RDNA 1이 남긴 숙제

RDNA 1은 GCN에서 벗어나는 데 성공했다. Wave32, WGP, 캐시 재설계로 클럭과 효율을 끌어올렸고, NVIDIA Turing과 래스터라이제이션에서 대등하게 경쟁했다. 그러나 두 가지 기능이 빠졌다.

- **레이 트레이싱**: Turing은 RT Core로 BVH 순회와 광선-교차 판정을 하드웨어에서 처리했다. RDNA 1에는 RT 전용 하드웨어가 없었다.
- **업스케일링**: Turing의 Tensor Core는 DLSS를 가능하게 했다. RDNA 1에는 대응 기술이 없었다.

**RDNA 2(Navi 21, 2020년 11월)**는 이 두 항목을 모두 추가했다.

---

## Ray Accelerator: AMD 최초 하드웨어 RT

RDNA 1의 CU는 레이 트레이싱을 셰이더 유닛에서 소프트웨어로만 처리했다. RDNA 2는 CU당 **Ray Accelerator** 1개를 추가했다.

```
RDNA 2 CU 구조:
┌─────────────────────────────────────────────────┐
│                      CU                         │
│  ┌─────────────────┐   ┌─────────────────┐      │
│  │    SIMD32 [0]   │   │    SIMD32 [1]   │      │
│  │    32 FP32      │   │    32 FP32      │      │
│  └─────────────────┘   └─────────────────┘      │
│  LDS 32KB                                       │
│  ┌───────────────────────────────────────────┐  │
│  │           Ray Accelerator (×1)            │  │
│  │  BVH 순회 + 박스-광선 + 삼각형 교차 판정  │  │
│  │  고정 기능 하드웨어로 처리                │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

Ray Accelerator가 처리하는 연산:
- **BVH(Bounding Volume Hierarchy) 순회**: 광선이 씬의 어느 오브젝트와 가깝게 지나가는지 탐색
- **박스-광선 교차 판정**: AABB(축 정렬 경계 박스)와 광선의 교차 여부 계산
- **삼각형-광선 교차 판정**: 최종 삼각형 레벨 교차 판정

이 연산들을 SIMD32 범용 유닛에서 처리하던 것을 고정 기능 하드웨어로 옮겼다. 셰이더 유닛은 셰이딩 연산에 집중하고, BVH 순회는 Ray Accelerator가 병렬로 처리한다.

Navi 21(80 CU) 전체: **80개의 Ray Accelerator**.

### Turing RT Core와의 구조 비교

| 항목 | Turing RT Core | RDNA 2 Ray Accelerator |
|:---|:---:|:---:|
| 세대 | 1세대 | 1세대 |
| 위치 | SM당 1개 | CU당 1개 |
| BVH 순회 | 전용 HW | 전용 HW |
| 박스-광선 교차 | 전용 HW | 전용 HW |
| 삼각형 교차 | 전용 HW | 전용 HW |
| DXR 1.1 (Inline RT) | 미지원 | 지원 |

구조는 유사하다. 실제 게임 RT 성능에서 Turing과 RDNA 2는 타이틀에 따라 엇비슷한 경우도 있었다. 동급 Ampere(RTX 30, 2세대 RT Core) 대비로는 RDNA 2가 열세였다.

---

## Infinity Cache: GDDR6 대역폭 한계를 우회하다

RDNA 2에서 가장 독창적인 설계다.

고대역폭 메모리(HBM)는 높은 대역폭을 제공하지만 가격이 높고 패키지 면적이 크다. GDDR6는 저렴하지만 대역폭이 제한된다. AMD는 제3의 방법을 선택했다. 대용량 온다이 L3 캐시를 추가해 GDDR6 접근 빈도 자체를 줄이는 것이다.

```
RDNA 1 메모리 경로:
CU → L0(WGP 128KB) → GL1(SA 128KB) → L2(4MB) → GDDR6 256-bit 448 GB/s

RDNA 2 메모리 경로:
CU → L0(WGP 128KB) → GL1(SA 128KB) → L2(4MB) → Infinity Cache(128MB) → GDDR6 256-bit 512 GB/s
                                                         ↑
                                             캐시 히트 시 여기서 종료
```

Navi 21의 Infinity Cache는 온다이 **128MB SRAM**이다.

대역폭 분석:
- GDDR6 인터페이스: 256-bit × 16 Gbps = **512 GB/s** (원시 대역폭)
- Infinity Cache 히트 시 내부 대역폭: AMD 발표 기준 ~**1,664 GB/s** 유효 대역폭 (히트율 100% 가정)
- 실제 유효 대역폭: 히트율에 따라 결정

```
해상도별 캐시 히트율 경향:
1080p: 히트율 높음 → 유효 BW ≈ HBM2e 수준 확보 가능
1440p: 히트율 중간 → 대역폭 이득 감소
4K:    히트율 낮음 → 원시 GDDR6 512 GB/s에 수렴
```

이 전략으로 AMD는 HBM 없이도 1080p/1440p 게임에서 경쟁력 있는 유효 대역폭을 달성했다. Infinity Cache가 4K에서 효과가 줄어드는 것은 RDNA 2의 구조적 한계이기도 하다.

---

## Navi 21 다이: Big Navi

RDNA 1은 중급 다이(Navi 10, 40 CU)만 있었다. RDNA 2에서 AMD는 처음으로 **대형 다이(Navi 21, 80 CU)**를 투입했다. "Big Navi"라는 별칭이 붙은 배경이다.

```
Navi 21 다이 구성:
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   SE 0   │  │   SE 1   │  │   SE 2   │  │   SE 3   │   │
│  │ SA0│ SA1 │  │ SA0│ SA1 │  │ SA0│ SA1 │  │ SA0│ SA1 │   │
│  │5WGP│5WGP │  │5WGP│5WGP │  │5WGP│5WGP │  │5WGP│5WGP │   │
│  │  (10 CU) │  │  (10 CU) │  │  (10 CU) │  │  (10 CU) │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                  SE 4개 × 20 CU = 80 CU                      │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  L2 캐시 4MB  |  Infinity Cache 128MB (온다이 SRAM) │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  [GDDR6 MC × 8, 256-bit]   [Display Engine]                │
└──────────────────────────────────────────────────────────────┘
```

| 항목 | Navi 10 (RDNA 1) | Navi 21 (RDNA 2) |
|:---|:---:|:---:|
| 공정 | TSMC 7nm | TSMC 7nm |
| 다이 면적 | 251mm² | ~520mm² |
| 트랜지스터 | 103억 | 268억 |
| CU (풀다이) | 40 | 80 |
| Infinity Cache | 없음 | 128MB |
| Ray Accelerator | 없음 | 80개 |

**RX 6900 XT (Navi 21 풀다이):**

| 항목 | 값 |
|:---|:---|
| CU | 80 |
| 셰이더 프로세서 | 5,120 |
| 부스트 클럭 | ~2,250 MHz |
| FP32 성능 | 23.04 TFLOPS |
| VRAM | GDDR6 16GB |
| 메모리 대역폭 | 512 GB/s (원시) |
| TDP | 300W |
| 출시가 | $999 |

부스트 클럭 2,250 MHz는 RDNA 1 RX 5700 XT(1,905 MHz) 대비 약 18% 높다. 아키텍처 개선과 공정 전압 최적화의 결과다.

---

## Smart Access Memory

PCIe 규격의 **Resizable BAR(Base Address Register)** 기능을 AMD가 브랜드화한 것이다. CPU가 GPU VRAM에 얼마나 직접 주소 지정할 수 있는지를 제어한다.

```
기존 BAR 제한 (256MB 고정):
CPU ──── PCIe ────► GPU VRAM 16GB
         [256MB 창]만 직접 접근, 나머지는 창 이동으로 처리

SAM (Resizable BAR):
CPU ──── PCIe ────► GPU VRAM 16GB
         전체 16GB 직접 주소 지정 가능
```

적용 조건: AMD RDNA 2 GPU + AMD Ryzen 5000 이상 + BIOS 지원 마더보드. 게임에 따라 최대 ~15% 성능 향상이 측정됐다. NVIDIA도 이후 RTX 30 시리즈에 동일 기능을 "Resizable BAR" 명칭으로 지원했다.

---

## DirectX 12 Ultimate 완전 지원

RDNA 2는 Microsoft의 DirectX 12 Ultimate 기능 4종을 모두 지원하는 최초의 AMD GPU다.

| DX12U 기능 | RDNA 1 | RDNA 2 |
|:---|:---:|:---:|
| DXR (레이 트레이싱) | 소프트웨어 폴백 | 하드웨어 (Ray Accelerator) |
| Mesh Shader | 미지원 | 지원 |
| Variable Rate Shading | Tier 1 | Tier 2 |
| Sampler Feedback | 미지원 | 지원 |

**Mesh Shader**는 기하 처리 파이프라인을 완전히 프로그래머블하게 만든다. 기존 Input Assembler → Vertex Shader → Geometry Shader 단계를 대체할 수 있다. LOD(레벨 오브 디테일)와 오클루전 컬링을 GPU에서 직접 수행한다.

**VRS Tier 2**는 삼각형 단위로 셰이딩 레이트를 지정할 수 있다. 움직임이 없거나 주변부인 픽셀의 셰이딩 품질을 낮춰 성능을 확보하는 방식이다.

---

## 콘솔 채택: Xbox Series X, PlayStation 5

RDNA 2 출시와 같은 시기인 2020년 11월, 두 차세대 콘솔이 출시됐다.

| 콘솔 | GPU | CU 수 | 클럭 | FP32 |
|:---|:---:|:---:|:---:|:---:|
| Xbox Series X | RDNA 2 | 52 CU | 1,825 MHz | 12.0 TFLOPS |
| PlayStation 5 | RDNA 2 | 36 CU | 2,233 MHz | 10.3 TFLOPS |

콘솔 개발자들이 RDNA 2 기반 코드를 작성하면, 동일 아키텍처인 PC GPU도 최적화 혜택을 받는다. Ray Accelerator, Mesh Shader, VRS Tier 2가 PC-콘솔 공통 기능이 됐다. 이는 RDNA 2 기능을 게임 개발자들이 적극 채택하는 동기로 작용했다.

---

## NVIDIA Ampere와의 비교

RDNA 2 출시 직전인 2020년 9월, NVIDIA는 **Ampere(GA102, RTX 30)** 를 출시했다. Turing 대비 주요 변화는 SM당 FP32 코어 증가와 2세대 RT Core 도입이다.

```
Turing SM (TU104):                    Ampere SM (GA102):
┌──────────────────────────┐          ┌──────────────────────────┐
│  FP32 × 64               │          │  FP32 × 128              │
│  INT32 × 64 (동시 가능)   │          │  INT32 × 64 (동시 가능)  │
│  Tensor Core 2세대 × 8    │          │  Tensor Core 3세대 × 4   │
│  RT Core 1세대 × 1        │          │  RT Core 2세대 × 1       │
└──────────────────────────┘          └──────────────────────────┘
SM당 FP32: 64                         SM당 FP32: 128 (2배)
```

Ampere의 SM당 FP32 처리량은 Turing의 2배다. RT Core는 2세대로 교체되며 BVH 처리 속도가 크게 향상됐다.

### 핵심 사양 비교

![RX 6900 XT (RDNA 2) vs RTX 3080 10G (Ampere)](/assets/img/posts/amd-gpu-arch-2-rdna2/spec-compare.png)

| | RX 6900 XT (RDNA 2) | RTX 3080 10G (Ampere) | RTX 3090 (Ampere) |
|:---|:---:|:---:|:---:|
| 공정 | TSMC 7nm | Samsung 8nm | Samsung 8nm |
| 다이 | Navi 21 (~520mm²) | GA102 (628mm²) | GA102 (628mm²) |
| 셰이더 | 5,120 SP | 8,704 CUDA | 10,496 CUDA |
| FP32 TFLOPS | 23.04 | 29.77 | 35.58 |
| 메모리 인터페이스 | GDDR6 256-bit | GDDR6X 320-bit | GDDR6X 384-bit |
| 원시 메모리 BW | 512 GB/s | 760 GB/s | 936 GB/s |
| 유효 메모리 BW | ~1,664 GB/s (IC 포함) | 760 GB/s | 936 GB/s |
| VRAM | 16GB | 10GB | 24GB |
| RT 세대 | 1세대 | 2세대 | 2세대 |
| 행렬 가속 | 없음 | Tensor Core 3세대 | Tensor Core 3세대 |
| TDP | 300W | 320W | 350W |
| 출시가 | $999 | $699 | $1,499 |

### 영역별 우열

**래스터라이제이션**

1080p/1440p 기준, RX 6900 XT와 RTX 3080은 게임에 따라 엇비슷하다. Infinity Cache의 유효 대역폭 이점이 저해상도일수록 두드러지기 때문이다. 4K에서는 원시 대역폭의 차이로 RTX 3080이 앞서는 경향이 있다.

**레이 트레이싱**

RDNA 2 Ray Accelerator는 1세대, Ampere RT Core는 2세대다. RT 활성화 게임에서 RTX 3080이 RX 6900 XT보다 약 30~50% 앞서는 경우가 일반적이었다. DXR 1.1(Inline Ray Tracing) 지원은 RDNA 2가 추가했으나 절대 성능 차이는 컸다.

**업스케일링**

DLSS 2.0은 Tensor Core에서 실행되는 딥러닝 기반 업스케일링이다. RDNA 2에서는 사용 불가능하다.

AMD는 **FSR 1.0(FidelityFX Super Resolution, 2021년 6월)**으로 대응했다. FSR 1.0은 Easu(에지 적응형 공간 업스케일링) + Rcas(선명화) 두 단계의 공간 기반 알고리즘이다. AI 추론 하드웨어가 필요 없어 AMD GPU 외에 NVIDIA GPU, 콘솔, 구형 하드웨어 모두에서 동작한다. 반면 화질은 DLSS 2.0에 미치지 못했다.

**메모리 용량**

RTX 3080 10GB는 출시 당시 VRAM 용량 논란이 있었다. RX 6900 XT 16GB는 고해상도 텍스처와 미래 대응 측면에서 명확한 우위였다. (NVIDIA는 이후 RTX 3080 12GB를 출시해 보완했다.)

---

## 소프트웨어

**FidelityFX 라이브러리 확장**

AMD는 RDNA 2 시기에 FidelityFX 오픈소스 효과 라이브러리를 본격 확장했다.

| 기능 | 설명 |
|:---|:---|
| FSR 1.0 (2021.06) | 공간 업스케일링 (Easu + Rcas), 하드웨어 비의존 |
| CAS | 대비 적응형 선명화 |
| CACAO | 앰비언트 오클루전 |
| Denoiser | RT 노이즈 제거 |

FidelityFX의 모든 효과는 오픈소스로 공개돼 있다. NVIDIA GPU에서도 동작하며, 개발사가 자유롭게 통합할 수 있다. 이는 NVIDIA의 DLSS(폐쇄적, Tensor Core 전용)와 대조되는 전략이다.

**ROCm**

RDNA 2 시기 ROCm은 4.x 버전으로 진행됐으나, 컴퓨트 워크로드의 주력 타깃은 CDNA 1(Arcturus, MI100)이었다. RDNA 2에서 일부 컴퓨트 지원이 개선됐으나, HPC/ML 용도로는 RDNA 아키텍처보다 CDNA를 사용하는 것이 일반적이었다.

---

## 요약

| 항목 | RDNA 1 대비 변화 |
|:---|:---|
| Ray Tracing | 소프트웨어 폴백 → Ray Accelerator (CU당 1개) |
| 캐시 추가 | 없음 → Infinity Cache 128MB (온다이 SRAM) |
| Mesh Shader | 미지원 → 지원 |
| VRS | Tier 1 → Tier 2 |
| SAM | 없음 → 지원 |
| CU 최대 | 40 → 80 (Big Navi) |
| 부스트 클럭 (플래그십) | ~1,905 MHz → ~2,250 MHz (+18%) |
| VRAM (플래그십) | 8GB → 16GB |
| 콘솔 기반 아키텍처 | 없음 → Xbox Series X / PS5 |

| | RX 6900 XT (RDNA 2) | RTX 3080 10G (Ampere) |
|:---|:---:|:---:|
| FP32 TFLOPS | 23.04 | 29.77 |
| 원시 메모리 BW | 512 GB/s | 760 GB/s |
| 유효 메모리 BW | ~1,664 GB/s (IC) | 760 GB/s |
| 래스터 1440p | 동급 | 동급 |
| 래스터 4K | 약간 열세 | 약간 우세 |
| 레이 트레이싱 | 1세대, 열세 | 2세대, 우세 |
| 업스케일링 | FSR 1.0 (공간 기반) | DLSS 2.0 (AI 기반) |
| VRAM | 16GB | 10GB |

RDNA 2는 RDNA 1이 남긴 RT 공백을 채웠다. Infinity Cache는 GDDR6의 한계를 우회하는 독창적인 해법이었고, Big Navi로 고성능 시장에도 진입했다. 그러나 Ampere의 2세대 RT Core와 DLSS 2.0 앞에서 RT와 AI 업스케일링의 격차는 한 세대로 좁혀지지 않았다.

다음 글: RDNA 3 - 칩렛(GCD+MCD), 듀얼-이슈 셰이더, 5nm 전환 (예정)
