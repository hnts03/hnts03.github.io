---
layout: post
title: "AMD GPU 아키텍처 #5: CDNA 1"
subtitle: "GCN 컴퓨트 계보의 계승, Matrix Core의 등장, 그리고 NVIDIA A100과의 대결"
tags: [GPU, Architecture, AMD, CDNA, ROCm, HPC, Computer-Architecture]
lang: kr
translation-url: /2026-07-15-amd-gpu-arch-5-cdna1-en/
readtime: true
mathjax: true
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 개요 | [RDNA / CDNA 전 세대 타임라인](/2026-07-09-amd-gpu-arch-overview-kr/) | ✅ |
| 1 | [RDNA 1 - Wave32, WGP, 7nm](/2026-07-09-amd-gpu-arch-1-rdna1-kr/) | ✅ |
| 2 | [RDNA 2 - Ray Accelerator, Infinity Cache](/2026-07-13-amd-gpu-arch-2-rdna2-kr/) | ✅ |
| 3 | [RDNA 3 - 칩렛, Dual-Issue](/2026-07-13-amd-gpu-arch-3-rdna3-kr/) | ✅ |
| 4 | [RDNA 4 - 모놀리식 복귀, FSR 4](/2026-07-13-amd-gpu-arch-4-rdna4-kr/) | ✅ |
| 5 | CDNA 1 - GCN 계승, Matrix Core, A100 대결 | ✅ |
| 6 | [CDNA 2 - MCM, FP64 Matrix, Frontier](/2026-07-15-amd-gpu-arch-6-cdna2-kr/) | ✅ |
| 7 | CDNA 3 - XCD 칩렛, MI300A APU, El Capitan | 🔲 |

---

## 왜 별도의 컴퓨트 아키텍처인가

2019년 AMD는 GPU 아키텍처를 둘로 나눴다. RDNA는 소비자 그래픽으로, CDNA는 데이터센터 컴퓨트로 향했다.

RDNA 시리즈를 다루며 반복해서 나온 명제가 있다. RDNA는 GCN에서 벗어나 Wave32 실행 모델로 전환했다는 것이다. 그런데 CDNA는 반대다. **CDNA는 GCN의 컴퓨트 기반을 그대로 계승한다.**

![GCN에서 RDNA / CDNA로의 분기](/assets/img/posts/amd-gpu-arch-5-cdna1/gcn-fork.png)

이 분기의 논리는 워크로드 특성에서 나온다.

- **그래픽(RDNA)**: 분기가 잦고 레이턴시에 민감하다. Wave32로 좁혀야 분기 손실이 줄고 고클럭이 가능하다.
- **컴퓨트(CDNA)**: 대규모 행렬 연산과 규칙적인 데이터 병렬성이 지배적이다. Wave64의 넓은 실행 폭이 처리량 확보에 유리하다.

RDNA가 그래픽을 위해 버린 Wave64를, CDNA는 컴퓨트를 위해 유지했다. 두 아키텍처는 같은 GCN 뿌리에서 정반대 방향으로 특화됐다.

**CDNA 1(Arcturus, MI100, 2020년 11월)**은 이 분리 이후 첫 데이터센터 전용 아키텍처다.

---

## 그래픽 파이프라인 제거

CDNA 1의 첫 번째 결정은 그래픽 하드웨어의 완전한 제거다.

```
GCN (Vega) → CDNA 1 (Arcturus) 제거된 블록:
┌────────────────────────────────────────────┐
│  ❌ ROP (Render Output Unit)               │
│  ❌ 래스터라이저 (Rasterizer)              │
│  ❌ 지오메트리/테셀레이션 엔진             │
│  ❌ 디스플레이 엔진 (출력 포트 없음)       │
│  ❌ 멀티미디어 인코드/디코드 (일부)        │
│                                            │
│  ✅ 남은 것: 컴퓨트 유닛(CU) + 메모리      │
│  ✅ 추가된 것: Matrix Core                 │
└────────────────────────────────────────────┘
```

MI100에는 디스플레이 출력 포트가 없다. 화면을 그리지 않기 때문이다. 래스터라이저와 ROP도 없다. 삼각형을 픽셀로 바꾸는 작업을 하지 않는다.

이 제거의 대가는 다이 면적의 재분배다. 그래픽 고정 기능 블록이 차지하던 공간을 컴퓨트 유닛과 Matrix Core에 할당한다. MI100은 120개 CU를 집적했다. 같은 7nm 세대 소비자 GPU(RDNA 1 Navi 10 40 CU)의 3배다.

---

## CU 구조: GCN 계보의 계승

CDNA 1의 컴퓨트 유닛은 GCN의 구조를 유지한다. RDNA와 비교하면 차이가 분명하다.

```
RDNA CU (Wave32):              CDNA 1 CU (Wave64, GCN 계승):
┌──────────────────────┐      ┌──────────────────────────────┐
│  SIMD32 × 2          │      │  SIMD16 × 4                  │
│  Wave32 (32 스레드)  │      │  Wave64 (64 스레드)          │
│  1클럭 완료          │      │  4클럭 완료 (16 × 4)         │
│                      │      │  ┌────────────────────────┐  │
│  (Matrix 없음)        │      │  │  Matrix Core (MFMA)   │  │
│                      │      │  │  FP32/FP16/BF16/INT8  │  │
│  LDS 128KB (WGP)     │      │  └────────────────────────┘  │
└──────────────────────┘      │  LDS 64KB                    │
                              └──────────────────────────────┘
```

CDNA 1 CU는 GCN처럼 **SIMD16 유닛 4개**로 구성되고, **Wave64(64스레드)** 를 기본 실행 단위로 사용한다. RDNA가 SIMD32 2개와 Wave32로 전환한 것과 대조된다.

| 항목 | GCN (Vega) | RDNA | CDNA 1 |
|:---|:---:|:---:|:---:|
| SIMD 구성 | SIMD16 × 4 | SIMD32 × 2 | SIMD16 × 4 |
| 웨이브 크기 | Wave64 | Wave32 | Wave64 |
| 웨이브 완료 클럭 | 4 | 1 | 4 |
| 대상 워크로드 | 혼합 | 그래픽 | 컴퓨트 |

컴퓨트 워크로드는 대규모 배열 연산이 규칙적으로 반복된다. 분기가 적으므로 Wave64의 넓은 폭이 낭비되지 않는다. 오히려 명령 페치와 스케줄링 오버헤드를 웨이브당 더 많은 스레드에 분산해 효율이 높아진다.

---

## Matrix Core: AMD 최초의 행렬 가속

CDNA 1의 핵심 추가는 **Matrix Core**다. NVIDIA Tensor Core에 대응하는 AMD의 전용 행렬 연산 유닛이다.

Matrix Core는 **MFMA(Matrix Fused Multiply-Add)** 명령으로 동작한다. 행렬 A와 B를 곱해 누산기 C에 더하는 $D = A \times B + C$ 연산을 한 명령으로 처리한다. 딥러닝의 GEMM(일반 행렬 곱)과 HPC의 밀집 선형대수가 이 패턴이다.

```
MFMA가 가속하는 연산 (한 명령):
    D[M×N] = A[M×K] × B[K×N] + C[M×N]

지원 정밀도 (CDNA 1):
  FP32 matrix : 46.1 TFLOPS  (FP32 vector 23.1의 2배)
  FP16 matrix : 184.6 TFLOPS
  BF16 matrix : 92.3 TFLOPS
  INT8 matrix : 184.6 TOPS
```

CDNA 1의 Matrix Core는 FP32, FP16, BF16, INT8, INT4 행렬 연산을 가속한다. 주목할 점은 **FP64 행렬 연산이 없다**는 것이다. FP64는 벡터 파이프라인(11.5 TFLOPS)으로만 처리된다. FP64 Matrix Core는 다음 세대 CDNA 2에서 추가된다.

Matrix Core는 별도의 거대한 고정 블록이라기보다, CU의 SIMD 유닛과 결합된 행렬 명령 경로에 가깝다. NVIDIA Tensor Core와 구현 방식은 다르지만, 목적은 동일하다. 행렬 곱 처리량을 벡터 연산 대비 크게 높이는 것이다.

---

## 메모리와 인터커넥트

**HBM2 메모리**

MI100은 4스택 HBM2, 총 32GB를 4096-bit 인터페이스로 연결한다. 대역폭은 1.23 TB/s다. 소비자 GPU가 GDDR6 256~384bit를 쓰는 것과 달리, 컴퓨트 GPU는 넓은 HBM 인터페이스로 대역폭을 확보한다.

**Infinity Fabric (2세대)**

MI100은 GPU 간 직접 연결을 위한 **Infinity Fabric** 링크 3개를 제공한다. 이를 통해 최대 4개 GPU를 완전 연결(fully-connected) 하이브로 묶는다.

```
4-GPU 하이브 (fully-connected):
    GPU0 ─── GPU1
     │  ╲   ╱  │
     │   ╳     │      각 GPU가 나머지 3개와 직접 연결
     │  ╱   ╲  │      IF 링크로 PCIe 대비 높은 peer 대역폭
    GPU2 ─── GPU3

호스트 인터페이스: PCIe 4.0 x16
```

이 구성은 다중 GPU 간 데이터 교환이 빈번한 HPC/학습 워크로드에서 PCIe 병목을 완화한다. GPU 간 통신을 호스트 메모리를 경유하지 않고 직접 처리한다.

**MI100 스펙:**

| 항목 | 값 |
|:---|:---|
| 코드명 | Arcturus |
| 공정 | TSMC 7nm FinFET |
| CU | 120 |
| 스트림 프로세서 | 7,680 |
| 부스트 클럭 | 1,502 MHz |
| FP64 벡터 | 11.5 TFLOPS |
| FP32 벡터 | 23.1 TFLOPS |
| FP32 Matrix | 46.1 TFLOPS |
| FP16 Matrix | 184.6 TFLOPS |
| BF16 Matrix | 92.3 TFLOPS |
| 메모리 | HBM2 32GB, 4096-bit |
| 메모리 대역폭 | 1.23 TB/s |
| TDP | 300W |
| 인터페이스 | PCIe 4.0 x16 + IF 링크 3개 |

---

## NVIDIA A100과의 비교

CDNA 1의 경쟁자는 2020년 출시된 NVIDIA **A100(Ampere, GA100)** 이다. 데이터센터 컴퓨트 시장의 사실상 표준이었다.

### 핵심 사양 비교

![MI100 (CDNA 1) vs A100 40GB (Ampere)](/assets/img/posts/amd-gpu-arch-5-cdna1/spec-compare.png)

| | MI100 (CDNA 1) | A100 40GB (Ampere) |
|:---|:---:|:---:|
| 공정 | TSMC 7nm | TSMC 7nm |
| FP64 벡터 | 11.5 TFLOPS | 9.7 TFLOPS |
| FP64 Matrix/Tensor | 없음 | 19.5 TFLOPS |
| FP32 벡터 | 23.1 TFLOPS | 19.5 TFLOPS |
| FP16 Matrix/Tensor | 184.6 TFLOPS | 312 TFLOPS |
| TF32 | 미지원 | 지원 (156 TFLOPS) |
| Sparsity 가속 | 없음 | 2배 (구조적 희소성) |
| 메모리 | HBM2 32GB | HBM2e 40GB |
| 메모리 대역폭 | 1.23 TB/s | 1.55 TB/s |
| TDP | 300W | 400W (SXM) |

### 영역별 우열

**전통 HPC (FP64/FP32 벡터)**

MI100이 앞선다. FP64 벡터 11.5 TFLOPS는 A100의 9.7 TFLOPS를 약 19% 상회한다. FP32 벡터도 우세하다. 배정밀도 밀집 선형대수가 중심인 과학 계산 워크로드에서 MI100은 경쟁력이 있었다.

**AI/딥러닝 (행렬/텐서)**

A100이 앞선다. FP16 텐서 312 TFLOPS는 MI100 Matrix 184.6 TFLOPS를 크게 상회한다. A100은 여기에 **구조적 희소성(structured sparsity)** 가속으로 최대 2배(624 TFLOPS)까지 확장한다. 또한 **TF32**라는 학습 친화적 포맷을 지원한다. MI100에는 없는 기능이다. FP64 텐서 코어도 A100에만 있다.

**소프트웨어 생태계**

가장 큰 격차는 하드웨어가 아니었다. NVIDIA **CUDA**는 2007년부터 축적된 생태계를 보유한다. cuBLAS, cuDNN, NCCL 등 라이브러리와 모든 주요 ML 프레임워크가 CUDA에 최적화돼 있다.

AMD **ROCm**은 CDNA 1 시기에 성숙도가 낮았다. HIP(CUDA 유사 API)로 이식성을 제공했으나, 라이브러리 커버리지와 안정성에서 CUDA에 미치지 못했다. MI100의 하드웨어 경쟁력에도 불구하고 실사용 채택을 제약한 핵심 요인이다.

---

## 소프트웨어: ROCm과 HIP

CDNA 1은 **ROCm(Radeon Open Compute)** 스택으로 프로그래밍한다.

- **HIP(Heterogeneous-computing Interface for Portability)**: CUDA와 유사한 C++ API. `hipify` 도구로 CUDA 코드를 HIP로 변환 가능. AMD와 NVIDIA GPU 양쪽에서 컴파일된다.
- **rocBLAS, MIOpen**: cuBLAS, cuDNN에 대응하는 선형대수·딥러닝 라이브러리
- **RCCL**: NCCL에 대응하는 다중 GPU 집합 통신 라이브러리

CDNA 1 시기의 ROCm은 기능적으로는 갖춰졌으나 생태계 성숙도에서 CUDA와 격차가 컸다. 이 격차는 이후 세대(CDNA 2의 Frontier, CDNA 3의 MI300)를 거치며 대형 슈퍼컴퓨터 도입과 함께 점진적으로 좁혀진다.

---

## 요약

| 항목 | 내용 |
|:---|:---|
| 계보 | GCN 컴퓨트 기반 계승 (RDNA와 반대 방향) |
| 실행 모델 | Wave64 / SIMD16 × 4 (GCN 유지) |
| 그래픽 | 파이프라인 완전 제거 (ROP/래스터/디스플레이 없음) |
| 핵심 추가 | Matrix Core (MFMA) - AMD 최초 행렬 가속 |
| FP64 | 벡터만 (Matrix는 CDNA 2에서 추가) |
| 메모리 | HBM2 32GB, 1.23 TB/s |
| 인터커넥트 | Infinity Fabric 3링크, 4-GPU 하이브 |

| | MI100 (CDNA 1) | A100 (Ampere) |
|:---|:---:|:---:|
| FP64 벡터 | 11.5 TFLOPS (우세) | 9.7 TFLOPS |
| FP32 벡터 | 23.1 TFLOPS (우세) | 19.5 TFLOPS |
| FP16 Matrix/Tensor | 184.6 TFLOPS | 312 TFLOPS (우세) |
| AI 특화 | 기본 | TF32, Sparsity (우세) |
| 소프트웨어 | ROCm (미성숙) | CUDA (성숙, 우세) |

CDNA 1은 AMD가 데이터센터 컴퓨트로 복귀하는 출발점이었다. GCN의 Wave64 컴퓨트 기반을 계승하고, 그래픽 하드웨어를 제거해 다이를 컴퓨트에 집중시켰다. Matrix Core로 행렬 가속의 첫발을 뗐다. FP64/FP32 벡터에서 A100을 앞섰으나, AI 텐서 성능과 소프트웨어 생태계에서는 뒤처졌다. 이 격차를 좁히는 과정이 다음 세대들의 과제가 된다.

다음 글: [CDNA 2 - MCM 2-die, FP64 Matrix Core, 그리고 세계 최초 엑사스케일 Frontier](/2026-07-15-amd-gpu-arch-6-cdna2-kr/)
