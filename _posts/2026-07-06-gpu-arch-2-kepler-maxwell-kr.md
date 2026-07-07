---
layout: post
title: "GPU 아키텍처 #2: Kepler와 Maxwell - 효율성의 탐구"
subtitle: "192코어 SMX의 실험, Quadrant 설계로의 수렴, 그리고 스케줄링의 진화"
tags: [GPU, Architecture, CUDA, NVIDIA, Kepler, Maxwell, Computer-Architecture]
lang: kr
translation-url: /2026-07-06-gpu-arch-2-kepler-maxwell-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 |
|:--:|:---|
| 1 | [GPU의 출발과 SIMT의 탄생 - Tesla, Fermi](/2026-04-12-gpu-arch-1-tesla-fermi-kr/) |
| **2** | **Kepler와 Maxwell - 효율성의 탐구** |
| 3 | Pascal, Volta, Ampere - 컴퓨팅 중심으로 |
| 4 | GPU 메모리 시스템과 최적화 |
| 5 | GPU 내부 해부 - 파이프라인과 실행 유닛 |

---

## 1. Fermi의 한계: 다음 세대의 출발점

Fermi(GF100, 2010)는 L1/L2 캐시 도입, ECC 지원, Dual Warp Scheduler 등으로 GPU를 진정한 컴퓨팅 플랫폼으로 완성했습니다. 그러나 40nm 공정에서 뽑아낼 수 있는 성능과 전력 효율은 한계에 다다랐습니다.

문제는 두 가지였습니다.

첫째, **전력 소비**입니다. GF100은 다이 크기 529mm², 트랜지스터 30억 개, TDP 250W로, 당시 기준으로 극단적인 설계였습니다. HPC 클러스터에 도입하기에는 랙당 소비 전력이 과했습니다.

둘째, **CPU 연동의 비효율**입니다. Fermi는 CPU에서 GPU로 이어지는 워크 큐가 단 1개였습니다. MPI 멀티 프로세스 환경에서 여러 CPU 코어가 GPU에 작업을 보내도 하나씩 직렬 처리될 수밖에 없었습니다.

NVIDIA는 28nm 공정으로의 전환과 함께 두 세대에 걸쳐 이 문제를 해결해 나갔습니다.

---

## 2. Kepler: 규모의 도전 (2012)

### SMX: 192코어를 선택한 이유

Kepler(GK104/GK110, 2012)의 첫인상은 SM당 192개 CUDA Core입니다. Fermi의 32코어에서 6배로 뛴 수치입니다.

이 선택의 배경은 **클럭 속도와 코어 수의 트레이드오프**입니다. 같은 목표 처리량을 달성할 때, 소수의 코어를 높은 클럭으로 돌리는 방식은 클로킹 로직 자체의 전력 소비가 커집니다. Kepler는 반대로 낮은 클럭에서 더 많은 코어를 동작시켜 **성능/전력비를 Fermi 대비 3배** 끌어올렸습니다.

SM의 이름도 변경되었습니다. Fermi의 SM은 Kepler에서 **SMX**(Streaming Multiprocessor eXtended)로 불립니다.

```
Fermi SM (GF100)           Kepler SMX (GK110)
────────────────            ──────────────────────────
 32 CUDA Cores               192 CUDA Cores
 Warp Sched ×2               Warp Sched ×4
  (각 1 IDU)                  (각 2 IDU = 클럭당 8 이슈)
 DP Unit ×16                 DP Unit ×64
 SFU ×4                      SFU ×32
 LD/ST ×16                   LD/ST ×32
 Reg File 32,768×32b=128KB   Reg File 65,536×32b=256KB
 L1+Shared 64KB (공유)       L1+Shared 64KB (공유)
 최대 48 warps/SM            최대 64 warps/SMX, 16 블록/SMX
```

GK110의 경우 SMX 15개로 총 2,880개의 CUDA Core를 탑재했습니다.

### 4 Warp Scheduler와 ILP 의존

SMX는 Warp Scheduler를 4개로 늘리고 각 스케줄러에 **IDU(Instruction Dispatch Unit)를 2개**씩 배치했습니다. 클럭당 최대 8개의 명령어를 동시에 이슈할 수 있습니다.

단, 주의할 점이 있습니다. SMX에서 192개 코어는 4개 스케줄러 사이에서 공유됩니다. 스케줄러당 할당 코어가 48개이지만 warp 크기는 32개입니다. 이 16코어의 갭을 메우려면 **ILP(Instruction-Level Parallelism)** 가 필요합니다. 즉, 단일 warp에서 연속된 독립적인 명령어들을 동시에 이슈해야만 코어 활용률이 올라갑니다. Fermi에서는 warp 수(TLP)만으로 latency를 숨기는 데 충분했지만, Kepler에서는 ILP를 함께 고려한 커널 설계가 요구되었습니다.

---

## 3. Kepler의 소프트웨어 혁신

### Dynamic Parallelism

Fermi까지는 GPU 커널이 완료되면 제어권이 CPU로 돌아와야 다음 커널을 launch할 수 있었습니다. 계층적인 연산 - 예를 들어 병렬 BVH(Bounding Volume Hierarchy) 탐색처럼 데이터에 따라 하위 작업이 동적으로 생성되는 경우 - 에서는 CPU와 GPU 사이의 왕복 비용이 병목이었습니다.

GK110(Compute Capability 3.5)에서 도입된 **Dynamic Parallelism**은 커널이 CPU 개입 없이 GPU에서 직접 새 커널을 launch하는 기능입니다.

```
기존 방식 (Fermi까지)          Dynamic Parallelism (Kepler GK110)
────────────────────           ──────────────────────────────────
CPU: kernel_A launch           CPU: kernel_A launch
GPU: kernel_A 실행                GPU: kernel_A 실행
  CPU로 복귀                          ↳ kernel_B launch (GPU 내부)
CPU: kernel_B launch                  GPU: kernel_B 실행
GPU: kernel_B 실행                    ↳ kernel_C launch ...
  CPU로 복귀                    CPU: 최종 결과만 수신
CPU: ...
```

트리 탐색, 적응형 메시 정제, 희소 행렬 처리 등 재귀적 패턴에서 CPU↔GPU 왕복 횟수를 대폭 줄입니다.

### Hyper-Q

Fermi는 CPU에서 GPU로 향하는 하드웨어 워크 큐가 1개뿐이었습니다. MPI 환경에서 여러 CPU 코어가 동시에 GPU 작업을 투입하려 해도 단일 큐를 통과해야 했습니다.

**Hyper-Q**는 이 연결을 **32개의 독립 하드웨어 큐**로 확장합니다. 각 MPI 태스크, CUDA 스트림, CPU 스레드가 별도의 큐를 가질 수 있으므로 GPU 내 유휴 SMX가 생기는 상황을 줄일 수 있습니다.

```
Fermi                       Kepler Hyper-Q
──────                      ────────────────────────
CPU Core 0 ─┐               CPU Core 0 ──→ [큐 0 ]─┐
CPU Core 1 ─┤               CPU Core 1 ──→ [큐 1 ] │
CPU Core 2 ─┼─→ [큐 1개]    CPU Core 2 ──→ [큐 2 ] ├─→ GPU
CPU Core 3 ─┤               ...             ...      │
...         ─┘               MPI Task N ──→ [큐 31]─┘
             ↓               (최대 32개 동시)
            GPU
```

### Warp Shuffle

Warp 내 스레드 간 데이터를 교환하려면 기존에는 Shared Memory를 거쳐야 했습니다. 쓰기 → 동기화 → 읽기의 3단계가 필요했습니다.

CC 3.0부터 지원되는 **Warp Shuffle 명령어**(`__shfl_sync()`)는 레지스터 간 직접 교환을 허용합니다. Shared Memory 접근 없이 warp reduction을 구현할 수 있습니다.

```cuda
// warp 내 합산 - Shared Memory 없이
int val = threadIdx.x;
for (int offset = 16; offset > 0; offset >>= 1)
    val += __shfl_down_sync(0xffffffff, val, offset);
// lane 0에 warp 합계 누적
```

---

## 4. Maxwell: 설계의 정제 (2014)

### 192코어 SMX의 문제

Kepler의 192코어 SMX는 처리량을 늘렸지만, 스케줄러당 코어 수(48개)가 warp 크기(32개)와 맞지 않는 구조적 불일치를 낳았습니다. 이를 해소하기 위해 ILP가 필요했고, 그만큼 컴파일러와 프로그래머의 부담이 늘었습니다.

Maxwell(GM107/GM204, 2014)의 답은 **축소와 전용화**였습니다. SM당 CUDA Core 수를 128개로 줄이는 대신, 내부를 4개의 **Quadrant**로 완전히 분리했습니다.

### SMM: Quadrant 분할

Maxwell SM은 **SMM**(Streaming Multiprocessor Maxwell)으로 불립니다.

```
Maxwell SMM (GM204, 128 CUDA Cores)
┌─────────────────────┬─────────────────────┐
│   Quadrant 0        │   Quadrant 1        │
│   Warp Scheduler    │   Warp Scheduler    │
│   32 CUDA Cores     │   32 CUDA Cores     │
│   (전용)            │   (전용)            │
├─────────────────────┼─────────────────────┤
│   Quadrant 2        │   Quadrant 3        │
│   Warp Scheduler    │   Warp Scheduler    │
│   32 CUDA Cores     │   32 CUDA Cores     │
│   (전용)            │   (전용)            │
└─────────────────────┴─────────────────────┘
         Shared Memory 96KB (전용)
         L1 Cache + Texture Cache (분리)
```

각 스케줄러는 32개의 코어를 **독점 소유**합니다. 32 = warp 크기이므로, 스케줄러는 단일 이슈(single-issue)만으로 담당 코어를 100% 활용할 수 있습니다. Kepler에서 ILP를 통해 억지로 메워야 했던 코어 활용률 갭이 설계 수준에서 제거되었습니다.

결과는 수치로 확인됩니다. **CUDA Core당 전달 성능이 Kepler 대비 40% 향상**, SM 전체 효율은 Kepler GK104 대비 2배입니다. 이는 28nm 공정을 유지하면서 얻어낸 개선입니다.

![SM 구조 비교: Fermi → Kepler → Maxwell](/assets/img/posts/gpu-arch-2/sm-compare.png)

### Shared Memory의 완전 독립

Fermi와 Kepler에서는 L1 Cache와 Shared Memory가 **같은 64KB 온칩 스토리지를 나눠 썼습니다.** L1을 넓히면 Shared Memory가 줄고, 반대도 마찬가지였습니다. 커널 launch 시 `cudaFuncSetCacheConfig()`로 비율을 설정해야 했습니다.

Maxwell은 이 공유를 끊었습니다. Shared Memory에 **전용 온칩 스토리지**가 할당됩니다(GM107: 64KB, GM204: 96KB). L1 Cache는 Texture Cache와 병합되어 별도로 운영됩니다.

```
Fermi / Kepler              Maxwell
──────────────              ─────────────────────
┌──────────────┐            ┌────────────────┐
│  64KB 공유   │            │ Shared Mem     │
│  ┌──┬──────┐ │            │ (64~96KB 전용) │
│  │L1│Shared│ │            └────────────────┘
│  │16│ 48KB │ │            ┌────────────────┐
│  └──┴──────┘ │            │ L1 + Tex Cache │
└──────────────┘            │    (분리)      │
(또는 48/16 비율)            └────────────────┘
```

덕분에 L1 hit rate와 Shared Memory 사용량이 상호 간섭 없이 독립적으로 결정됩니다.

### 컴파일러 기반 레지스터 재사용

Kepler까지는 레지스터 읽기 충돌(bank conflict)을 **Operand Collector**가 런타임에 해소했습니다. Maxwell은 이 역할을 컴파일러로 옮겼습니다. 컴파일러가 **Register Reuse Cache**를 관리해, 직전에 사용된 피연산자를 캐시에 보유하고 bank conflict 없이 재사용합니다. 런타임 충돌 해소 로직이 사라진 만큼 디스패치 경로가 단순해졌습니다.

### CUDA Unified Memory (CUDA 6.0)

Maxwell과 함께 출시된 CUDA 6.0은 **Unified Memory**를 도입했습니다. `cudaMallocManaged()`로 할당된 메모리는 CPU와 GPU가 동일한 포인터로 접근할 수 있으며, 런타임이 페이지 단위로 자동 마이그레이션을 처리합니다.

```cuda
// 이전 방식: CPU/GPU 메모리 명시적 분리
float *h_data, *d_data;
h_data = (float*)malloc(size);
cudaMalloc(&d_data, size);
cudaMemcpy(d_data, h_data, size, cudaMemcpyHostToDevice);
kernel<<<grid, block>>>(d_data);
cudaMemcpy(h_data, d_data, size, cudaMemcpyDeviceToHost);

// Unified Memory: 포인터 하나로 CPU/GPU 모두 접근
float *data;
cudaMallocManaged(&data, size);
init_on_cpu(data);           // CPU에서 초기화
kernel<<<grid, block>>>(data); // GPU에서 사용 - 자동 마이그레이션
result = data[0];            // CPU에서 결과 읽기
```

프로그래머가 `cudaMemcpy()`를 직접 호출할 필요가 없어져 개발 부담이 크게 줄었습니다. 단, 마이그레이션 오버헤드가 발생하므로 성능이 중요한 경로에서는 여전히 명시적 메모리 관리가 권장됩니다.

---

## 5. 스케줄링 변화 흐름

세 아키텍처의 Warp Scheduling 구조를 비교합니다.

```
Fermi SM               Kepler SMX             Maxwell SMM
──────────────         ──────────────         ──────────────
Sched A (1 IDU)        Sched A (2 IDU)        Quad 0: Sched
Sched B (1 IDU)        Sched B (2 IDU)          → 32코어 전용
  ↓                    Sched C (2 IDU)        Quad 1: Sched
32코어 공유             Sched D (2 IDU)          → 32코어 전용
                          ↓                   Quad 2: Sched
클럭당 최대 2 이슈      192코어 공유              → 32코어 전용
                                             Quad 3: Sched
TLP로 latency 은닉      클럭당 최대 8 이슈        → 32코어 전용
충분                    TLP + ILP 모두 필요
                                             single-issue로
                                             코어 100% 활용
                                             SM당 최대 block: 32
                                             (Kepler 16 → 2배)
```

| | Fermi | Kepler | Maxwell |
|:---|:---:|:---:|:---:|
| Warp Scheduler / SM | 2 | 4 | 4 |
| IDU / Scheduler | 1 | 2 | 2 |
| 코어 / Scheduler | 16 | 48 | **32 (= warp)** |
| Latency 은닉 전략 | TLP | TLP + ILP | TLP |
| Max Warp / SM | 48 | 64 | 64 |
| Max Block / SM | 8 | 16 | **32** |
| Shared Memory 구조 | L1 공유 | L1 공유 | **독립** |

---

## 인터커넥트 및 외부 채널

### PCIe 호스트 인터페이스

Kepler는 NVIDIA GPU 최초로 **PCIe 3.0 x16**을 채택한 세대다. 이론 단방향 대역폭은 16 GB/s로 PCIe 2.0(8 GB/s)의 2배다. Maxwell도 PCIe 3.0 x16을 유지한다.

### NVENC / NVDEC

| | Kepler (GK104/GK110) | Maxwell (GM204/GM200) |
|:---|:---:|:---:|
| NVENC 세대 | **1세대** | **2세대** |
| 인코드 코덱 | H.264 | H.264 + **HEVC** |
| NVDEC 세대 | VP5 | VP6 |
| 디코드 코덱 | H.264, VC-1 | +**HEVC 디코드** |

Kepler는 최초로 하드웨어 H.264 인코더(NVENC)를 탑재했다. 이전 세대(Tesla/Fermi)는 디코드 전용이었다. Maxwell은 HEVC(H.265) 인코드와 디코드를 추가했다.

### 디스플레이 출력 (소비자 GPU 레퍼런스 카드 기준)

| 제품 | DP | HDMI | DVI |
|:---|:---:|:---:|:---:|
| GTX 680 (GK104) | 1.2 ×1 | 1.4 ×1 | ×2 |
| GTX 980 Ti (GM200) | 1.2 ×3 | 2.0 ×1 | ×1 |

---

## 정리

| | Kepler GK110 (2012) | Maxwell GM204 (2014) |
|:---|:---:|:---:|
| CUDA Core / SM | 192 | 128 |
| SM 내부 구조 | Monolithic | 4 Quadrant |
| Warp Scheduler / SM | 4 (각 2 IDU) | 4 (각 전용 32코어) |
| 코어 / Scheduler | 48 | **32** |
| 레지스터 파일/SM | 256KB | 256KB |
| L2 캐시 | GK110: 1.5MB | GM204: 2MB |
| DP Unit / SM | 64 | - (GM204 소비자향) |
| Shared Memory | 64KB (L1 공유) | 96KB (전용) |
| PCIe | **3.0 x16** | 3.0 x16 |
| NVENC | **1세대** (H.264) | **2세대** (H.264+HEVC) |
| 대표 기능 | Dynamic Parallelism, Hyper-Q, Warp Shuffle | Unified Memory, Quadrant 설계 |
| 공정 | 28nm | 28nm |
| 대표 제품 | Tesla K40, GTX 680 | GTX 980, GTX Titan X |

Kepler는 규모를 통해 처리량을 끌어올렸고, Maxwell은 구조를 정제해 같은 공정에서 효율을 2배로 높였습니다.

다음 글에서는 HBM 메모리와 NVLink를 도입한 Pascal, 그리고 AI 가속을 위한 Tensor Core를 처음 탑재한 Volta를 다룹니다.

---

## References

- NVIDIA. *NVIDIA's Next Generation CUDA Compute Architecture: Kepler GK110/GK210* (Whitepaper, 2012). [PDF](https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/tesla-product-literature/NVIDIA-Kepler-GK110-GK210-Architecture-Whitepaper.pdf)
- NVIDIA. *5 Things You Should Know About the New Maxwell GPU Architecture*. NVIDIA Developer Blog, 2014. [Link](https://developer.nvidia.com/blog/5-things-you-should-know-about-new-maxwell-gpu-architecture/)
- NVIDIA. *Maxwell: The Most Advanced CUDA GPU Ever Made*. NVIDIA Developer Blog, 2014. [Link](https://developer.nvidia.com/blog/maxwell-most-advanced-cuda-gpu-ever-made/)
- NVIDIA. *Maxwell Tuning Guide*. CUDA Toolkit Documentation. [Link](https://docs.nvidia.com/cuda/maxwell-tuning-guide/)
- NVIDIA. *Tuning CUDA Applications for Kepler*. CUDA Toolkit Documentation. [Link](https://docs.nvidia.com/cuda/archive/11.3.1/pdf/Kepler_Tuning_Guide.pdf)
- Chester Lam. *Maxwell: Nvidia's Silver 28nm Hammer*. Chips and Cheese, 2023. [Link](https://chipsandcheese.com/p/maxwell-nvidias-silver-28nm-hammer)

---

*이 포스트의 영문 버전은 상단 언어 스위처를 통해 확인할 수 있습니다.*
