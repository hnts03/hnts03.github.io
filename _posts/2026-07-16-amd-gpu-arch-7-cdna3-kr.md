---
layout: post
title: "AMD GPU 아키텍처 #7: CDNA 3"
subtitle: "MI300X - 3D 적층, 통합 논리 GPU, 192GB HBM3, ROCm 6로 AI 추론 시장에 진입하다"
tags: [GPU, Architecture, AMD, CDNA, ROCm, HPC, AI, Computer-Architecture]
lang: kr
translation-url: /2026-07-16-amd-gpu-arch-7-cdna3-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 개요 | [RDNA / CDNA 전 세대 타임라인](/2026-07-09-amd-gpu-arch-overview-kr/) | ✅ |
| 5 | [CDNA 1 - GCN 계승, Matrix Core, A100 대결](/2026-07-15-amd-gpu-arch-5-cdna1-kr/) | ✅ |
| 6 | [CDNA 2 - MCM 2-die, FP64 Matrix, Frontier](/2026-07-15-amd-gpu-arch-6-cdna2-kr/) | ✅ |
| 7 | CDNA 3 - MI300X, 3D 적층, 통합 GPU, ROCm 6 | ✅ |

---

## CDNA 2가 남긴 것, CDNA 3가 바꾼 것

CDNA 2(MI250X)는 MCM으로 다이 한계를 넘고 FP64 Matrix로 HPC를 완성했다. 그러나 두 가지 근본 문제가 남았다.

- **분리형 GPU**: 2개 GCD가 OS에 별도 GPU로 보였다. 프로그래머가 다이 간 데이터 이동을 직접 관리해야 했다.
- **소프트웨어 미성숙**: ROCm이 CUDA를 따라가지 못해, 하드웨어가 경쟁력 있어도 실사용이 제약됐다.

CDNA 3는 이 둘을 포함해 하드웨어와 소프트웨어 스택 전반을 재설계했다. 세대 간 변화폭이 CDNA 시리즈에서 가장 크다. 그 중심에 **MI300X**가 있다. AMD가 AI 추론 시장에서 NVIDIA의 실질적 대안으로 처음 자리 잡은 디바이스다.

이 글은 MI300X를 중심으로 다룬다. HPC용 변형인 MI300A(CPU+GPU APU)는 뒤에서 별도로 정리한다.

| 축 | CDNA 2 (MI250X) | CDNA 3 (MI300X) |
|:---|:---|:---|
| 패키징 | 2.5D MCM (나란히 배치) | **3.5D (XCD를 IOD 위에 3D 적층)** |
| 논리 GPU | 2개 (분리) | **1개 (통합 논리 GPU)** |
| 다이 역할 | GCD (컴퓨트+IO 혼합) | **XCD(컴퓨트) + IOD(IO/캐시) 분리** |
| 공유 캐시 | 없음 | **256MB Infinity Cache (통합 LLC)** |
| 데이터 포맷 | FP16/BF16/INT8 | **+ FP8, TF32 추가** |
| 메모리 | HBM2e 128GB | **HBM3 192GB** |
| 소프트웨어 | ROCm 4/5 (미성숙) | **ROCm 6 (PyTorch/vLLM 공식)** |

---

## 3.5D 패키징: XCD를 IOD 위에 적층

CDNA 3의 가장 큰 하드웨어 변화는 패키징이다. CDNA 2의 2.5D MCM(다이를 인터포저 위에 나란히 배치)에서, **3D 하이브리드 본딩**으로 전환했다.

![MI300X 3.5D 패키징 단면도](/assets/img/posts/amd-gpu-arch-7-cdna3/packaging-3d.png)

MI300X는 12개 다이를 3개 층으로 쌓는다.

- **컴퓨트 층**: 8개 **XCD(Accelerator Complex Die)**, TSMC N5(5nm). 순수 컴퓨트 유닛만 담는다.
- **IO 층**: 4개 **IOD(I/O Die)**, TSMC N6(6nm). 메모리 컨트롤러, Infinity Cache, Infinity Fabric을 담는다.
- **본딩**: XCD를 IOD 위에 **TSMC SoIC(하이브리드 본딩)** 로 3D 접합한다. IOD당 XCD 2개가 올라간다.

이 구조를 "3.5D"라 부르는 이유는 2.5D(인터포저)와 3D(다이 적층)를 결합했기 때문이다. IOD와 HBM3는 인터포저 위에 2.5D로 배치되고, XCD는 IOD 위에 3D로 적층된다.

### 컴퓨트와 IO의 분리

CDNA 2의 GCD는 컴퓨트 유닛과 메모리 컨트롤러를 한 다이에 섞었다. CDNA 3는 이를 **역할별로 분리**했다.

```
CDNA 2 GCD (혼합):              CDNA 3 (분리):
┌─────────────────────┐        XCD (N5): 컴퓨트 전용
│  CU + 메모리 컨트롤러  │              ↑ 3D 본딩
│  + HBM PHY 혼합       │        IOD (N6): 메모리 컨트롤러
└─────────────────────┘              + Infinity Cache + IF
```

분리의 이익은 두 가지다. 컴퓨트 로직(XCD)은 최신 5nm로 성능을 높이고, 미세화 이득이 작은 IO/캐시(IOD)는 저렴한 6nm에 둔다. 그리고 XCD를 IOD 바로 위에 적층해 컴퓨트-메모리 간 물리적 거리를 최소화한다. 다이 간 배선이 짧아져 대역폭과 전력 효율이 개선된다.

---

## 통합 논리 GPU: CDNA 2의 숙제 해결

CDNA 2의 가장 큰 사용성 문제는 MI250X가 2개 GPU로 보이는 것이었다. CDNA 3는 이를 근본적으로 해결했다.

MI300X의 8개 XCD는 4개 IOD를 통해 **256MB Infinity Cache를 공유**한다. 이 공유 캐시가 모든 XCD에 코히런트한 마지막 레벨 캐시(LLC)를 제공한다. 결과적으로 8개 XCD가 하나의 논리적 GPU로 동작한다.

```
CDNA 2 (MI250X):                 CDNA 3 (MI300X):
GPU0 ←IF→ GPU1                   ┌──────────────────────────┐
(별도 주소공간)                   │ XCD×8이 공유하는          │
프로그래머가 분할 관리             │ 256MB Infinity Cache      │
                                │ → 단일 논리 GPU로 동작     │
                                │ → 프로그래머는 1개로 취급   │
                                └──────────────────────────┘
```

프로그래머는 MI300X를 하나의 GPU로 다룬다. 다이 간 데이터 분할을 명시적으로 관리할 필요가 없다. 필요 시 컴퓨트 파티셔닝 모드로 XCD 그룹을 나눠 여러 논리 GPU로 쓸 수도 있다. 통합이 기본이고 분할은 선택이다. CDNA 2와 정반대다.

---

## Matrix Core 강화와 FP8

CDNA 3는 Matrix Core를 대폭 강화하고 AI 추론용 저정밀도 포맷을 추가했다.

- **FP8 추가**: MI300X 기준 FP8 2,614 TFLOPS. LLM 추론의 핵심 포맷이다.
- **TF32 추가**: NVIDIA가 A100에서 도입했던 학습 친화 포맷을 CDNA 3에서 지원한다.
- **처리량 향상**: CDNA 2 대비 FP16/BF16 3배, INT8 6.8배(AMD 발표).

```
MI300X 연산 성능:
  FP64 벡터  :   81.7 TFLOPS
  FP64 Matrix:  163.4 TFLOPS
  FP32 벡터  :  163.4 TFLOPS
  FP16/BF16  : 1307.4 TFLOPS
  FP8        : 2614.9 TFLOPS   ← 신규
```

FP64와 FP8을 모두 최상급으로 제공하는 것이 CDNA 3의 특징이다. FP64는 HPC(과학 계산), FP8은 AI(LLM 추론)를 겨냥한다. 하나의 아키텍처로 두 시장을 동시에 노린다.

**MI300X 스펙:**

| 항목 | 값 |
|:---|:---|
| 공정 | XCD N5 (5nm) / IOD N6 (6nm) |
| 다이 구성 | 8 XCD + 4 IOD + 8 HBM3 (12 다이) |
| 트랜지스터 | 약 1,530억 |
| CU | 304 (XCD당 38 × 8) |
| 스트림 프로세서 | 19,456 |
| Infinity Cache | 256MB (공유 LLC) |
| 메모리 | HBM3 192GB (12-Hi) |
| 메모리 대역폭 | 5.3 TB/s |
| FP64 Matrix | 163.4 TFLOPS |
| FP8 | 2,614 TFLOPS |
| TDP | 750W |

---

## MI300X가 중요한 이유: 192GB 단일 카드

MI300X가 CDNA 3의 핵심 디바이스인 이유는 벤치마크 수치가 아니라 **메모리 용량**에 있다. AI 추론 시장의 요구가 정확히 여기에 맞았다.

LLM 추론에서 가장 큰 제약은 연산이 아니라 메모리다. 모델 가중치와 KV 캐시가 GPU 메모리에 올라가야 한다. MI300X는 **192GB HBM3**를 단일 카드에 담는다. 같은 시기 NVIDIA H100은 80GB, H200은 141GB였다.

```
70B 모델 추론에 필요한 GPU 수 (FP16 가중치 ~140GB 기준):
  H100 (80GB)   : 최소 2장 (텐서 병렬로 분할)
  H200 (141GB)  : 1장 (여유 적음)
  MI300X (192GB): 1장 (KV 캐시 여유까지 확보)
```

단일 카드에 큰 모델이 올라가면 GPU 간 통신이 사라진다. 텐서 병렬 분할에 따르는 통신 오버헤드와 복잡성이 줄어든다. KV 캐시 용량이 커지면 더 긴 컨텍스트, 더 큰 배치를 처리할 수 있다. 추론 처리량이 곧 서비스 비용인 환경에서 이 이점은 직접적이다.

이 특성 덕분에 MI300X는 AMD 데이터센터 GPU 최초로 대규모 상업 채택에 이르렀다. Microsoft Azure를 비롯한 주요 클라우드가 MI300X 인스턴스를 제공한다. AI 가속기 시장에서 NVIDIA 독점에 대한 실질적 대안이 처음 등장한 것이다.

---

## 소프트웨어 대격변: ROCm 6

MI300X의 하드웨어 우위(192GB, 5.3 TB/s)가 실제 채택으로 이어진 것은 소프트웨어가 뒷받침했기 때문이다. CDNA 3와 함께 출시된 **ROCm 6**는 하드웨어만큼 큰 변화였다.

CDNA 1/2 시기 ROCm의 최대 약점은 생태계 성숙도였다. 하드웨어가 좋아도 프레임워크 지원이 CUDA를 따라가지 못했다. ROCm 6는 이 격차를 크게 좁혔다.

**주요 변화:**

- **PyTorch 공식 지원**: MI300X에서 PyTorch가 공식 지원된다. 별도 패치 없이 표준 워크플로우가 동작한다.
- **vLLM 통합**: LLM 추론 프레임워크 vLLM이 MI300X를 지원한다. ROCm 6.2에서 FP8 추론, FP8 KV 캐시까지 지원한다.
- **FP8 GEMM**: hipBLASLt를 통해 PyTorch, JAX에서 FP8 행렬 연산을 가속한다.
- **컨테이너 배포**: ROCm + vLLM + PyTorch를 묶은 사전 빌드 Docker 이미지로 배포가 간소화됐다.

```
ROCm 6 스택 (MI300X 추론):
  vLLM 0.6.x  (LLM 서빙, FP8 KV 캐시)
     │
  PyTorch 2.5 (프레임워크)
     │
  hipBLASLt / Composable Kernel (FP8 GEMM)
     │
  ROCm 6.2 런타임 + HIP
     │
  MI300X (CDNA 3)
```

CDNA 3 세대에서 처음으로 AMD 데이터센터 GPU가 하드웨어와 소프트웨어를 모두 갖췄다. 192GB라는 하드웨어 강점이 vLLM의 FP8 추론 위에서 실제 서비스로 구현됐다.

---

## 변형: MI300A APU

MI300X와 같은 CDNA 3 기반이지만, HPC를 겨냥한 변형이 **MI300A**다. 데이터센터용으로 CPU와 GPU를 단일 패키지에 통합한 AMD 최초의 APU다.

![MI300X vs MI300A 변형 비교](/assets/img/posts/amd-gpu-arch-7-cdna3/mi300x-vs-mi300a.png)

MI300A는 MI300X의 XCD 2개를 **Zen 4 CPU 칩렛(CCD) 3개**로 교체한다.

- **MI300X**: 8 XCD (순수 GPU), HBM3 192GB
- **MI300A**: 6 XCD + 3 Zen 4 CCD (24 CPU 코어) + 228 CU, 통합 HBM3 128GB

핵심은 **CPU와 GPU가 같은 HBM3 풀을 공유**한다는 것이다. 기존에는 CPU가 계산한 결과를 GPU로 넘기려면 명시적 복사가 필요했다. MI300A에서는 CPU와 GPU가 같은 물리 메모리의 같은 주소를 본다. 데이터 복사가 사라진다. CPU-GPU 상호작용이 잦은 HPC 워크로드에서 프로그래밍을 단순화하고 성능을 높인다. 방향은 NVIDIA Grace-Hopper(GH200)와 같으나, GH200이 2칩 연결인 반면 MI300A는 단일 패키지 통합이다.

MI300A는 **El Capitan**의 연산 엔진이다. El Capitan은 미국 로렌스 리버모어 국립연구소(LLNL)의 슈퍼컴퓨터로, 2024년 11월 Top500에서 세계 1위에 올랐다(HPL 1.742 EFlop/s, MI300A 43,808개). CDNA 2의 Frontier에 이은 AMD의 두 번째 엑사스케일 1위 시스템이다.

MI300 시리즈는 이후 **MI325X(2024)** 로 메모리를 강화했다. 아키텍처는 CDNA 3 동일, HBM3를 HBM3e로 교체해 용량 256GB, 대역폭 6.0 TB/s로 확장했다. LLM 추론에서 KV 캐시 용량을 직접 늘린다.

---

## NVIDIA H100/H200과의 비교

MI300X의 경쟁자는 NVIDIA **H100(Hopper, 2022)** 와 그 메모리 강화판 **H200** 이다.

### 핵심 사양 비교

![MI300X (CDNA 3) vs H100 SXM (Hopper)](/assets/img/posts/amd-gpu-arch-7-cdna3/spec-compare.png)

| | MI300X (CDNA 3) | H100 SXM (Hopper) | H200 (Hopper) |
|:---|:---:|:---:|:---:|
| 공정 | N5 + N6 | TSMC 4N | TSMC 4N |
| 다이 구성 | 3.5D 12-die | 모놀리식 | 모놀리식 |
| FP64 Matrix | 163.4 TFLOPS | 34 TFLOPS | 34 TFLOPS |
| FP8 | 2,614 TFLOPS | 1,979 TFLOPS | 1,979 TFLOPS |
| 메모리 | HBM3 192GB | HBM3 80GB | HBM3e 141GB |
| 메모리 대역폭 | 5.3 TB/s | 3.35 TB/s | 4.8 TB/s |
| 멀티 GPU | Infinity Fabric | NVLink + NVSwitch | NVLink + NVSwitch |
| 소프트웨어 | ROCm 6 | CUDA | CUDA |

### 영역별 우열

**단일 GPU 하드웨어**

MI300X가 앞선다. FP64 Matrix는 H100의 약 4.8배, 메모리 용량은 2.4배(192 vs 80GB), 대역폭도 앞선다. H200과 비교해도 메모리 용량(192 vs 141GB)과 대역폭(5.3 vs 4.8 TB/s)에서 우위다. 단일 카드에 더 큰 모델을 올릴 수 있어 LLM 추론에서 유리하다.

**멀티 GPU 확장**

NVIDIA가 앞선다. NVLink와 NVSwitch는 GPU 간 all-to-all 대역폭에서 AMD의 Infinity Fabric 기반 연결보다 우수하다. 대규모 분산 학습에서 이 차이가 확장 효율에 영향을 준다.

**소프트웨어**

여전히 CUDA가 앞선다(이른바 CUDA moat). ROCm 6로 추론 워크로드의 격차는 크게 좁혀졌으나, 대규모 학습의 성숙도와 커널 최적화 폭에서 CUDA가 우위를 유지한다. MI300X는 추론에서 강한 경쟁력을 확보했고, 학습에서는 격차를 좁히는 중이다.

---

## 요약

| 축 | CDNA 2 대비 변화 |
|:---|:---|
| 패키징 | 2.5D MCM → 3.5D (XCD를 IOD 위에 3D 적층) |
| 논리 GPU | 2개 분리 → 1개 통합 (256MB Infinity Cache) |
| 다이 역할 | GCD 혼합 → XCD(컴퓨트) + IOD(IO) 분리 |
| 데이터 포맷 | FP16/BF16/INT8 → + FP8, TF32 |
| 메모리 | HBM2e 128GB → HBM3 192GB |
| 소프트웨어 | ROCm 4/5 → ROCm 6 (PyTorch/vLLM 공식) |
| 변형 | - → MI300A APU (CPU+GPU 통합 메모리), El Capitan |

| | MI300X (CDNA 3) | H100/H200 (Hopper) |
|:---|:---:|:---:|
| FP64 Matrix | 163.4 TFLOPS (압도) | 34 TFLOPS |
| 메모리 용량 | 192GB (우세) | 80 / 141GB |
| 메모리 대역폭 | 5.3 TB/s (우세) | 3.35 / 4.8 TB/s |
| 멀티 GPU 확장 | 열세 | NVLink/NVSwitch (우세) |
| 소프트웨어 | ROCm 6 (추론 경쟁력) | CUDA (우세) |

CDNA 3는 CDNA 시리즈에서 가장 큰 세대 변화다. 그 핵심 디바이스인 MI300X는 3D 적층으로 컴퓨트와 IO를 분리하고, 통합 논리 GPU로 CDNA 2의 프로그래밍 복잡성을 해소했으며, 192GB HBM3로 단일 카드에 큰 모델을 담았다. ROCm 6의 소프트웨어 성숙이 이 하드웨어를 실전에서 뒷받침했다. MI300X는 AMD 데이터센터 GPU 최초로 AI 추론 시장에서 NVIDIA의 실질적 대안이 됐다. HPC용 변형 MI300A는 El Capitan으로 세계 1위를 갱신했다.

이것으로 AMD GPU 아키텍처 시리즈(RDNA 1~4, CDNA 1~3)를 마친다. 후속 CDNA 4(MI350)는 [개요 포스트](/2026-07-09-amd-gpu-arch-overview-kr/)에서 다룬다.
