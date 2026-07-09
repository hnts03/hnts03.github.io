---
layout: post
title: "Vera CPU / Rubin GPU: GTC 2025 공개 내용 정리"
subtitle: "공식 발표 한도 내에서 정리한 NVIDIA 차세대 AI 플랫폼"
tags: [CPU, Architecture, ARM, NVIDIA, Rubin, Vera, HPC, NVLink, Computer-Architecture]
lang: kr
translation-url: /2026-07-09-cpu-arch-2-rubin-vera-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 1 | Grace - NVIDIA의 첫 데이터센터 CPU | ✅ |
| 2 | Vera / Rubin - GTC 2025 공개 내용 | ✅ |
| 3 | (미정) | 🔲 |

---

이 글은 2025년 3월 GTC에서 공개된 내용만을 다룬다. 미공개 항목은 명시적으로 표기한다.

---

## Grace-Hopper가 증명한 것

Grace CPU와 Hopper GPU를 NVLink-C2C로 연결한 GH200은 CPU-GPU 통합의 새 기준을 제시했다. 핵심은 두 가지였다.

1. PCIe 병목 제거: NVLink-C2C 900 GB/s로 PCIe 5.0 x16(~64 GB/s)의 약 14배 대역폭 확보
2. 하드웨어 캐시 일관성: `cudaMemcpy` 없이 CPU-GPU 간 포인터 직접 공유

Rubin/Vera는 이 전략의 다음 세대다.

---

## GTC 2025 발표 개요

2025년 3월 GTC에서 Jensen Huang이 공개한 내용:

- **Rubin**: 차세대 GPU 아키텍처
- **Vera**: Rubin과 쌍을 이루는 차세대 CPU
- 통합 플랫폼명: **Vera-Rubin**
- 출시 예정: 2026년 (Rubin / Vera), 2027년 (Rubin Ultra)
- 이후 세대: **Feynman** (이름만 공개)

NVIDIA의 세대별 로드맵:

```
         2022-23      2024-25      2026       2027      2028+
GPU:  [─ Hopper ─][─ Blackwell ─][─ Rubin ─][R.Ultra][─ Feynman ─]
CPU:  [──────────── Grace ────────][─── Vera ────────][     ?     ]
SYS:  [───────── GH200 / NVL72 ───][── Vera-Rubin ───][     ?     ]

      ■ 출시    ░ 발표    · 이름만 공개
```

---

## Rubin GPU: 공개된 사항

| 항목 | 내용 |
|:---|:---|
| Tensor Core | **6세대** |
| GPU 메모리 | **HBM4** |
| GPU-GPU 인터커넥트 | **NVLink 6.0** |
| 출시 예정 | 2026년 |

### HBM4

HBM4는 Rubin GPU에서 사용이 확정됐다. JEDEC HBM4 표준과 SK Hynix, Samsung, Micron의 공개 발표에 따르면 HBM3e 대비 높은 대역폭과 용량을 목표로 한다. Rubin에서의 구체적인 스택 수, 총 용량, 총 대역폭 수치는 미공개다.

### NVLink 6.0

Rubin GPU 간 인터커넥트로 NVLink 6.0이 사용된다. 세대별 대역폭 진화:

| 세대 | GPU | 대역폭 (GPU당) |
|:---|:---:|:---:|
| NVLink 4.0 | Hopper H100 | 900 GB/s |
| NVLink 5.0 | Blackwell B200 | 1,800 GB/s |
| NVLink 6.0 | Rubin | **미공개** |

### 6세대 Tensor Core

6세대 Tensor Core가 탑재된다는 것만 확인됐다. 지원 정밀도, 처리량, 설계 변경 사항은 미공개다.

### 미공개 항목 (Rubin GPU)

SM 수, 다이 구성(단일/MCM), 공정 노드, HBM4 총 용량, NVLink 6.0 대역폭, Tensor Core 지원 정밀도 및 처리량.

---

## Vera CPU: 공개된 사항

Vera에 대해 GTC 2025에서 공개된 내용은 다음이 전부다.

| 항목 | 내용 |
|:---|:---|
| 역할 | Grace 후속 데이터센터 CPU |
| 쌍을 이루는 GPU | Rubin |
| 플랫폼 | Vera-Rubin |
| 출시 예정 | 2026년 |

### CPU-GPU 연결 방식

Grace-Hopper에서 NVLink-C2C로 CPU-GPU를 연결한 선례가 있다. Vera-Rubin에서도 동일한 방식이 사용될 것으로 예상되나, NVIDIA가 Vera에 대해 공식적으로 명시하지는 않았다.

### 미공개 항목 (Vera CPU)

코어 수, 마이크로아키텍처(ARM Neoverse 후속 여부 포함), 메모리 규격 및 대역폭, 캐시 구성, 공정 노드, NVLink-C2C 대역폭.

---

## Rubin Ultra (2027년 예정)

Rubin의 고성능 변형이다. 이름과 출시 예정 연도 외에 공개된 사항이 없다.

---

## Feynman

Richard Feynman의 이름을 딴 Rubin 이후 세대다. 이름과 로드맵 위치(2027-2028년)만 공개됐으며 기술 내용은 없다.

---

## 현재 시점 비교

Grace-Hopper와 Vera-Rubin의 공개된 정보를 나란히 정리하면:

| 항목 | Grace-Hopper (GH200) | Vera-Rubin |
|:---|:---:|:---:|
| GPU 아키텍처 | Hopper | Rubin |
| CPU 아키텍처 | Grace (Neoverse V2) | Vera (미공개) |
| GPU 메모리 | HBM3 / HBM3e | HBM4 |
| GPU-GPU 연결 | NVLink 4.0 (900 GB/s) | NVLink 6.0 (대역폭 미공개) |
| CPU-GPU 연결 | NVLink-C2C (900 GB/s) | 미공개 (NVLink-C2C 예상) |
| GPU TC 세대 | 4세대 (FP8) | 6세대 (세부 미공개) |
| 출시 | 2022-2023 | 2026 (예정) |

공개된 정보의 비대칭이 뚜렷하다. GPU 측은 세대, 메모리 규격, 인터커넥트 이름이 확인됐고, CPU 측(Vera)은 이름과 역할 정도만 공개됐다.

추가 공개는 2025년 하반기 SC(Supercomputing) 컨퍼런스나 2026년 GTC에서 이루어질 것으로 예상된다.

다음 글: (미정)
