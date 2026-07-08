---
layout: post
title: "CXL이란 무엇인가 - Compute Express Link 개요"
subtitle: "PCIe 위의 캐시 일관성 인터커넥트, 메모리 확장, AI/HPC 활용"
tags: [CXL, Computer-Architecture, Memory, Interconnect, HPC]
lang: kr
translation-url: /2026-07-08-cxl-overview-en/
readtime: true
mathjax: false
---

## 문제: 메모리 벽

서버의 CPU 소켓당 DIMM 슬롯 수는 제한적이다. 고성능 서버도 보통 16~24개 DIMM 슬롯에 최대 수 TB DRAM을 탑재한다. AI 추론에서 100B 이상 파라미터 모델의 KV Cache는 수백 GB를 요구한다. LLM 서빙 서버 한 대에서 처리할 수 있는 동시 요청 수는 결국 DRAM 용량 한계에 부딪힌다.

동시에, GPU처럼 대용량 HBM을 탑재한 가속기와 CPU 사이의 데이터 이동은 여전히 비일관적(non-coherent) PCIe를 통한 DMA로 이뤄진다. 가속기가 CPU 메모리를 읽으려면 명시적 복사가 필요하고, 일관성 유지는 소프트웨어가 책임진다.

**CXL(Compute Express Link)**은 이 두 문제를 동시에 다루는 오픈 인터커넥트 표준이다.

---

## CXL이란

CXL은 PCIe 물리 계층 위에서 동작하는 고속 인터커넥트 프로토콜이다. 2019년 Intel 주도로 규격이 공개됐으며, AMD, ARM, NVIDIA, Samsung, Micron, Alibaba 등이 CXL 컨소시엄에 참여하고 있다.

CXL의 핵심 목표:
- **메모리 용량 확장**: CPU가 DIMM 슬롯 한계를 넘어 CXL 장치에 부착된 메모리를 직접 접근
- **캐시 일관성**: 가속기가 CPU 메모리 계층에 참여해 명시적 복사 없이 데이터 공유
- **메모리 풀링**: 여러 서버가 CXL 패브릭을 통해 메모리 자원을 동적으로 공유

물리 계층은 PCIe와 동일하다. PCIe 5.0(CXL 1.x/2.0) 또는 PCIe 6.0(CXL 3.0) 핀을 그대로 사용한다. CXL은 PCIe의 물리/링크 계층 위에 새로운 프로토콜 계층을 얹은 형태다.

---

## 세 가지 서브 프로토콜

CXL은 세 개의 독립적인 서브 프로토콜로 구성된다. 디바이스는 지원하는 프로토콜 조합에 따라 타입이 결정된다.

```
CXL 프로토콜 스택

┌──────────────────────────────────────────────┐
│  CXL.io      │  CXL.cache   │  CXL.mem       │  ← CXL 트랜잭션 계층
├──────────────────────────────────────────────┤
│           CXL Flex Bus (ARB/MUX)             │  ← 프로토콜 다중화
├──────────────────────────────────────────────┤
│           PCIe 5.0 / 6.0 물리 계층           │  ← 공유 물리 레이어
└──────────────────────────────────────────────┘
```

### CXL.io

PCIe와 완전히 호환되는 I/O 프로토콜이다. 디바이스 발견(enumeration), BAR 맵핑, 구성 공간 접근에 사용한다. 기존 PCIe 드라이버가 CXL 장치를 인식하는 기반이 된다.

### CXL.cache

**디바이스가 CPU 메모리를 캐시 일관성 있게 접근하는 프로토콜이다.**

기존 PCIe DMA는 비일관적이다. GPU가 CPU 메모리를 읽으려면 드라이버가 DMA를 설정하고, CPU 캐시 플러시를 관리해야 한다. CXL.cache는 이 과정을 하드웨어가 처리한다.

```
기존 PCIe (비일관):
CPU DRAM → DMA 복사 → GPU 버퍼 → GPU 연산
  ↑ 소프트웨어가 캐시 일관성 직접 관리

CXL.cache (일관):
CPU DRAM ← CXL.cache → 가속기
  ↑ 하드웨어가 캐시 일관성 자동 유지
  가속기가 CPU 캐시 라인 단위로 직접 읽기/쓰기 가능
```

가속기 입장에서 CPU 메모리의 특정 영역을 자신의 로컬 캐시에 보유할 수 있다. CPU가 같은 데이터를 수정하면 CXL.cache 프로토콜이 MESI 스타일 일관성 메시지로 가속기 캐시를 무효화한다.

### CXL.mem

**CPU 호스트가 디바이스에 부착된 메모리를 직접 접근하는 프로토콜이다.**

CPU가 CXL 장치 위의 DRAM을 자신의 주소 공간으로 맵핑한다. `malloc()` 등 일반 메모리 API로 이 메모리를 사용할 수 있다. OS에는 별도의 NUMA 노드로 노출된다.

```
CPU 주소 공간에서 본 CXL 메모리

[로컬 DRAM 영역]  0x0000_0000 ~ 0x3FFF_FFFF   → DDR5 DIMM
[CXL.mem 영역]    0x4000_0000 ~ 0x7FFF_FFFF   → CXL Type 3 장치 DRAM
                  (NUMA node 1 로 노출)
```

---

## 디바이스 타입

| 타입 | 지원 프로토콜 | 용도 | 예시 |
|:---|:---|:---|:---|
| Type 1 | CXL.io + CXL.cache | 자체 메모리 없음. 가속기가 CPU 메모리 캐시 | SmartNIC, FPGA |
| Type 2 | CXL.io + CXL.cache + CXL.mem | 자체 메모리 보유 + 양방향 일관성 | GPU, AI 가속기 |
| Type 3 | CXL.io + CXL.mem | CPU 메모리 확장 전용 | CXL DRAM 모듈 |

**Type 3**가 현재 가장 활발하게 출시되는 형태다. Samsung, Micron, SK Hynix 등이 CXL DRAM 모듈을 양산 중이다. 서버의 DIMM 슬롯을 다 사용한 상태에서 CXL 슬롯을 통해 DRAM 용량을 수 TB까지 확장한다.

**Type 2**는 이론적으로 GPU와 CPU가 동일 캐시 일관성 도메인에 참여하는 형태다. 현 세대 GPU는 PCIe 기반으로 연결되며 완전한 CXL Type 2로 동작하지 않는다.

---

## CXL 버전 진화

### CXL 1.0 / 1.1 (2019/2020)

PCIe 5.0 물리 계층 기반. 단일 호스트 CPU와 단일 CXL 장치를 1:1로 연결한다. 세 프로토콜 모두 정의됐다.

지원 CPU 예시:
- Intel Xeon Sapphire Rapids (4세대, 2023): CXL 1.1
- AMD EPYC Genoa (9004 시리즈, 2022): CXL 1.1

### CXL 2.0 (2020)

**CXL 스위치**와 **메모리 풀링**이 추가됐다. 단일 스위치가 여러 호스트와 여러 CXL 장치를 중간에서 연결한다.

```
CXL 2.0 풀링 구성

  Host A ─┐                    ┌─ CXL DRAM 0 (256GB)
  Host B ─┤── CXL Switch ──────┤─ CXL DRAM 1 (256GB)
  Host C ─┘                    └─ CXL DRAM 2 (256GB)

Host A가 256GB, Host B가 512GB 할당받는 등 동적 배분 가능
```

이 구성에서 메모리를 많이 필요로 하는 워크로드(추론 서버)와 컴퓨트 집약적 워크로드(학습 서버)가 동일 CXL 메모리 풀을 공유한다.

### CXL 3.0 (2022)

다중 레벨 패브릭과 P2P(Peer-to-Peer) 통신이 추가됐다. CXL 스위치를 계층적으로 연결해 최대 수천 노드 규모의 메모리 패브릭을 구성할 수 있다. PCIe 6.0 물리 계층으로 대역폭을 2배 향상시켰다.

---

## 지연 특성

CXL 메모리는 로컬 DRAM보다 접근 지연이 높다. CXL 프로토콜 처리와 링크 횡단 시간이 더해지기 때문이다.

![메모리 계층별 접근 지연 (로컬 DRAM 대비)](/assets/img/posts/cxl-overview/latency-compare.png)

| 메모리 계층 | 절대 지연 (대략) | 로컬 DRAM 대비 |
|:---|:---:|:---:|
| 로컬 DRAM (DDR5) | ~75ns | 1× |
| CXL 1.x 직결 | ~150ns | ~2× |
| CXL 2.0 스위치 경유 | ~250ns | ~3× |
| CXL 3.0 원격 노드 | ~400ns | ~5× |

2× 지연 증가는 용량 대비 트레이드오프로 수용 가능한 경우가 많다. LLM KV Cache처럼 접근 패턴이 대역폭 집약적(bandwidth-bound)이고 지연에 덜 민감한 워크로드에 적합하다.

OS는 CXL 메모리를 별도 **NUMA 노드**로 인식한다. `numactl --membind=1` 또는 `mmap(MAP_POPULATE)` 등으로 특정 할당을 CXL 노드로 명시적으로 지정할 수 있다. 리눅스 커널 6.x부터 CXL 디바이스 인식과 NUMA 노드 등록을 기본 지원한다.

---

## AI / LLM 활용

### KV Cache 오프로딩

LLM 서빙에서 KV Cache는 배치 크기와 시퀀스 길이에 비례해 성장한다. 모델 가중치는 고정 크기지만 KV Cache는 동적으로 확장된다.

```
LLM 서빙 메모리 사용 예시 (70B 모델, FP16)

GPU HBM (80GB):
  모델 가중치: ~35GB
  KV Cache: ~20GB  ← 처리 가능 요청 수가 여기서 막힘
  기타: ~5GB

CXL 메모리 확장 (256GB):
  오버플로우 KV Cache: ~200GB  ← 동시 처리 요청 수 대폭 증가
  (지연 허용 가능한 히스토리 토큰에 적용)
```

GPU HBM의 KV Cache 중 최근 토큰만 GPU에 유지하고 이전 히스토리를 CXL 메모리로 오프로드하면, 같은 GPU에서 더 많은 배치를 처리할 수 있다. 지연 증가는 있지만 throughput 향상이 가능하다.

### 메모리 풀링과 서버 컨버전스

CXL 2.0 이상에서 여러 서버가 하나의 CXL 메모리 풀을 공유하면, 개별 서버의 메모리 사용이 낮을 때 유휴 용량을 다른 서버가 활용할 수 있다. 메모리 자원의 평균 이용률이 높아진다.

---

## CXL vs NVLink vs PCIe

| 항목 | PCIe | CXL | NVLink |
|:---|:---:|:---:|:---:|
| 물리 계층 | PCIe | PCIe (공유) | 독자 규격 |
| 표준 | 오픈 | 오픈 | 독점 (NVIDIA) |
| 캐시 일관성 | 없음 | **있음** | 있음 (NVLink-C2C) |
| 대역폭 (최신) | PCIe 5.0: ~64 GB/s | PCIe 6.0: ~128 GB/s | NVLink 5.0: 1,800 GB/s |
| 연결 대상 | 범용 | CPU-디바이스 | GPU-GPU, GPU-CPU |
| 주 활용처 | 범용 I/O | 메모리 확장/일관성 | GPU 클러스터 통신 |

NVLink는 대역폭에서 압도적이지만 NVIDIA 생태계에 한정된다. CXL은 대역폭이 낮지만 CPU-중심 메모리 계층 통합에 강점이 있고 벤더 중립적이다.

---

## 에코시스템 현황

| 구성 요소 | 현황 |
|:---|:---|
| CPU 지원 | Intel Xeon Sapphire Rapids/Granite Rapids (CXL 1.1/2.0), AMD EPYC Genoa/Turin (CXL 1.1/2.0) |
| CXL DRAM 모듈 | Samsung CMM-D, Micron CZ120, SK Hynix AiMX (Type 3) |
| CXL 스위치 | Microchip PFX, Astera Labs Leo (CXL 2.0 스위치) |
| OS 지원 | Linux 6.0+ (CXL 서브시스템), NUMA 노드 자동 등록 |
| 프레임워크 | PyTorch/vLLM에서 NUMA-aware 메모리 할당으로 CXL 노드 활용 가능 |

---

## 정리

| 항목 | 내용 |
|:---|:---|
| 물리 계층 | PCIe 5.0 (CXL 1.x/2.0), PCIe 6.0 (CXL 3.0) |
| 핵심 프로토콜 | CXL.io (I/O), CXL.cache (일관 캐시), CXL.mem (메모리 확장) |
| 디바이스 타입 | Type 1 (캐시만), Type 2 (캐시+메모리), Type 3 (메모리 확장) |
| CXL 1.x | 1:1 연결 |
| CXL 2.0 | 스위치, 메모리 풀링 |
| CXL 3.0 | 멀티 레벨 패브릭, P2P |
| 지연 오버헤드 | 로컬 DRAM 대비 ~2× (직결) ~ 5× (원격) |
| AI 활용 | KV Cache 오프로딩, 메모리 풀 공유 |

CXL은 PCIe 인프라 위에서 CPU 중심 메모리 계층을 수 TB 규모로 확장하고, 가속기와의 캐시 일관성을 하드웨어 수준에서 해결하는 표준이다. 현재 LLM 추론 인프라에서 메모리 병목이 심화되는 상황에서 채택이 가속화되고 있다.

---

## 참고 자료

- CXL Consortium. *CXL Specification 3.0*. computeexpresslink.org, 2022.
- Intel. *Compute Express Link (CXL) Technology Overview*. Intel Developer Zone, 2023.
- JEDEC. *DDR5 and CXL Memory Technology*. 2023.
- Linux Kernel. *CXL Subsystem Documentation*. kernel.org/doc/html/latest/driver-api/cxl.
- MemVerge. *CXL Memory Tiering in AI Workloads*. 2023.
