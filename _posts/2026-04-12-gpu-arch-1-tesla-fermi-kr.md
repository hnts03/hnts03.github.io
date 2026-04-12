---
layout: post
title: "GPU 아키텍처 #1: GPU의 출발과 SIMT의 탄생"
subtitle: "Tesla, Fermi 아키텍처와 CUDA의 시작"
tags: [GPU, Architecture, CUDA, NVIDIA, SIMT, Computer-Architecture]
lang: kr
translation-url: /2026-04-12-gpu-arch-1-tesla-fermi-en/
readtime: true
mathjax: true
---

## 시리즈 로드맵

| # | 주제 |
|:--:|:---|
| **1** | **GPU의 출발과 SIMT의 탄생 — Tesla, Fermi** |
| 2 | GPU 아키텍처의 진화 — Kepler에서 Blackwell까지 |
| 3 | GPU 메모리 시스템과 최적화 |
| 4 | GPU 내부 해부 — Instruction/Memory/Compute 파이프라인 |
| 5 | CUDA 커널 최적화 |

---

## 1. GPU는 어디서 왔는가

GPU는 원래 화면에 픽셀을 빠르게 그리기 위한 장치였습니다. 1990년대 3D 게임 붐이 일면서 기하(geometry) 연산과 픽셀 색상 계산 수요가 폭발적으로 증가했고, CPU 혼자 감당하기에는 역부족이었습니다.

초기 GPU는 **고정 함수 파이프라인(Fixed-Function Pipeline)** 구조였습니다. T&L(Transform & Lighting), 래스터라이저, 텍스처 매핑 같은 각 단계가 하드웨어에 고정되어 있었고, 개발자가 할 수 있는 것은 파라미터를 조정하는 것뿐이었습니다.

전환점은 **프로그래머블 셰이더(Programmable Shader)** 의 등장이었습니다. NVIDIA GeForce 3(2001)에서 처음 도입된 버텍스 셰이더는 GPU 파이프라인의 일부를 코드로 제어할 수 있게 했습니다. DirectX 9(2002) 시대에는 버텍스 셰이더와 픽셀 셰이더가 보편화되면서 광원 효과, 그림자, 굴절 같은 복잡한 효과도 셰이더 코드로 구현할 수 있게 되었습니다.

이 시기에 일부 연구자들이 중요한 사실을 발견했습니다. 셰이더는 결국 **부동소수점 연산을 병렬로 수행하는 작은 프로그램**이고, 이를 그래픽 이외의 과학 계산에도 활용할 수 있다는 것이었습니다. GPGPU(General-Purpose computing on GPU)의 시대가 시작된 것입니다.

---

## 2. Tesla 아키텍처 — GPGPU의 첫 발

### 통합 셰이더 아키텍처의 등장

DirectX 9까지는 버텍스 셰이더와 픽셀 셰이더가 분리된 하드웨어 유닛에서 동작했습니다. 문제는 씬의 복잡도에 따라 두 유닛의 부하 비율이 달라지는데, 하드웨어 비율은 고정되어 있다 보니 한쪽이 유휴 상태가 되고 다른 쪽이 병목이 되는 상황이 반복되었습니다.

NVIDIA는 G80(GeForce 8800, 2006)에서 **통합 셰이더 아키텍처(Unified Shader Architecture)** 를 도입했습니다. 버텍스와 픽셀 처리를 동일한 범용 프로세서 풀에서 처리하고, 워크로드에 따라 자원을 동적으로 배분하는 방식입니다. 이것이 Tesla 마이크로아키텍처의 핵심입니다.

### G80의 구조

G80은 128개의 스칼라 프로세서(Scalar Processor)를 탑재했습니다.

```
G80 구조 (간략화)
├── TPC (Texture Processor Cluster) × 8
│   └── SM (Streaming Multiprocessor) × 2
│       ├── SP (Scalar Processor) × 8
│       ├── SFU (Special Function Unit) × 2
│       └── Shared Memory / L1 Cache
└── ROP (Raster Operation Processor)
```

그래픽 계층인 TPC 아래에 SM이 있고, SM 내부의 SP가 실제 연산을 담당합니다.

### CUDA의 탄생

G80 출시와 함께 NVIDIA는 **CUDA(Compute Unified Device Architecture)** 를 발표했습니다(2006). CUDA는 두 가지 의미를 가집니다.

1. **하드웨어**: GPU를 일반 계산에 활용할 수 있도록 설계된 아키텍처. 메모리 직접 접근, 스레드 동기화 등을 지원합니다.
2. **소프트웨어**: C 언어 기반의 GPU 병렬 프로그래밍 플랫폼.

CUDA 이전의 GPGPU는 셰이더 언어(GLSL, HLSL)를 우회하는 방식이라 생산성이 극히 낮았습니다. CUDA는 GPU를 C로 직접 프로그래밍하는 길을 열었고, 과학 계산 커뮤니티가 GPU로 본격적으로 이동하는 계기가 되었습니다.

---

## 3. SIMT — Single Instruction, Multiple Threads

Tesla 아키텍처에서 NVIDIA가 제안한 핵심 실행 모델이 **SIMT**입니다.

### SIMD와의 차이

CPU의 SIMD(Single Instruction, Multiple Data)와 이름이 유사하지만 실제로는 다릅니다.

| | SIMD | SIMT |
|:---|:---|:---|
| 추상화 단위 | 벡터 레인 | 독립 스레드 |
| 레지스터 | 공유 벡터 레지스터 | 스레드별 개별 레지스터 |
| 분기 처리 | 마스크를 명시적으로 관리 | 하드웨어가 처리 |
| 프로그래밍 모델 | 벡터 연산을 직접 표현 | 스칼라 코드를 작성 |

SIMT의 핵심은 다음과 같습니다. **프로그래머는 스칼라 코드를 작성하고, 하드웨어가 스레드들을 묶어 병렬로 실행합니다.** 덕분에 GPU 프로그래밍의 진입 장벽이 크게 낮아졌습니다.

### Warp — 실행의 기본 단위

SIMT에서 실제 병렬 실행의 단위는 **Warp**입니다. Warp는 32개의 스레드 묶음으로, 매 사이클에 동일한 명령어를 함께 실행합니다.

```
스레드 계층 구조
Thread  → 가장 작은 실행 단위. 고유한 레지스터와 PC를 가집니다.
Warp    → 32개 Thread의 묶음. 하드웨어 스케줄링 단위입니다.
Block   → 여러 Warp의 묶음. Shared Memory를 공유하고 __syncthreads()로 동기화합니다.
Grid    → 여러 Block의 묶음. 하나의 커널 실행 단위입니다.
```

SM은 여러 Warp를 동시에 보유(in-flight)할 수 있습니다. 특정 Warp가 메모리 접근으로 인해 대기(stall) 상태가 되면, 스케줄러는 준비된 다른 Warp로 즉시 전환합니다. 이를 **Warp Latency Hiding**이라 하며, GPU가 메모리 지연을 감추는 핵심 메커니즘입니다.

### Branch Divergence

Warp 내 32개의 스레드는 항상 같은 명령어를 실행해야 합니다. 그런데 스레드마다 조건 분기 결과가 다르면 어떻게 될까요?

```c
// threadIdx.x 가 짝수냐 홀수냐에 따라 다른 경로로 분기
if (threadIdx.x % 2 == 0) {
    doA();
} else {
    doB();
}
```

하드웨어는 **Active Mask**를 사용해 두 경로를 순서대로 실행합니다.

```
Cycle 1~N:  [T0 T2 T4 ... T30] 활성화 → doA() 실행
Cycle N~M:  [T1 T3 T5 ... T31] 활성화 → doB() 실행
```

두 경로가 순차적으로 실행되므로 최악의 경우 처리량이 절반으로 줄어듭니다. 이를 **Warp Divergence**라 하며, GPU 커널 최적화에서 반드시 고려해야 하는 문제입니다.

---

## 4. SM — Streaming Multiprocessor

SM은 GPU의 핵심 연산 블록입니다. Tesla(G80) SM의 구성은 다음과 같습니다.

```
Tesla SM (G80)
├── 8× SP (Scalar Processor, INT/FP32 ALU)
├── 2× SFU (Special Function Unit: sin, cos, sqrt, rcp 등)
├── Instruction Cache
├── Warp Scheduler (1개)
├── Register File (8,192 × 32-bit)
└── Shared Memory (16 KB)
```

**Register File**: 모든 스레드 컨텍스트가 레지스터 파일에 올라와 있습니다. Warp 전환 시 별도의 컨텍스트 저장/복원이 필요하지 않습니다. 이 zero-overhead switching이 GPU Warp 스케줄링의 핵심입니다.

**Shared Memory**: 같은 Block 내 스레드들이 공유하는 on-chip 메모리입니다. 속도는 L1 캐시 수준이지만 프로그래머가 명시적으로 관리해야 합니다. 스레드 간 데이터 공유나 글로벌 메모리 접근 횟수를 줄이는 데 활용합니다.

---

## 5. Fermi 아키텍처 — GPU 컴퓨팅의 완성

Tesla가 GPGPU의 문을 열었다면, **Fermi(GF100, 2010)** 는 GPU를 진정한 컴퓨팅 플랫폼으로 완성한 아키텍처입니다.

### 주요 변화

```
Fermi SM
├── 32× CUDA Core (FP32/INT32 ALU) — Tesla 대비 4배
├── 4× SFU
├── 16× Load/Store Unit
├── 2× Warp Scheduler (Dual-Issue 지원)
├── Register File (32,768 × 32-bit)
└── L1 Cache / Shared Memory (64 KB, 비율 조정 가능)
```

**Dual Warp Scheduler**: SM당 Warp Scheduler가 2개로 늘었습니다. 매 사이클 최대 2개의 Warp를 동시에 이슈할 수 있어 실행 유닛을 더 촘촘하게 채울 수 있습니다.

**L1/L2 캐시 계층 도입**: Tesla에는 캐시가 없었습니다. Fermi에서 SM별 L1(16~48 KB)과 전체 공유 L2(768 KB)가 도입되면서 불규칙한 메모리 접근 패턴에서의 성능 하락이 크게 줄었습니다.

**ECC 지원**: 과학 계산에서 비트 오류는 치명적입니다. Fermi부터 메모리 전반에 ECC가 적용됩니다.

**IEEE 754-2008 완전 준수**: Tesla에서 불완전했던 배정밀도(FP64) 연산이 IEEE 표준을 완전히 만족하게 되었습니다. HPC 시장에 본격적으로 진입하는 데 핵심적인 변화였습니다.

### Fermi 전체 구조

```
Fermi (GF100)
├── GPC (Graphics Processing Cluster) × 4
│   └── SM × 4
│       └── CUDA Core × 32
├── L2 Cache (768 KB, 공유)
├── Memory Controller × 6 (GDDR5, 총 384-bit 버스)
└── 총 CUDA Core: 512개
```

Fermi는 CUDA 2.0과 함께 출시되면서 C++ 문법, 재귀 호출, 함수 포인터 등을 GPU에서 지원하기 시작했습니다. Tesla에서 제한적으로만 가능했던 것들이 범용 언어 수준으로 확장되었습니다.

---

## 정리

| | Tesla (G80, 2006) | Fermi (GF100, 2010) |
|:---|:---:|:---:|
| CUDA Core / SM | 8 | 32 |
| Warp Scheduler / SM | 1 | 2 |
| L1 Cache | X | 16~48 KB |
| L2 Cache | X | 768 KB |
| FP64 | 부분 지원 | IEEE 754 완전 준수 |
| ECC | X | O |
| Shared Memory | 16 KB | 16 or 48 KB |

Tesla는 SIMT와 CUDA라는 개념을 제안한 아키텍처이고, Fermi는 그 위에서 실제 HPC 워크로드를 실행할 수 있는 기반을 완성한 아키텍처입니다.

다음 글에서는 Kepler부터 시작해 Blackwell까지, 세대별로 어떤 문제를 해결하려 했고 아키텍처가 어떤 방향으로 진화해왔는지 살펴봅니다.

---

*이 포스트의 영문 버전은 상단 언어 스위처를 통해 확인할 수 있습니다.*
