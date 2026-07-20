---
layout: post
title: "논문 리뷰: Kimi Delta Attention, 선형 어텐션이 전체 어텐션을 넘다"
subtitle: "Kimi Linear - 채널별 게이팅과 하이브리드 구성으로 1M 컨텍스트를 감당하는 방법"
tags: [AI, LLM, Attention, Paper-Review]
lang: kr
translation-url: /2026-07-21-kimi-delta-attention-en/
readtime: true
mathjax: true
---

## 논문 정보

- **제목**: Kimi Linear: An Expressive, Efficient Attention Architecture
- **저자**: Kimi Team (Moonshot AI)
- **arXiv**: [2510.26692](https://arxiv.org/abs/2510.26692) (2025년 10월)
- **코드**: [MoonshotAI/Kimi-Linear](https://github.com/MoonshotAI/Kimi-Linear) · [모델(48B/3B)](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct)

이 글은 [Kimi K3 분석](/2026-07-21-kimi-k3-kr/)에서 언급한 세 자체 기법 중 하나인 **Kimi Delta Attention(KDA)** 의 원 논문을 다룬다.

---

## 배경: 전체 어텐션과 선형 어텐션의 상충

트랜스포머의 표준 어텐션(full attention)은 표현력이 높지만 시퀀스 길이에 이차로 비싸다. 1M 토큰 컨텍스트에서는 KV 캐시와 연산이 감당하기 어렵다.

**선형 어텐션(linear attention)** 은 이를 선형 비용으로 낮춘다. 어텐션 상태를 고정 크기의 순환 상태(RNN 유사)로 압축해, 토큰마다 KV를 무한히 쌓지 않는다. 문제는 표현력이다. 고정 크기 상태에 정보를 욱여넣으므로 긴 의존성에서 전체 어텐션에 뒤지는 것이 통념이었다.

이 논문의 질문은 명확하다. 선형 어텐션이 공정한 비교에서 전체 어텐션을 실제로 넘을 수 있는가.

---

## Kimi Delta Attention

KDA는 **Gated DeltaNet**을 확장한다. DeltaNet은 delta 규칙으로 순환 상태를 갱신하는 선형 어텐션 계열이다. Gated DeltaNet은 여기에 감쇠(decay) 게이트를 더한다. 이전 상태를 얼마나 잊을지를 조절하는 것이다.

핵심 차이는 **게이팅의 세밀도**다.

```
Gated DeltaNet:  이전 상태 × (스칼라 decay)
                 → 모든 은닉 차원이 같은 속도로 망각

KDA:             이전 상태 × (채널별 벡터 decay, 대각 행렬)
                 → 차원마다 다른 망각 속도
```

표준 Gated DeltaNet은 순환 상태에 단일 스칼라 감쇠를 곱한다. 모든 은닉 차원이 같은 속도로 잊는다는 뜻이다. KDA는 이 스칼라를 **채널별 벡터**로 바꿔 대각 행렬로 만든다. 차원마다 다른 망각 속도를 가진다. 이 세밀한 게이팅이 유한한 순환 상태 메모리를 더 효과적으로 쓰게 한다.

수학적으로는 **DPLR(Diagonal-Plus-Low-Rank)** 전이 행렬을 쓴다. 일반적인 DPLR 형식보다 연산을 줄이면서 고전적 delta 규칙에 더 부합하는 특화 변형이다. 하드웨어 효율을 위해 청크 단위(chunkwise) 알고리즘으로 구현하고, `FlashKDA` 커널과 vLLM 구현을 공개했다.

---

## 하이브리드 구성

KDA만으로 전체 어텐션을 완전히 대체하지는 않는다. 논문은 KDA와 **MLA(Multi-head Latent Attention)** 를 계층 단위로 섞는다.

![Kimi Linear 하이브리드 어텐션](/assets/img/posts/kimi-delta-attention/kda-hybrid.png)

구성 비율은 **KDA 3 : MLA 1**이다. 선형 계층 3개가 지역 시퀀스 구조를 싸게 처리하고, 전체 어텐션 계층 1개가 전역 정보 흐름을 보존한다. 대부분의 계층이 KV 캐시를 쌓지 않으므로 메모리가 크게 준다.

이 배치는 두 방식의 장점을 취한다. 선형 어텐션의 저비용과 전체 어텐션의 전역 표현력이다. 순수 선형도 순수 전체도 아닌 절충이다.

---

## 결과

논문은 3B 활성 / 48B 전체 파라미터의 Kimi Linear 모델을 사전학습해 검증했다(1.4T 토큰).

- **KV 캐시**: 전체 MLA 대비 최대 75% 절감
- **디코딩 처리량**: 1M 컨텍스트에서 최대 6배
- **품질**: 동일 학습 레시피에서 전체 MLA를 모든 평가 과제에서 상당한 격차로 상회

주목할 점은 마지막이다. 선형 어텐션이 짧은 컨텍스트, 긴 컨텍스트, RL 스케일링까지 다양한 환경에서 공정한 비교로 전체 어텐션을 넘은 첫 사례라는 것이 논문의 주장이다. 선형 어텐션이 효율만이 아니라 품질에서도 앞선다는 결과다.

---

## 한계

논문 초록은 구체적 실패 모드를 나열하지 않는다. 다만 구조상 유의할 점은 있다. 하이브리드 비율(3:1)과 DPLR 형식은 설계 선택이며, 다른 모델 규모나 과제에서 최적 비율이 달라질 수 있다. 순수 선형이 아니라 전체 어텐션 계층을 여전히 포함하므로, 전역 정보가 필요한 과제에서는 그 계층에 의존한다.

---

## Kimi K3와의 연결

KDA는 [Kimi K3](/2026-07-21-kimi-k3-kr/)의 핵심 어텐션 메커니즘이다. K3는 이 Kimi Linear의 KDA를 2.8T 규모로 확장 적용해 1M 컨텍스트를 감당한다. K3 분석에서 언급한 "디코딩 6.3배, KV 75% 절감" 주장의 근거가 이 논문이다. Moonshot이 KDA 구현을 vLLM에 기여한 것도 여기서 출발한다.

---

## 레퍼런스

- Kimi Team. "Kimi Linear: An Expressive, Efficient Attention Architecture." arXiv:2510.26692, 2025. [arXiv](https://arxiv.org/abs/2510.26692)
- 코드/모델: [GitHub](https://github.com/MoonshotAI/Kimi-Linear) · [HuggingFace](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct)
- 관련 글: [Kimi K3 분석](/2026-07-21-kimi-k3-kr/)

수치는 논문 보고값이다. 다이어그램은 논문 개념을 바탕으로 직접 제작했다.
