---
layout: post
title: "GPU 아키텍처 #8: Ada Lovelace - 3세대 RT Core와 96MB L2"
subtitle: "Opacity Micromap, Shader Execution Reordering, DLSS 3 Frame Generation"
tags: [GPU, Architecture, CUDA, NVIDIA, AdaLovelace, RayTracing, TensorCore, Computer-Architecture]
lang: kr
translation-url: /2026-07-07-gpu-arch-8-ada-lovelace-en/
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
| **8** | **Ada Lovelace - 3세대 RT Core와 96MB L2** |
| 9 | GPU 메모리 시스템과 최적화 |

---

## Ampere 이후의 과제

GA102(RTX 30xx)는 2세대 RT Core로 실시간 레이트레이싱을 대중화했다. 하지만 두 가지 병목이 남았다.

첫 번째는 투명 재질이다. 유리, 나뭇잎, 알파 텍스처를 포함한 장면에서 광선이 삼각형에 닿으면 BVH 탐색을 멈추고 SM에서 AnyHit 셰이더를 실행해 실제로 불투명한지 확인했다. 이 과정이 RT Core 처리량을 낮췄다.

두 번째는 L2 캐시 부족이다. GA102의 L2는 6MB였다. 레이트레이싱은 BVH 탐색 경로가 광선마다 다르기 때문에 캐시 적중률이 낮다. 6MB로는 BVH의 상위 노드조차 온전히 담기 어렵다.

Ada Lovelace(AD102, 2022년 9월)는 3세대 RT Core, 96MB L2, 4세대 Tensor Core(FP8)로 이 두 문제를 동시에 공략했다.

---

## 다이 스펙

| | GA102 (Ampere, RTX 3090) | AD102 (Ada, RTX 4090) |
|:---|:---:|:---:|
| 공정 | Samsung 8nm | **TSMC 4N (4nm 급)** |
| 트랜지스터 | 28.3B | **76.3B** |
| 다이 면적 | 628mm² | 608mm² |
| 전체 SM 수 | 84 | **144** |
| 활성 SM (RTX 4090 기준) | 82 (RTX 3090) | **128** |
| FP32/SM | 128 | 128 |
| FP64/SM | 2 (1/64 비율) | 2 (1/64 비율) |
| TC 세대 | 3세대 | **4세대** |
| RT Core 세대 | 2세대 | **3세대** |
| L2 캐시 | 6MB | **96MB** |
| Compute Capability | 8.6 | **8.9** |
| 대표 제품 | RTX 3090 | **RTX 4090** |

같은 다이 면적에서 트랜지스터가 2.7배 늘었다. TSMC 4N 공정의 밀도 이점이다. SM당 FP32 수(128개)는 GA102와 동일하지만, SM 수(84 → 144)와 클럭(1,695 → 2,520 MHz)이 함께 올라가 FP32 처리량이 2.3배 증가했다.

![Ada (RTX 4090) vs Ampere (RTX 3090) 주요 지표 비교](/assets/img/posts/gpu-arch-8/perf-compare.png)

메모리 대역폭은 8% 증가에 그쳤지만 L2 캐시는 16배 늘었다. DRAM 접근 빈도를 줄이는 방향으로 설계했음을 보여주는 수치다.

---

## 3세대 RT Core

### 처리량 향상

3세대 RT Core는 BVH 교차 테스트 처리량을 2세대 대비 향상시켰다. 이와 함께 두 가지 전용 가속 엔진이 새로 추가됐다.

### Opacity Micromap Engine (OME)

**문제**: 투명 재질 처리 비용.

나뭇잎, 철조망, 불꽃 이펙트 같은 알파 텍스처 삼각형은 광선이 닿을 때마다 AnyHit 셰이더를 SM에서 실행해 투명한지 불투명한지 결정했다. AnyHit 셰이더 하나는 단순하지만, 수백만 개의 광선이 동시에 처리되는 상황에서는 RT Core 이용률을 크게 낮췄다.

**OME 해결**: 삼각형을 여러 마이크로삼각형으로 분할하고, 각 마이크로삼각형의 투명도를 2비트로 인코딩해 BVH에 직접 붙인다.

```
마이크로삼각형 상태: 00 = Opaque, 01 = Transparent, 10 = Unknown
```

RT Core는 BVH 탐색 중 이 2비트를 읽어 즉시 결정한다:
- `Opaque(00)`: AnyHit 없이 교차 확정
- `Transparent(01)`: 즉시 건너뜀
- `Unknown(10)`: 기존 방식대로 AnyHit 셰이더 호출

```
기존 방식:                              OME 적용:
광선 → 삼각형 교차                      광선 → 마이크로삼각형 교차
  → AnyHit 셰이더 (SM 실행)               → Opaque: 즉시 확정 (SM 불필요)
  → 투명도 판정                            → Transparent: 건너뜀
  → 확정 또는 건너뜀                       → Unknown: AnyHit 셰이더만 호출
```

수풀이나 유리가 많은 장면에서 AnyHit 호출 횟수를 대폭 줄인다. BVH 빌드 시 OME 데이터를 같이 생성하므로 VRAM 사용량이 약간 늘어나는 트레이드오프가 있다.

### Displaced Micro-Mesh Engine (DMME)

**문제**: 고디테일 기하 표현 비용.

바위, 지형, 캐릭터 피부처럼 미세한 요철이 있는 표면을 레이트레이싱으로 렌더링하려면 수백만 개의 삼각형이 필요했다. 삼각형이 많을수록 BVH가 커지고, 탐색 비용과 VRAM 사용량이 늘어났다.

**DMME 해결**: 저해상도 기본 메시 위에 변위(displacement) 맵을 정의한다. RT Core는 광선 교차 테스트 시 이 변위 맵을 적용해 마이크로삼각형 수준의 교차를 계산한다.

```
기존: 기본 메시 수천 폴리곤
      + 테셀레이션으로 수백만 삼각형 생성
      → 수백만 개 BVH 노드 → 큰 VRAM 사용

DMME: 기본 메시 수천 폴리곤
      + displacement map (압축 저장)
      → RT Core가 교차 시 절차적으로 디테일 계산
      → BVH 크기 감소 → VRAM 절감
```

---

## Shader Execution Reordering (SER)

Ada의 주요 하드웨어/소프트웨어 공동 최적화 기능이다.

**문제**: 레이트레이싱에서의 Warp Divergence.

Rasterization에서는 인접 픽셀이 같은 삼각형을 공유하는 경우가 많아 Warp 내 스레드들이 같은 셰이더를 실행한다. 레이트레이싱에서는 광선마다 BVH 탐색 경로가 다르고, 서로 다른 재질의 표면에 닿는다. Warp 내 32개 스레드가 서로 다른 ClosestHit 셰이더를 필요로 하면, 스레드 하나씩 순차 실행하는 것과 다를 바 없어진다.

**SER 해결**: GPU 하드웨어가 셰이더 호출을 버퍼에 쌓고, 동일한 셰이더가 필요한 교차 결과들을 묶어 처리한다.

```
기존 방식:
Warp 내 광선 A → 나무 재질 → NatureShader
Warp 내 광선 B → 돌 재질  → RockShader     ← 서로 다른 셰이더 → 분기 지속
Warp 내 광선 C → 유리 재질 → GlassShader

SER 적용:
광선들 교차 결과 → Hit Object 버퍼에 저장
                 → 셰이더 타입별 정렬
NatureShader × N개 교차 → Warp 전체가 NatureShader → 분기 없음
RockShader   × M개 교차 → Warp 전체가 RockShader   → 분기 없음
GlassShader  × K개 교차 → Warp 전체가 GlassShader  → 분기 없음
```

DXR(DirectX Raytracing) 1.2에서 `HitObject` API를 통해 SER에 참여한다. 셰이더 코드는 교차 결과를 `HitObject`로 받은 뒤 `ReorderThread()`를 호출해 GPU에 재정렬을 위임한다. 재정렬 완료 후 동일 셰이더 타입의 교차들이 같은 Warp에 모여 `Invoke()`로 실행된다.

NVIDIA 발표에 따르면 복잡한 레이트레이싱 장면에서 셰이더 처리량이 최대 2배 향상된다.

---

## 4세대 Tensor Core와 FP8

Ada의 4세대 Tensor Core는 Hopper와 동일한 세대다. FP8(E4M3, E5M2) 입력을 지원한다. FP8 형식의 비트 구조와 Transformer Engine 상세는 이전 포스트(Hopper)를 참조한다.

Ada 관점에서 핵심은 소비자 GPU에서 FP8 Tensor Core 연산이 처음 가능해졌다는 점이다. Hopper는 데이터센터 학습에 FP8을 도입했고, Ada는 같은 세대 TC로 소비자 GPU 추론에서 FP8을 활용할 수 있게 했다.

2:4 구조적 희소성(Ampere에서 도입)도 계속 지원한다.

| 연산 정밀도 | RTX 3090 (GA102) | RTX 4090 (AD102) |
|:---|:---:|:---:|
| FP32 CUDA Core | 35.6 TFLOPS | **82.6 TFLOPS** |
| GDDR6X 대역폭 | 936 GB/s | **1,008 GB/s** |
| FP8 TC (Dense) | 없음 | 지원 |
| FP16 TC (Sparse) | 지원 | 지원 |

---

## Ada SM 구조

Ada SM은 GA102와 동일한 4-서브코어 구조다. 변경 사항은 TC와 RT Core 세대뿐이다.

```
Ada SM (AD102, CC 8.9)
┌─────────────────────────────────────────────────┐
│  서브코어 0               서브코어 1             │
│  Warp Scheduler × 1       Warp Scheduler × 1    │
│  Dispatch Unit × 2        Dispatch Unit × 2     │
│  FP32 × 16 + FP32/INT32 × 16   (서브코어당 32)  │
│  Tensor Core × 1 (4세대)  Tensor Core × 1       │
│  LD/ST × 8 | SFU × 4     LD/ST × 8 | SFU × 4  │
├─────────────────────────────────────────────────┤
│  서브코어 2               서브코어 3             │
│  (위와 동일 구조)         (위와 동일 구조)       │
├─────────────────────────────────────────────────┤
│  RT Core × 1 (3세대, SM 전체에 1개)             │
├─────────────────────────────────────────────────┤
│  L1 캐시 + Shared Memory  128KB (설정 가능)     │
│  레지스터 파일             256KB                 │
└─────────────────────────────────────────────────┘

SM 전체 합산:
  FP32: 128개 | INT32: 64개 (dual-mode 유닛)
  TC: 4개 (4세대, FP8/FP16/BF16/TF32/INT8 지원)
  RT Core: 1개 (3세대, OME + DMME 지원)
  LD/ST: 32개 | SFU: 16개
```

GA102 SM과 비교:

| 항목 | GA102 (CC 8.6) | AD102 (CC 8.9) |
|:---|:---:|:---:|
| FP32/SM | 128 | 128 |
| INT32/SM | 64 | 64 |
| TC 세대/SM | 3세대 | **4세대** |
| RT Core/SM | 2세대 | **3세대** |
| LD/ST/SM | 32 | 32 |
| SFU/SM | 16 | 16 |
| L1+Shared/SM | 128KB | 128KB |
| 레지스터 파일/SM | 256KB | 256KB |
| 최대 Warps/SM | 48 | 48 |
| 최대 Blocks/SM | **16** | **24** |

최대 블록 수가 SM당 16에서 24로 늘었다. 블록 크기가 작은 커널에서 점유율(occupancy)을 높이는 데 유리하다.

---

## L2 캐시 96MB

GA102의 6MB에서 AD102의 96MB로 16배 증가다.

**왜 96MB인가?**

레이트레이싱에서 BVH 탐색 패턴은 광선마다 다르다. 가시성이 높은 오브젝트의 BVH 상위 노드는 반복 접근되지만, 6MB로는 이 노드들을 온전히 캐시에 유지할 수 없었다. 96MB는 중간 규모 장면의 BVH 상위 계층 전체를 캐시에 보유할 수 있다.

추론 측면에서도 유효하다. 수십억 파라미터 규모가 아닌 소형-중형 모델의 경우 활성값과 KV 캐시 일부가 96MB L2에 상주하면 HBM 접근 빈도가 줄어든다.

AD102의 L2는 물리적으로 여러 파티션으로 나뉘지만, 캐싱 정책 면에서 소프트웨어에는 단일 96MB 공간으로 노출된다.

```
GA102 L2: 6MB     RTX 3090 BVH 적중률: 낮음 → GDDR6X 행 접근 빈번
AD102 L2: 96MB    RTX 4090 BVH 상위 노드 상주 → GDDR6X 접근 감소
```

RTX 4090의 GDDR6X 대역폭이 RTX 3090 대비 8% 증가에 그쳤음에도 레이트레이싱 성능이 크게 향상된 이유 중 하나다.

---

## DLSS 3와 Frame Generation

DLSS 2.x(RTX 30xx부터)는 낮은 해상도로 렌더링한 프레임을 AI로 업스케일링하는 **Super Resolution** 기능이다. Ada의 DLSS 3는 여기에 **Frame Generation**을 추가했다.

**Frame Generation 원리**:

```
DLSS 3 Frame Generation 파이프라인

렌더링된 프레임 N ─────────────────────────────┐
                                               │
렌더링된 프레임 N+1 ────────────────────────── │── AI 네트워크
                                               │   (Tensor Core)
게임 엔진 모션 벡터 ─────────────────────────── │     → 생성 프레임 G
                                               │
Optical Flow Accelerator (OFA 5세대) ──────────┘
  : 픽셀 단위 옵티컬 플로우 계산

출력 순서: N → G → N+1 → G' → N+2 → ...
         (렌더링 프레임 1개 사이에 AI 생성 프레임 1개 삽입)
```

Frame Generation은 기존 DLSS Super Resolution(SR) 위에 추가되는 단계다. SR로 저해상도 → 목표 해상도 업스케일링 후, 생성된 프레임 사이에 AI 중간 프레임을 삽입한다. 결과적으로 표시 프레임 수가 2배 가까이 늘어난다.

**5세대 OFA(Optical Flow Accelerator)**가 핵심이다. OFA는 Turing부터 탑재됐지만, Ada의 5세대 OFA는 실시간 프레임 생성에 필요한 처리량을 갖췄다. RTX 30xx는 이 OFA 세대가 부족해 Frame Generation을 소프트웨어 업데이트로도 지원하지 못한다.

입력 지연(input lag) 측면에서 AI 생성 프레임은 렌더링 완료 후 삽입되므로 약간의 추가 지연이 생긴다. **NVIDIA Reflex**를 함께 활성화하면 게임-드라이버 간 렌더링 큐를 줄여 이 지연을 보상한다.

---

## 스케줄링

Ada의 Warp 스케줄링 모델은 Ampere를 계승한다. SM당 4개의 독립 Warp 스케줄러가 매 클럭 Warp를 선택한다. Volta에서 도입된 **독립 스레드 스케줄링**(스레드마다 별도 PC 유지)도 그대로 유지된다.

CC 8.9의 점유율(occupancy) 한계:

| 항목 | GA102 (CC 8.6) | AD102 (CC 8.9) |
|:---|:---:|:---:|
| SM당 최대 Warp 수 | 48 | 48 |
| SM당 최대 블록 수 | 16 | **24** |
| SM당 최대 스레드 수 | 1,536 | 1,536 |

최대 Warp 수는 동일하지만 블록 수 상한이 높아져 소규모 블록 커널에서 더 많은 블록을 SM에 상주시킬 수 있다.

SER은 스케줄러 수준에서의 기능이 아니라 드라이버/하드웨어 협력으로 동작하는 셰이더 재정렬 엔진이다. SM 내 Warp 스케줄러 자체는 변경되지 않았다.

---

## 인터커넥트 및 외부 채널

### PCIe 호스트 인터페이스

| 세대 | PCIe 버전 | 최초 아키텍처 |
|:---|:---:|:---:|
| Ada Lovelace (AD102) | **4.0 x16** | - (Ampere에서 동일) |
| Hopper (GH100) | 5.0 x16 | 최초 PCIe 5.0 |
| Ampere (GA102) | 4.0 x16 | 최초 PCIe 4.0 |

Ada는 PCIe 4.0을 유지했다. Hopper만이 PCIe 5.0으로 전환했다. 소비자 GPU에서 PCIe 5.0으로의 전환은 차세대 아키텍처로 미뤄졌다.

### NVLink

RTX 40xx 소비자 GPU에는 NVLink가 없다. RTX 30xx(GA102)에서 NVLink 브리지 커넥터가 존재했던 것과 달리, RTX 40xx에서는 NVLink 커넥터 자체가 제거됐다. Ada 기반 전문가용 GPU(L40, L40S)도 NVLink 미지원이다.

### L2 캐시 및 메모리 서브시스템

| 제품 | L2 캐시 | DRAM 타입 | 버스 폭 | 대역폭 |
|:---|:---:|:---:|:---:|:---:|
| RTX 3090 (GA102) | 6MB | GDDR6X | 384-bit | 936 GB/s |
| RTX 4090 (AD102) | **96MB** | GDDR6X | 384-bit | **1,008 GB/s** |
| RTX 4080 (AD103) | 64MB | GDDR6X | 256-bit | 717 GB/s |
| RTX 4070 Ti (AD104) | 48MB | GDDR6X | 192-bit | 504 GB/s |

### NVENC / NVDEC

| | RTX 3090 (GA102) | RTX 4090 (AD102) | L40S (AD102) |
|:---|:---:|:---:|:---:|
| NVENC 수 | 1 | **2 (dual)** | **2 (dual)** |
| AV1 인코딩 | 지원 | 지원 | 지원 |
| H.264/HEVC 인코딩 | 지원 | 지원 | 지원 |
| AV1 디코딩 | 지원 | 지원 | 지원 |

AD102/AD103는 **NVENC를 2개** 탑재한 최초의 소비자 GPU다. 스트리밍과 로컬 인코딩을 동시에 수행하거나 두 개의 독립 인코드 스트림을 병렬 처리할 수 있다. AD104 이하(RTX 4070 Ti 미만) 다이는 NVENC 1개다.

### 디스플레이 출력 (소비자 참조 기준)

| 제품 | DisplayPort | HDMI | 최대 해상도 |
|:---|:---:|:---:|:---:|
| RTX 4090 (AD102) | 1.4a × 3 | 2.1 × 1 | 7,680×4,320 (DSC) |
| RTX 4080 (AD103) | 1.4a × 3 | 2.1 × 1 | 7,680×4,320 (DSC) |
| L40S (AD102, 전문가용) | 없음 | 없음 | - |

L40S는 데이터센터 AI 추론 전용 카드로 디스플레이 출력이 없다.

---

## 정리

| 항목 | GA102 (Ampere) | AD102 (Ada) |
|:---|:---:|:---:|
| 공정 | Samsung 8nm | **TSMC 4N** |
| 트랜지스터 | 28.3B | **76.3B** |
| FP32 처리량 (RTX 기준) | 35.6 TFLOPS | **82.6 TFLOPS** |
| TC 세대 | 3세대 | **4세대 (FP8)** |
| RT Core 세대 | 2세대 | **3세대 (OME, DMME)** |
| SER | 없음 | **있음** |
| L2 캐시 | 6MB | **96MB** |
| 메모리 대역폭 | 936 GB/s | **1,008 GB/s** |
| 레지스터 파일/SM | 256KB | 256KB |
| 최대 Warps/SM | 48 | 48 |
| 최대 Blocks/SM | 16 | **24** |
| PCIe | 4.0 x16 | 4.0 x16 |
| NVLink | 3.0 (RTX 3090) | **없음** |
| NVENC 수 (AD102) | 1 | **2 (dual)** |
| Frame Generation | 없음 | **DLSS 3** |

Ada Lovelace는 컴퓨트 성능을 2배 이상 높이면서 레이트레이싱 품질과 효율을 근본적으로 끌어올린 아키텍처다. 96MB L2 캐시, 3세대 RT Core(OME, DMME, SER), 4세대 TC(FP8)의 조합은 단순 스케일업이 아니라 레이트레이싱 병목 지점을 구조적으로 해소했다.

다음 포스트에서는 GPU 메모리 시스템과 최적화를 다룬다. L1/L2/HBM 계층의 대역폭 특성, 캐시 관리 정책, 최적화 전략을 다룬다.

---

## 참고 자료

- NVIDIA. *NVIDIA Ada Lovelace GPU Architecture Whitepaper*. 2022.
- NVIDIA. *DLSS 3 and NVIDIA Reflex Technical Blog*. NVIDIA Developer Blog, 2022.
- NVIDIA. *Shader Execution Reordering: Nvidia's Hardware-Assisted Shader Coherence Feature*. NVIDIA Developer Blog, 2022.
- NVIDIA. *GeForce RTX 4090 Product Specifications*. NVIDIA.com.
- NVIDIA. *CUDA C++ Programming Guide, Appendix H: Compute Capabilities*. CUDA Toolkit Documentation.
