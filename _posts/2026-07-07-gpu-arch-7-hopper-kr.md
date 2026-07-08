---
layout: post
title: "GPU 아키텍처 #7: Hopper - Transformer Engine과 FP8"
subtitle: "4세대 Tensor Core의 FP8 가속, Transformer Engine, Thread Block Cluster, GH200 Grace Hopper"
tags: [GPU, Architecture, CUDA, NVIDIA, Hopper, TensorCore, Transformer, Computer-Architecture]
lang: kr
translation-url: /2026-07-07-gpu-arch-7-hopper-en/
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
| **7** | **Hopper - Transformer Engine과 FP8** |
| 8 | [Ada Lovelace - 3세대 RT Core와 96MB L2](/2026-07-07-gpu-arch-8-ada-lovelace-kr/) |
| 9 | [Blackwell - FP4 Tensor Core와 멀티다이 설계](/2026-07-08-gpu-arch-9-blackwell-kr/) |
| 10 | GPU 메모리 시스템과 최적화 |

---

## Ampere 이후의 병목

A100은 대규모 언어 모델 학습의 표준 플랫폼이 됐다. GPT-3(175B) 학습에는 수백 장의 A100이 수십 일을 소비했다. 규모가 커질수록 병목이 뚜렷해졌다. Transformer 아키텍처의 핵심 연산인 GEMM(행렬 곱)은 Ampere의 BF16 TC로 고속화됐지만, 정밀도 손실 없이 더 낮은 비트폭으로 내려가는 방법이 없었다. INT8은 추론에서 사용됐지만 학습에는 동적 범위가 부족했다.

동시에 Transformer의 계산 패턴이 병목의 형태를 바꿨다. Attention 연산은 입력 길이의 제곱에 비례하는 메모리와 계산을 요구했다. 긴 시퀀스에서 SM 하나가 처리하는 타일 간 데이터 교환은 L2를 통해 우회해야 했다.

Hopper(2022)는 이 두 병목을 직접 겨냥했다. **Transformer Engine**과 **FP8**으로 학습 단계의 정밀도 장벽을 낮추고, **Thread Block Cluster**와 **Distributed Shared Memory**로 SM 간 통신 비용을 줄였다.

---

## 다이 스펙

| | Ampere GA100 | Hopper GH100 |
|:---|:---:|:---:|
| 공정 | TSMC 7nm | **TSMC 4nm (N4)** |
| 트랜지스터 | 54.2B | **80B** |
| 다이 면적 | 826mm² | **814mm²** |
| SM 수 (전체) | 132 | **144** |
| SM 수 (H100 SXM5 활성) | 108 (A100) | **132** |
| FP32/SM | 64 | **128** |
| FP64/SM | 32 | **64** |
| TC 세대 | 3세대 | **4세대** |
| L2 캐시 | 40 MB | **50 MB** |
| 대표 제품 | A100 SXM4 | **H100 SXM5** |

공정이 TSMC 7nm에서 4nm(N4)로 전환됐다. 동일한 다이 면적(약 820mm²)에서 트랜지스터 수가 54.2B에서 80B으로 늘었다. FP32와 FP64 코어 모두 SM당 2배로 증가했다.

---

## 4세대 Tensor Core와 FP8

### FP8: 새로운 정밀도 형식

**FP8**은 Hopper에서 처음 도입된 8비트 부동소수점 형식이다. 두 가지 변형이 있다.

```
FP32  (32비트): 부호 1 | 지수 8 | 가수 23
BF16  (16비트): 부호 1 | 지수 8 | 가수  7
FP16  (16비트): 부호 1 | 지수 5 | 가수 10
TF32  (19비트): 부호 1 | 지수 8 | 가수 10

FP8 E4M3 ( 8비트): 부호 1 | 지수 4 | 가수 3  ← 순전파 활성값
FP8 E5M2 ( 8비트): 부호 1 | 지수 5 | 가수 2  ← 역전파 기울기
```

E4M3는 가수 비트가 3개로 정밀도가 낮지만 지수 범위가 충분해 순전파 활성값과 가중치 표현에 적합하다. E5M2는 지수 비트를 하나 더 가져 동적 범위가 넓다. 역전파에서 기울기 값의 분포가 넓기 때문이다.

4세대 Tensor Core는 FP8 × FP8 행렬 곱을 FP32로 누산한다. INT8과 동일한 비트폭이지만 부동소수점이므로 정수 연산이 불가능한 작업에서 활용 가능하다.

### 처리량 비교

![A100 SXM4 vs H100 SXM5 Tensor Core 처리량 비교](/assets/img/posts/gpu-arch-7/perf-compare.png)

| 정밀도 | A100 SXM4 Dense | H100 SXM5 Dense | H100 SXM5 Sparse |
|:---|---:|---:|---:|
| FP64 TC | 19.5 TFLOPS | **66.9 TFLOPS** | 133.8 TFLOPS |
| TF32 TC | 156 TFLOPS | **494.7 TFLOPS** | 989.4 TFLOPS |
| BF16/FP16 TC | 312 TFLOPS | **989.4 TFLOPS** | 1,978.9 TFLOPS |
| FP8 TC | 없음 | **1,978.9 TFLOPS** | 3,957.8 TFLOPS |
| INT8 TC | 624 TOPS | **1,978.9 TOPS** | 3,957.8 TOPS |

FP8 Dense 처리량(1,978.9 TFLOPS)은 A100 BF16 TC Dense(312 TFLOPS)의 6.3배다. BF16/FP16 대비로도 H100 FP8은 Dense에서 2배다.

---

## Transformer Engine

### 문제: FP8 학습의 정밀도 관리

FP8로 직접 학습하면 수치 불안정이 발생한다. 각 Transformer 레이어는 다른 통계적 분포를 가진다. 첫 번째 레이어의 활성값 스케일이 마지막 레이어와 다를 수 있고, 기울기는 더 넓은 범위를 가진다. 고정된 스케일로 FP8에 맞추면 대부분의 값이 언더플로 또는 오버플로가 된다.

### 해결: 자동 정밀도 전환

**Transformer Engine**은 NVIDIA가 제공하는 라이브러리+하드웨어 조합이다. 레이어별로 텐서의 통계를 추적하고, GEMM 직전에 FP8로 변환한 뒤 결과를 BF16/FP32로 복원한다.

```
Transformer 레이어 실행 흐름 (Transformer Engine)
─────────────────────────────────────────────────────────

입력 (BF16/FP32)
   │
   ▼
[스케일 팩터 계산]  ← 이전 스텝의 절대값 최대값 amax 기록
   │                    scale = 448 / amax  (E4M3 최대값 기준)
   ▼
[FP8 변환: Input × scale → FP8 E4M3]
   │
   ▼
[FP8 × FP8 Tensor Core GEMM]  ← H100 4세대 TC
   │           ↑
   │    [FP8 가중치: 사전 변환 후 저장]
   ▼
[FP32 누산 결과]
   │
   ▼
[descale: 결과 / scale → BF16/FP32 출력]
   │
   ▼
다음 레이어 (BF16/FP32)
```

스케일 팩터는 텐서별(per-tensor) 또는 채널별(per-channel)로 관리된다. Transformer Engine은 이 과정을 자동화한다. CUDA 코드를 직접 작성하지 않아도 `transformer_engine.pytorch`를 통해 레이어를 교체하면 된다.

```python
import transformer_engine.pytorch as te

# 기존 PyTorch Linear → Transformer Engine Linear으로 교체만 하면 됨
# layer = torch.nn.Linear(in_features, out_features)
layer = te.Linear(in_features, out_features, fp8_wgrad=True)

# fp8_autocast 컨텍스트에서 실행 시 자동으로 FP8 GEMM 사용
with te.fp8_autocast(enabled=True):
    output = layer(input)
```

역전파에서는 기울기를 E5M2 형식으로 관리해 넓은 동적 범위를 확보한다.

---

## Hopper SM 구조

### Volta/Ampere와의 비교

```
Hopper GH100 Sub-core
─────────────────────────────────
Warp Scheduler
Dispatch Unit ×2
32 FP32              (전통 FP32)
16 FP64              (HPC)
32 FP32/INT32        (이중 모드)
 1 TC (4세대)         FP8/FP16/BF16/TF32/INT8/FP64
 8 LD/ST   4 SFU

SM 합계 (4 Sub-core):
  128 FP32, 64 FP64, 4 TC
```

| 항목 | Ampere GA100 | Hopper GH100 |
|:---|:---:|:---:|
| FP32/SM | 64 | **128** |
| FP64/SM | 32 | **64** |
| TC 세대 | 3세대 | **4세대** |
| TC 지원 정밀도 | TF32/BF16/FP16/INT8/FP64 TC | +**FP8 (E4M3, E5M2)** |
| 2:4 Sparsity | 있음 | **있음** |
| RT Core | 없음 | **없음 (데이터센터 전용)** |
| Distributed Shared Memory | 없음 | **있음** |
| Unified L1+Shared | 192KB | **228KB** |
| 최대 Shared Memory | 164KB | **228KB** |
| 레지스터 파일/SM | 256KB | 256KB |
| 최대 Warps/SM | 64 | 64 |
| 최대 Blocks/SM | 32 | 32 |

GH100 SM은 최대 **64 warps/SM, 32 블록/SM**을 동시에 보유할 수 있다. 레지스터 파일은 256KB/SM으로 Ampere와 동일하다.

H100(GH100)에는 **RT Core가 없다**. Turing과 Ampere GA102의 RT Core는 소비자 GPU 전용 기능으로, 데이터센터 가속기에는 포함되지 않는다. A100(GA100)도 RT Core가 없으며, H100은 이 정책을 계승한다.

Hopper SM은 Ampere GA100 대비 FP32를 2배(64→128), FP64를 2배(32→64)로 늘렸다. 공정 전환(7nm→4nm)이 같은 다이 면적에서 이 증가를 가능하게 했다.

Unified L1+Shared Memory도 192KB에서 228KB로 증가했으며, 전체를 Shared Memory로 구성할 수 있다(최대 228KB). 큰 타일 크기의 GEMM과 Flash Attention 구현에서 활용된다.

---

## Thread Block Cluster와 Distributed Shared Memory

### 기존 한계

CUDA 프로그래밍 모델에서 Thread Block은 하나의 SM에 할당된다. 같은 GPC 내의 다른 SM에 있는 Shared Memory에 직접 접근할 수 없다. 데이터 공유는 L2 캐시를 경유해야 했다.

```
기존 모델 (Ampere까지):
SM 0 (Shared Mem A)  ←→  L2 Cache  ←→  SM 1 (Shared Mem B)
         (라운드트립, 수백 사이클)
```

### Thread Block Cluster: 새로운 협력 단위

**Thread Block Cluster**는 같은 GPC 내의 여러 Thread Block을 하나의 협력 단위로 묶는다. CUDA 12에서 도입됐다. 클러스터 내 Thread Block은 동시에 실행이 보장되며, 서로의 Shared Memory에 직접 접근할 수 있다.

```
Hopper Thread Block Cluster (GPC 내):
┌─────────────────────────────────────────────────┐
│  GPC                                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │   SM 0    │  │   SM 1    │  │   SM 2    │   │
│  │ Block 0   │  │ Block 1   │  │ Block 2   │   │
│  │ Shared  ◄─┼──┼─► Shared ◄┼──┼─► Shared  │   │
│  │ Memory    │  │  Memory   │  │  Memory   │   │
│  └───────────┘  └───────────┘  └───────────┘   │
│   ↑─────────────── 직접 SM-to-SM 경로 ──────────┘
│   (L2 우회, 낮은 지연)
└─────────────────────────────────────────────────┘
```

클러스터 크기는 최대 8 Thread Block(HW 제약)이다. Cluster 내 Thread Block 수를 `cluster_dims`로 지정한다.

```cuda
// CUDA 12: Thread Block Cluster 실행
cudaLaunchAttribute attr[1];
attr[0].id = cudaLaunchAttributeClusterDimension;
attr[0].val.clusterDim = {4, 1, 1};  // 4개 Thread Block = 1 Cluster

cudaLaunchKernelEx(&config, my_kernel, args...);

// 커널 내부: Distributed Shared Memory 접근
__global__ void my_kernel() {
    namespace cg = cooperative_groups;
    cg::cluster_group cluster = cg::this_cluster();

    __shared__ float smem[TILE_SIZE];

    // 인접 Block의 Shared Memory 포인터 획득
    float *peer_smem = cluster.map_shared_rank(smem, /* peer_rank */ 1);

    cluster.sync();           // 클러스터 범위 배리어
    float val = peer_smem[threadIdx.x];  // 인접 SM Shared Memory 직접 읽기
}
```

### Flash Attention과 Cluster

Transformer의 Attention 연산은 쿼리(Q), 키(K), 밸류(V) 행렬의 분할(tile) 간 통신이 필요하다. Flash Attention v3는 Hopper의 Thread Block Cluster를 활용해 인접 SM의 KV 타일을 Distributed Shared Memory로 직접 교환한다. L2 경유 없이 낮은 지연으로 KV 타일을 공유해 Attention 계산의 메모리 이동을 줄인다.

---

## NVLink 4.0과 HBM3

### NVLink 4.0

| | Ampere NVLink 3.0 | Hopper NVLink 4.0 |
|:---|:---:|:---:|
| H100/A100당 링크 수 | 12 | **18** |
| 링크당 대역폭 | 25 GB/s 양방향 | **25 GB/s 양방향** |
| GPU당 총 대역폭 | 600 GB/s | **900 GB/s** |

**NVSwitch 3.0**은 한 스위치당 13.6 Tb/s 비전이선 대역폭을 제공한다. DGX H100 시스템에서 8개의 H100은 NVLink 4.0으로 완전 연결된다.

### HBM3

| 제품 | 메모리 | 대역폭 | VRAM |
|:---|:---:|---:|:---:|
| A100 SXM4 80GB | HBM2e | 2,000 GB/s | 80 GB |
| H100 SXM5 80GB | **HBM3** | **3,350 GB/s** | 80 GB |
| H100 PCIe 80GB | HBM2e | 2,000 GB/s | 80 GB |

H100 SXM5의 HBM3 대역폭(3.35 TB/s)은 A100 대비 1.67배다. H100 PCIe는 폼팩터 제약으로 HBM2e를 유지한다.

---

## GH200 Grace Hopper Superchip

**GH200**은 NVIDIA의 첫 CPU+GPU 통합 플랫폼이다. ARM 기반 Grace CPU와 H100 GPU가 **NVLink-C2C(Chip-to-Chip)** 인터커넥트로 연결된다.

```
GH200 Grace Hopper Superchip
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  Grace CPU (ARM Neoverse V2)    H100 GPU (GH100)        │
│  ┌──────────────────────┐       ┌────────────────────┐   │
│  │ 72 Neoverse V2 코어  │       │ 132 SM (Hopper)    │   │
│  │ 96GB LPDDR5X         │       │ 80/96GB HBM3/HBM3e │   │
│  │ 512 GB/s CPU Mem BW  │       │ 3.35 TB/s HBM BW   │   │
│  └──────────┬───────────┘       └──────┬─────────────┘   │
│             │                          │                  │
│             └──── NVLink-C2C ──────────┘                 │
│                   900 GB/s 양방향                         │
│                   (PCIe 5.0 x16 대비 7배)                │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

NVLink-C2C의 핵심은 **일관된 메모리 주소 공간**이다. GPU 커널이 CPU의 LPDDR5X 메모리를 직접 주소 지정할 수 있다. GPU HBM이 부족한 대형 모델 추론에서 CPU 메모리를 연장선으로 사용할 수 있다.

| 항목 | H100 SXM5 (PCIe 기반) | GH200 |
|:---|:---:|:---:|
| CPU-GPU 인터페이스 | PCIe 5.0 x16 (~128 GB/s) | NVLink-C2C (900 GB/s) |
| CPU 메모리 | 별도 DRAM | 96GB LPDDR5X (GPU 직접 접근) |
| 총 사용 가능 메모리 | GPU HBM만 | **HBM + CPU LPDDR5X** |
| 주소 공간 | 분리 | **통합** |

---

## 스케줄링 변화

### Thread Block Cluster

Thread Block Cluster는 Hopper의 가장 큰 스케줄링 변화다. 기존의 Grid → Block → Warp → Thread 계층에 **Cluster**가 추가됐다.

```
실행 계층 (Hopper):
Grid
└─ Cluster  ← 신규 (GPC 단위, 최대 8 Block)
   └─ Thread Block  (SM 단위)
      └─ Warp  (32 Thread)
         └─ Thread
```

클러스터 내 Thread Block은 동시 실행이 보장된다. 이는 기존 Block 간에는 없었던 보장이다. `__cluster_sync()`로 클러스터 범위의 배리어를 수행한다. 클러스터 단위 원자적 연산도 지원한다.

### Warp 스케줄링

개별 Warp 스케줄링은 Volta/Ampere와 동일하다. Per-thread PC 기반 독립 스레드 스케줄링이 유지된다.

### 비동기 실행 심화

Hopper는 비동기 실행을 한 단계 더 확장했다. Warp Specialization 기법을 공식 지원한다: 하나의 Thread Block 내에서 일부 warp는 데이터 적재(`cp.async`)를 전담하고 다른 warp는 Tensor Core 연산을 전담한다. 두 그룹이 `cuda::pipeline`으로 동기화한다.

```cuda
// Warp Specialization: producer-consumer 분리
__global__ void warp_specialized_kernel(...) {
    auto pipeline = cuda::make_pipeline();

    if (warp_is_producer()) {
        // 이 warp는 데이터 적재 전담
        for (int i = 0; i < tiles; i++) {
            cuda::memcpy_async(smem[i % 2], gmem + i * TILE, size, pipeline);
            pipeline.producer_commit();
        }
    } else {
        // 이 warp는 TC 연산 전담
        for (int i = 0; i < tiles; i++) {
            pipeline.consumer_wait();
            __syncwarp();
            wmma::mma_sync(c_frag, a_frag, b_frag, c_frag);
            pipeline.consumer_release();
        }
    }
}
```

---

## 소프트웨어

### CUDA 12.0 (2022)

CUDA 12.0은 Hopper GH100을 지원하는 첫 버전이다.

- Thread Block Cluster API (`cudaLaunchAttributeClusterDimension`)
- Distributed Shared Memory (`cluster.map_shared_rank()`)
- `__cluster_sync()` 배리어
- Warp Specialization 지원 (`cuda::pipeline` 확장)
- FP8 데이터 타입 (`__nv_fp8_e4m3`, `__nv_fp8_e5m2`)

### Transformer Engine

NVIDIA Transformer Engine 라이브러리는 PyTorch / JAX / PaddlePaddle 백엔드를 제공한다. FP8 GEMM, 자동 스케일 팩터 관리, Attention 연산의 혼합 정밀도 실행을 담당한다.

```python
import transformer_engine.pytorch as te
import transformer_engine.common.recipe as recipe

# FP8 학습 설정
fp8_format = recipe.Format.HYBRID  # 순전파 E4M3, 역전파 E5M2
fp8_recipe = recipe.DelayedScaling(
    margin=0,
    interval=1,
    fp8_format=fp8_format,
    amax_history_len=16,   # 스케일 팩터 추정에 사용할 히스토리 길이
    amax_compute_algo="max"
)

model = te.TransformerLayer(hidden_size, ffn_hidden_size, num_heads)

with te.fp8_autocast(enabled=True, fp8_recipe=fp8_recipe):
    output = model(input, attention_mask)
```

### Flash Attention v3

Flash Attention v3는 Hopper 전용 최적화를 포함한다. 4세대 TC의 비동기 실행과 Thread Block Cluster 기반 Distributed Shared Memory를 활용해 Attention 계산을 가속한다. 기존 Flash Attention v2 대비 H100에서 약 1.5-2배 성능 향상이 보고됐다.

---

## 인터커넥트 및 외부 채널

### PCIe 호스트 인터페이스

H100 PCIe 버전은 **PCIe 5.0 x16**을 최초로 도입했다. 이론 단방향 대역폭은 64 GB/s(PCIe 4.0의 2배)다. H100 SXM5도 PCIe 5.0 호스트 인터페이스를 갖추며, GPU 간 주요 통신은 NVLink 4.0이 담당한다.

| 제품 | PCIe 세대 | 단방향 대역폭 |
|:---|:---:|---:|
| H100 SXM5 | **PCIe 5.0 x16** | 64 GB/s |
| H100 PCIe | **PCIe 5.0 x16** | 64 GB/s |
| A100 (참고) | PCIe 4.0 x16 | 32 GB/s |

### HBM3 버스 폭

H100 SXM5의 HBM3는 5개 스택, 스택당 1,024-bit = **총 5,120-bit 버스**를 통해 3,350 GB/s를 제공한다.

### 외부 채널

H100은 데이터센터 전용 가속기다. 다음 기능이 없다.

| 기능 | 상태 |
|:---|:---:|
| RT Core | 없음 |
| NVENC | 없음 |
| NVDEC | 없음 |
| 디스플레이 출력 | 없음 |

---

## 정리

| | Ampere GA100 (A100) | Hopper GH100 (H100) |
|:---|:---:|:---:|
| 공정 | TSMC 7nm | **TSMC 4nm (N4)** |
| FP32/SM | 64 | **128** |
| FP64/SM | 32 | **64** |
| TC 세대 | 3세대 | **4세대** |
| FP8 지원 | 없음 | **E4M3 / E5M2** |
| Transformer Engine | 없음 | **있음** |
| Thread Block Cluster | 없음 | **있음 (최대 8 Block)** |
| Distributed Shared Memory | 없음 | **있음** |
| NVLink | 3.0 (600 GB/s) | **4.0 (900 GB/s)** |
| 메모리 | HBM2e 2 TB/s | **HBM3 3.35 TB/s** |
| L2 캐시 | 40 MB | **50 MB** |
| Shared Memory 최대 | 164KB | **228KB** |
| MIG | 있음 (7 인스턴스) | **있음 (7 인스턴스)** |

Hopper의 중심은 Transformer Engine과 FP8이다. FP8 학습이 가능해짐으로써 H100의 BF16 TC 대비 FP8 TC에서 이론적으로 2배의 처리량을 얻는다. Thread Block Cluster는 SM 간 데이터 공유 비용을 줄여 Flash Attention 같은 타일 간 통신이 많은 알고리즘에서 효과를 발휘한다. GH200은 CPU-GPU 메모리 계층을 통합해 GPU HBM 용량 한계를 극복하는 새로운 방향을 열었다.

다음 포스트에서는 GPU 메모리 시스템을 다룬다: 레지스터 파일, Shared Memory, L1/L2 캐시, DRAM 계층의 구조와 각 아키텍처에 걸친 최적화 기법.

---

## References

- NVIDIA. *NVIDIA Hopper GPU Architecture Whitepaper*, 2022. [PDF](https://resources.nvidia.com/en-us-tensor-core/gtc22-whitepaper-hopper)
- NVIDIA. *NVIDIA H100 Tensor Core GPU Architecture In-Depth*. NVIDIA Developer Blog, 2022.
- NVIDIA. *NVIDIA Transformer Engine*. GitHub, 2022. [Link](https://github.com/NVIDIA/TransformerEngine)
- Shah, J. et al. *FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-precision*. arXiv:2407.08608, 2024.
- NVIDIA. *CUDA C++ Programming Guide: Thread Block Clusters*. CUDA 12 Documentation.
- NVIDIA. *GH200 Grace Hopper Superchip Architecture Whitepaper*, 2023.
