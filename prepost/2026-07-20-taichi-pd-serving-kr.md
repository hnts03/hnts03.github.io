---
layout: post
title: "논문 리뷰: TaiChi, Prefill-Decode 통합으로 Goodput을 최적화하다"
subtitle: "Aggregation이냐 Disaggregation이냐 - 둘을 합쳐 균형 SLO에서 이기는 LLM 서빙 시스템"
tags: [AI, LLM, Serving, GPU, Paper-Review]
lang: kr
translation-url: /2026-07-20-taichi-pd-serving-en/
readtime: true
mathjax: false
---

## 논문 정보

- **제목**: Prefill-Decode Aggregation or Disaggregation? Unifying Both for Goodput-Optimized LLM Serving
- **저자**: Chao Wang, Pengfei Zuo, Zhangyu Chen, Yunkai Liang, Zhou Yu, Ming-Chang Yang (홍콩중문대, Huawei Cloud, 중산대)
- **arXiv**: [2508.01989v1](https://arxiv.org/abs/2508.01989)

LLM 서빙에서 오래 이어진 논쟁이 있다. 프리필과 디코드를 같은 GPU에서 처리할 것인가(aggregation), 분리할 것인가(disaggregation). TaiChi는 이 논쟁에 "둘 다"라고 답한다. 배경부터 짚는다.

---

## 배경: 두 국면, 두 지표

LLM 추론은 성격이 다른 두 국면으로 나뉜다. 이 구분은 [LLM 서빙 개요](/2026-06-19-llm-serving-overview-kr/)에서 다룬 내용이지만 핵심만 다시 정리한다.

- **프리필(Prefill)**: 입력 프롬프트 전체를 한 번에 처리해 첫 토큰을 만든다. 연산 집약적(compute-bound)이다.
- **디코드(Decode)**: 토큰을 하나씩 자기회귀적으로 생성한다. 메모리 대역폭 집약적(memory-bound)이다.

두 국면은 서로 다른 지연 지표로 평가된다.

- **TTFT(Time To First Token)**: 첫 토큰까지의 시간. 프리필이 결정한다.
- **TPOT(Time Per Output Token)**: 토큰 하나당 생성 시간. 디코드가 결정한다.

서빙 시스템의 목표는 처리량이 아니라 **goodput**이다. Goodput은 TTFT와 TPOT의 SLO(서비스 수준 목표)를 **둘 다** 만족하는 요청의 처리율이다. 아무리 많은 요청을 처리해도 지연 목표를 어기면 goodput에 포함되지 않는다.

---

## 문제: Aggregation과 Disaggregation, 둘 다 반쪽

프리필과 디코드를 배치하는 두 가지 방식이 있고, 각각 한쪽 지표만 잘한다.

![세 가지 LLM 서빙 방식](/assets/img/posts/taichi-pd-serving/serving-modes.png)

**PD Aggregation (통합)**

프리필과 디코드를 같은 인스턴스에서 처리한다. vLLM의 연속 배칭에 chunked prefill을 결합한 방식이 대표적이다. GPU 활용률이 높고 프리필이 빨라 **TTFT는 좋다**. 그러나 같은 GPU에서 프리필과 디코드가 서로 간섭한다. 무거운 프리필이 끼어들면 진행 중인 디코드가 밀려 **TPOT가 나빠진다**.

**PD Disaggregation (분리)**

프리필 전용 인스턴스와 디코드 전용 인스턴스를 나눈다. DistServe, Splitwise 계열이다. 프리필이 디코드를 간섭하지 않으므로 **TPOT는 좋다**. 프리필이 끝나면 KV 캐시를 디코드 인스턴스로 전송한다. 문제는 프리필 인스턴스 수가 제한되어 프리필 처리 용량이 부족하다는 것이다. 부하가 오르면 프리필 대기가 길어져 **TTFT가 나빠진다**.

**핵심 관찰**: 한쪽 SLO만 빡빡할 때는 한 방식이 이긴다. TTFT가 빡빡하고 TPOT가 느슨하면 aggregation, 반대면 disaggregation이다. 그런데 실제 배포에서 흔한 **균형 잡힌 SLO**(TTFT와 TPOT가 모두 적당히 빡빡)에서는 둘 다 실패한다.

논문의 Table 2는 이를 수치로 보인다. TTFT 6초, TPOT 100ms의 균형 SLO에서 SLO 달성률은 aggregation 16%, disaggregation 50%에 그친다. 어느 쪽도 균형 조건을 감당하지 못한다.

---

## 핵심 아이디어: 통합과 Latency Shifting

TaiChi는 두 방식을 하나의 시스템으로 통합한다. 핵심 개념은 **latency shifting**이다. SLO를 이미 여유 있게 만족하는 요청에서 GPU 자원을 회수해, SLO 위반 위험이 있는 요청으로 재배치한다. 지연 여유를 요청 사이에서 옮기는 것이다.

이를 위한 세 가지 축이 있다.

1. **하이브리드 모드**: 배치는 통합 방식으로 묶어 활용률을 높이되, 요청은 분리 방식으로 세밀하게 제어한다.
2. **차등 능력 인스턴스**: 성격이 다른 두 종류의 인스턴스를 둔다.
3. **두 가지 스케줄링**: flowing decode scheduling과 length-aware prefill scheduling.

---

## 구조: 차등 능력 인스턴스와 세 개의 슬라이더

TaiChi는 인스턴스를 두 종류로 나눈다. 차이는 프리필 **청크 크기(chunk size)** 다. 청크 크기는 프리필을 얼마나 잘게 쪼개 디코드 사이에 끼워 넣을지를 정한다.

- **P-heavy 인스턴스**: 큰 청크(예: 1024). 프리필 처리량과 TTFT를 높인다. 대신 디코드와의 간섭이 크다.
- **D-heavy 인스턴스**: 작은 청크(예: 128~512). 프리필-디코드 간섭을 줄여 TPOT를 낮춘다. 대신 프리필이 느리다.

이 구성은 세 개의 조절 가능한 슬라이더로 표현된다.

| 슬라이더 | 의미 |
|:---:|:---|
| `R_PD` | P-heavy와 D-heavy 인스턴스의 비율 |
| `S_P` | P-heavy의 프리필 청크 크기 |
| `S_D` | D-heavy의 프리필 청크 크기 |

이 슬라이더를 조절하면 시스템을 순수 aggregation에 가깝게도, 순수 disaggregation에 가깝게도, 그 사이 어디로도 놓을 수 있다. 논문은 슬라이더 최적값을 오프라인 탐색으로 찾고, 워크로드가 크게 바뀔 때만 재설정한다.

---

## 스케줄링 1: Flowing Decode (TPOT 제어)

디코드 요청을 인스턴스 사이에서 흐르게 해 TPOT를 요청 단위로 관리한다. 세 단계로 동작한다.

```
1. 저간섭 초기화
   모든 디코드는 D-heavy에서 시작
   → 출력이 짧은 요청이 조기에 TPOT를 위반하지 않도록

2. 최장 우선 강등 (longest-first degradation)
   D-heavy 메모리가 임계에 도달하면,
   출력이 가장 긴 요청을 P-heavy로 이주
   → 이미 오래 혜택 본 요청은 약간의 저하를 견딜 수 있음

3. TPOT 인지 역류 (TPOT-aware backflow)
   TPOT SLO에 근접한 요청은 다시 D-heavy로 이주
   → 품질을 지킴
```

핵심은 지연 여유의 재분배다. 출력이 긴 요청은 이미 여러 토큰을 낮은 지연으로 생성했으므로 여유가 있다. 그 여유를 위험한 요청에 양보한다.

---

## 스케줄링 2: Length-Aware Prefill (TTFT 제어)

프리필 요청을 길이에 따라 라우팅해 TTFT를 관리한다.

- 각 인스턴스에서 TTFT 달성 가능성을 추정한다(대기 시간 + 실행 시간 + 전송 시간).
- 대기 중인 프리필 토큰이 가장 적은 인스턴스를 고른다.
- **짧은 요청은 가능하면 느린 D-heavy에 우선 배정**하고, 빠른 P-heavy는 길고 시간에 민감한 요청을 위해 남겨 둔다.

짧은 요청은 느린 인스턴스에서도 TTFT를 지킬 수 있다. 빠른 자원을 꼭 필요한 요청에 아껴 쓰는 전략이다. 이 역시 latency shifting의 한 형태다.

---

## 결과

논문이 보고한 수치다. Qwen2.5-14B와 32B 모델, 챗봇(ShareGPT)과 요약(ArXiv) 워크로드, A100 8장 단일 노드 환경이다.

**Goodput 개선**

| 비교 대상 | 챗봇 | 요약 |
|:---|:---:|:---:|
| vs PD Aggregation | 9~25% | 20~47% |
| vs PD Disaggregation | 29~49% | 30~77% |

요약 워크로드에서 disaggregation 대비 최대 77% goodput 향상을 보고한다.

**최대 goodput 지점에서의 지연 감소**

- TTFT: disaggregation 대비 2.42~13.20배 감소
- TPOT: aggregation 대비 1.11~1.69배 감소

**각 기법의 기여 (ablation)**

![SLO 달성률에 대한 각 기법의 기여](/assets/img/posts/taichi-pd-serving/ablation.png)

기준(CP256, 청크 256 고정)에서 SLO 달성률은 66.6%다. Flowing decode를 더하면 79.5%(+12.9%), 여기에 length-aware prefill을 더하면 91.2%(+11.7%)에 이른다. 두 스케줄링이 각각 비슷한 크기로 기여한다.

**오버헤드**

TaiChi가 추가한 비용은 작다. KV 캐시 전송이 전체 요청 시간의 0.20%, 프리필 스케줄링 0.01%, 디코드 스케줄링 0.89%다.

---

## 한계

논문이 밝힌 한계는 다음과 같다.

- **단일 노드 평가**: A100 8장 단일 노드에서만 검증했다. 다중 노드 성능은 확인되지 않았다.
- **오프라인 설정 탐색**: 슬라이더 최적값을 오프라인으로 찾아야 하고, 워크로드가 크게 바뀔 때만 재설정한다. 실시간 적응은 아니다.
- **반응형 스케줄링**: 출력 길이를 미리 알 수 없어, 예측이 아니라 사후 반응으로 요청을 이주시킨다.
- **예측 정확도 의존**: 실행 시간 예측(수십 마이크로초 단위)에 스케줄링 정확도가 달려 있다.

---

## 정리와 관점

TaiChi의 기여는 "aggregation이냐 disaggregation이냐"라는 이분법 자체를 재구성한 데 있다. 두 방식은 서로 다른 SLO 조건에 최적일 뿐, 어느 하나가 절대적으로 우월하지 않다. 실제 배포에서 흔한 균형 SLO에서는 둘을 섞고, 요청 사이에서 지연 여유를 옮기는 것이 답이라는 것을 보였다.

인상적인 부분은 latency shifting이라는 통일된 관점이다. flowing decode와 length-aware prefill은 겉으로 다른 기법처럼 보이지만, 둘 다 "여유 있는 요청에서 위험한 요청으로 자원을 옮긴다"는 하나의 원리를 디코드와 프리필에 각각 적용한 것이다. 시스템을 슬라이더 세 개로 파라미터화해 aggregation과 disaggregation을 양 극단으로 포함하는 설계도 깔끔하다.

한계도 분명하다. 단일 노드 검증과 오프라인 슬라이더 탐색은 대규모 클러스터의 동적 워크로드에 그대로 적용하기 어렵다. 다중 노드로의 확장과 온라인 적응이 후속 과제로 남는다. 그럼에도 PD 논쟁을 통합의 문제로 바꾼 관점은 이후 서빙 시스템 설계에 참고할 가치가 있다.

---

## 레퍼런스

- Chao Wang, Pengfei Zuo, Zhangyu Chen, Yunkai Liang, Zhou Yu, Ming-Chang Yang. "Prefill-Decode Aggregation or Disaggregation? Unifying Both for Goodput-Optimized LLM Serving." arXiv:2508.01989v1, 2025. [arXiv](https://arxiv.org/abs/2508.01989) | [HTML](https://arxiv.org/html/2508.01989v1)

이 글의 수치와 개념은 위 논문에서 인용했다. 다이어그램은 논문 원본이 아니라 개념을 바탕으로 직접 제작했다.
