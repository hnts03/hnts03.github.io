---
layout: post
title: "InfiniBand와 RoCE — GPU 클러스터 고속 네트워크의 기반"
subtitle: "RDMA 원리, Verbs API, Lossless Ethernet, DCQCN, GPUDirect RDMA"
tags: [Network, InfiniBand, RoCE, RDMA, HPC, NCCL, GPU-Cluster]
lang: kr
translation-url: /2026-07-07-hpc-network-ib-roce-en/
readtime: true
mathjax: false
---

## GPU 클러스터 통신의 물리적 제약

LLM 학습은 매 파라미터 업데이트마다 모든 GPU의 그래디언트를 동기화한다. NCCL/RCCL이 수행하는 **AllReduce**는 실행 한 번에 `2 × (N-1)/N × message_size`만큼의 데이터를 네트워크로 전달한다. GPU 수백 개가 이 연산을 매 스텝마다 반복한다.

TCP/IP 소켓으로 이 부하를 처리하면 세 가지 병목이 쌓인다.

**커널 개입**: 소켓 호출마다 syscall과 컨텍스트 스위치가 발생한다. 인터럽트 처리가 CPU 사이클을 소비한다.

**메모리 복사**: GPU 메모리 → PCIe → 시스템 DRAM → 커널 소켓 버퍼 → NIC → 네트워크. 반대 방향도 동일하다. 한 번의 전송에 최소 2~3회 memcpy가 포함된다.

**레이턴시**: TCP/IP 스택의 소프트웨어 처리만으로도 최소 50μs 이상이 더해진다.

128 GPU 벤치마크에서 gRPC(TCP) 대비 MPI+NCCL+RDMA가 약 2배의 학습 처리량을 기록한다.

---

## RDMA: 커널을 우회하는 전송

**RDMA**(Remote Direct Memory Access)는 데이터 경로에서 CPU와 커널을 제거한다.

```
[TCP/IP 경로]
GPU HBM → PCIe → 시스템 DRAM → CPU(TCP 스택) → NIC → 네트워크
← 역방향: NIC → DRAM → CPU → DRAM → PCIe → GPU HBM

[RDMA + GPUDirect 경로]
GPU HBM → PCIe → NIC → 네트워크
← NIC → PCIe → GPU HBM
```

핵심 메커니즘은 **메모리 등록(Memory Registration)**이다. 애플리케이션이 `ibv_reg_mr()`로 메모리 영역을 NIC에 등록하면, 해당 페이지가 물리 메모리에 고정(pin)되고 NIC의 IOMMU에 매핑된다. 이후 데이터 전송은 NIC이 직접 DMA로 처리한다. CPU는 개입하지 않는다. 중간 복사 버퍼도 없다.

---

## InfiniBand

### Verbs API

RDMA 프로그래밍의 기반은 **libibverbs**다. 소켓 API와 달리 핫 패스에서 커널 진입이 없다.

```
애플리케이션
   │
   ├─ ibv_reg_mr()           ← 메모리 등록 (초기화 시 한 번)
   │
   ├─ ibv_post_send(QP, WR)  ← WR 제출 (ring buffer write, syscall 없음)
   │     └─ NIC가 WR 폴링 → DMA 실행 → 패킷 전송
   │
   └─ ibv_poll_cq(CQ)        ← 완료 폴링 (busy poll, 인터럽트 없음)
```

핵심 객체:

| 객체 | 설명 |
|:---|:---|
| **QP** (Queue Pair) | Send Queue + Receive Queue 쌍. 연결 단위 |
| **CQ** (Completion Queue) | WR 완료 통지. SQ/RQ 공유 가능 |
| **MR** (Memory Region) | 등록된 pinned 메모리. NIC과 앱이 공유 |

WR operation 종류:

| 연산 | 설명 | 지원 전송 타입 |
|:---|:---|:---|
| SEND / RECV | 양 QP 모두 관여하는 표준 전송 | RC, UC, UD |
| RDMA WRITE | 수신측 CPU 개입 없이 원격 메모리에 쓰기 | RC, UC |
| RDMA READ | 원격 메모리에서 읽기 | RC |
| ATOMIC (CAS/FAA) | Compare-and-Swap, Fetch-and-Add | RC (선택적) |

NCCL은 **RC QP를 통한 RDMA WRITE**를 주로 사용한다. 수신측 CPU 개입이 없고 신뢰성 있는 전송이 보장된다.

### 전송 타입: RC / UC / UD

| | RC | UC | UD |
|:---|:---|:---|:---|
| 전체 명칭 | Reliable Connected | Unreliable Connected | Unreliable Datagram |
| 신뢰성 | ACK/재전송 | 없음 | 없음 |
| 연결 | 1:1 QP | 1:1 QP | 연결 없음 (1:N) |
| RDMA READ | 지원 | 미지원 | 미지원 |
| 주요 용도 | NCCL AllReduce | 드물게 사용 | MPI 제어 메시지, 멀티캐스트 |

### 세대별 대역폭과 레이턴시

| 세대 | 대역폭 (4x 포트) | 상용화 |
|:---|:---:|:---:|
| QDR | 40 Gbps | 2008 |
| FDR | 56 Gbps | 2012 |
| EDR | 100 Gbps | 2015 |
| HDR | 200 Gbps | 2019 |
| **NDR** | **400 Gbps** | 2022 |
| XDR | 800 Gbps | 2025 |

NVIDIA Quantum-2 NDR 스위치의 포트-대-포트 레이턴시는 **130ns**다. NDR NIC의 8바이트 메시지 레이턴시는 약 **0.9μs**, MPI 애플리케이션 레이턴시는 **1~2μs**다.

InfiniBand는 전용 패브릭이다. **Subnet Manager**가 클러스터의 모든 포트에 16-bit LID를 부여하고 라우팅 테이블을 계산한다. Fat-tree 토폴로지에서 소스-목적지 쌍마다 다중 경로가 존재해 장애 내성과 ECMP 로드 밸런싱을 제공한다.

---

## RoCE — Ethernet 위의 RDMA

**RoCE**(RDMA over Converged Ethernet)는 InfiniBand 전송 계층을 Ethernet 위에서 동작하도록 이식한 표준이다. libibverbs Verbs API는 동일하게 사용한다.

### v1 vs v2

| | RoCE v1 | RoCE v2 |
|:---|:---:|:---:|
| 전송 계층 | L2 (Ethertype 0x8915) | **UDP/IP** (포트 4791) |
| 라우팅 | VLAN 내부만 | **서브넷 간 L3 라우팅 가능** |
| 현황 | deprecated | **현재 표준** |

RoCE v2(RRoCE)는 표준 IP/UDP 헤더를 추가해 기존 IP 인프라와 통합된다.

### Lossless Ethernet: PFC

TCP와 달리 RDMA RC QP는 패킷 손실 시 타임아웃 후에야 재전송한다. 대규모 AllReduce에서 패킷 1개 손실이 수십 ms의 QP stall로 이어지고, 모든 GPU가 그 동기 지점에서 기다린다. 패킷 손실률 0.01%도 학습 처리량을 크게 떨어뜨린다.

RoCE는 **PFC**(Priority Flow Control, IEEE 802.1Qbb)로 패킷 손실을 원천 차단한다.

```
[PFC 동작 원리]
노드 A ──→ 스위치 포트 ──→ 스위치 내부 큐 ──→ 노드 B
                               │
                          버퍼 임박 임계값 도달
                               │
                    PAUSE 프레임 → 업스트림(노드 A) 전송 중지
                               │
                          (혼잡 해소 후 재개)
```

RDMA 트래픽을 TC(Traffic Class) 3으로 분리하면, 혼잡 시 RDMA 트래픽만 일시 정지하고 다른 트래픽에는 영향이 없다.

PFC의 구조적 문제는 **HOL(Head-of-Line) Blocking**이다. 같은 TC 내 비혼잡 플로우까지 함께 정지된다. 드물게는 여러 스위치에서 PAUSE가 순환하며 fabric collapse(PFC Pause Storm)로 이어진다.

### DCQCN — 혼잡 제어

PFC는 최후 수단이다. 실제 혼잡 제어는 **DCQCN**(Data Center Quantized Congestion Notification)이 담당한다 (Zhu et al., SIGCOMM 2015).

```
[스위치 = Congestion Point (CP)]
  큐 깊이 > 임계값
    → IP 헤더 CE 비트 설정 (ECN 마킹)

[수신 NIC = Notification Point (NP)]
  ECN-marked 패킷 수신
    → CNP (Congestion Notification Packet) 생성 → 송신자 전달

[송신 NIC = Reaction Point (RP)]
  CNP 수신 시 (승법적 감소):
    α(t) = (1 - g) × α(t-1) + g          ← EWMA 혼잡 신호
    Rate_new = Rate_cur × (1 - α / 2)     ← 즉각 적용

  CNP 없을 시 (속도 회복):
    Phase 1: 최대 속도의 절반까지 이진 증가  ← Fast Recovery
    Phase 2: 이후 선형 증가                  ← Additive Increase
```

DCQCN은 TCP와 달리 **속도 기반(rate-based)** 제어다. ECN 마킹부터 속도 감소까지 마이크로초 단위로 반응한다.

---

## GPUDirect RDMA

**GPUDirect RDMA**는 GPU HBM과 NIC 사이에서 시스템 DRAM을 경유하지 않는다.

```
[GPUDirect RDMA 없이]
GPU HBM → PCIe → 시스템 DRAM → CPU memcpy → DRAM → NIC → 네트워크

[GPUDirect RDMA]
GPU HBM → PCIe → NIC → 네트워크
```

GPU 메모리의 BAR(Base Address Register)를 PCIe 주소 공간에 직접 매핑해, NIC이 GPU HBM에 DMA로 접근한다. 400Gbps 라인 속도에서 GPUDirect RDMA 없이 진행하면 메모리 복사 overhead가 총 네트워크 레이턴시의 40%에 달한다.

NVIDIA GPU에서는 `nvidia_peermem.ko` 모듈을 로드해야 한다. AMD GPU에서는 `amdkfd` 드라이버에 P2P 지원이 내장돼 있으며, **ROCmRDMA**라고 부른다.

NCCL에서 GPUDirect RDMA 수준은 `NCCL_NET_GDR_LEVEL`로 제어한다:

| 값 | 허용 범위 |
|:---|:---|
| `PIX` | 같은 PCIe switch 내 GPU-NIC 쌍 |
| `PHB` | CPU 소켓 내 GPU-NIC 쌍 |
| `SYS` | NUMA 경계를 넘어서도 허용 |

다른 주요 NCCL IB/RoCE 환경변수:

| 변수 | 설명 |
|:---|:---|
| `NCCL_IB_HCA` | 사용할 HCA 지정 (`=mlx5_0,mlx5_1`) |
| `NCCL_IB_GID_INDEX` | RoCE GID 인덱스 (`ibv_show_gids`로 확인) |
| `NCCL_IB_QPS_PER_CONNECTION` | 연결당 QP 수 (1~128, fat-tree ECMP 엔트로피 향상용) |

---

## InfiniBand vs RoCE v2 vs iWARP

| | InfiniBand (NDR) | RoCE v2 | iWARP | TCP/IP |
|:---|:---:|:---:|:---:|:---:|
| 앱 레이턴시 | **1~2μs** | 5~7μs | >3μs | 50μs+ |
| 스위치 레이턴시 | **130ns** | 230ns | — | 높음 |
| 최대 대역폭 | **400Gbps** | 400Gbps | 낮음 | — |
| Lossless | 하드웨어 내장 | PFC+ECN 구성 필요 | TCP 재전송 | 없음 |
| 인프라 비용 | 높음 | **낮음 (Ethernet 공용)** | 낮음 | 최저 |
| 스위치 비용 | 기준 | **IB 대비 49~70% 절감** | — | — |

**InfiniBand를 선택하는 경우**: μs 단위 꼬리 레이턴시가 직접적 비용인 타이트한 HPC 결합 시뮬레이션, 또는 NVIDIA DGX/Base Command 생태계 구성 시.

**RoCE v2를 선택하는 경우**: 하이퍼스케일 규모(수천 노드), 기존 Ethernet 인프라 활용, AMD Instinct 클러스터(Broadcom Thor2 NIC 기반 등).

---

## 정리

| | InfiniBand | RoCE v2 |
|:---|:---|:---|
| 전송 계층 | 전용 IB fabric | UDP/IP over Ethernet |
| Lossless | 하드웨어 내장 | PFC + DCQCN 구성 필요 |
| 앱 레이턴시 | 1~2μs | 5~7μs |
| 인프라 비용 | 높음 | 낮음 |
| 주요 사용처 | HPC, NVIDIA DGX | 대규모 AI 클러스터, AMD MI |

GPU 클러스터 네트워킹의 핵심은 RDMA로 커널 경로를 제거하고, GPUDirect RDMA로 GPU 메모리를 NIC에 직접 노출하며, Lossless fabric으로 패킷 손실을 차단하는 것이다.

---

## References

- Zhu et al. *Congestion Control for Large-Scale RDMA Deployments* (DCQCN). ACM SIGCOMM 2015. [DOI](https://dl.acm.org/doi/10.1145/2785956.2787484)
- Hu et al. *RDMA over Ethernet for Distributed AI Training at Meta Scale*. ACM SIGCOMM 2024. [PDF](https://cs.stanford.edu/~keithw/sigcomm2024/sigcomm24-final246-acmpaginated.pdf)
- NVIDIA. *NCCL Documentation: Environment Variables*. [Link](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html)
- NVIDIA. *Scaling Deep Learning Training with NCCL*. NVIDIA Developer Blog. [Link](https://developer.nvidia.com/blog/scaling-deep-learning-training-nccl/)
- Red Hat. *Configuring InfiniBand and RDMA Networks* (RHEL 9). [Link](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_infiniband_and_rdma_networks/)
- AMD ROCm. *What is RCCL?*. ROCm Documentation. [Link](https://rocm.docs.amd.com/projects/rccl/en/docs-6.4.0/what-is-rccl.html)
- DatenLord. *The Evolution and Implementation of GPUDirect RDMA*. Medium. [Link](https://medium.com/@datenlord/the-evolution-and-implementation-of-gpudirect-rdma-19751f7b9413)
- Wikipedia. *RDMA over Converged Ethernet*. [Link](https://en.wikipedia.org/wiki/RDMA_over_Converged_Ethernet)
