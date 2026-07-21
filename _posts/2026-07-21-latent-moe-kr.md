---
layout: post
title: "논문 리뷰: LatentMoE, FLOP·파라미터당 정확도를 끌어올리는 MoE"
subtitle: "잠재공간에서 라우팅하는 MoE - 그리고 Kimi K3의 Stable LatentMoE"
tags: [AI, LLM, MoE, Paper-Review]
lang: kr
translation-url: /2026-07-21-latent-moe-en/
readtime: true
mathjax: false
---

## 논문 정보

- **제목**: LatentMoE: Toward Optimal Accuracy per FLOP and Parameter in Mixture of Experts
- **저자**: Venmugil Elango 외 (**NVIDIA**)
- **arXiv**: [2601.18089](https://arxiv.org/abs/2601.18089) (2026년 1월)

이 글은 [Kimi K3 분석](/2026-07-21-kimi-k3-kr/)에서 언급한 **Stable LatentMoE**의 기반이 되는 논문을 다룬다. 먼저 분명히 할 점: **LatentMoE 논문은 NVIDIA의 연구**이며 Nemotron-3 Super/Ultra 모델에 채택됐다. Moonshot의 K3는 이 LatentMoE 개념을 "Stable LatentMoE"로 변형해 적용한 것이다. 이 구분을 지키며 원 논문부터 본다.

---

## 문제: MoE는 비용당 최적인가

**MoE(Mixture of Experts)** 는 토큰마다 일부 전문가만 활성화해, 전체 파라미터는 크되 토큰당 연산은 적게 유지한다. 대형 모델의 표준 확장 방식이다.

논문의 질문은 이것이다. 기존 MoE 구조는 추론 비용 대비 얼마나 최적인가. 여기서 비용은 두 축으로 측정된다. **FLOP당 정확도**와 **파라미터당 정확도**다. 같은 연산량, 같은 파라미터로 더 높은 정확도를 낼 여지가 있는가.

---

## LatentMoE

핵심 아이디어는 **전문가 연산을 은닉차원에서 분리**하는 것이다.

![표준 MoE vs LatentMoE](/assets/img/posts/latent-moe/latentmoe.png)

표준 MoE는 전문가가 모델의 큰 은닉차원 `d`에서 직접 연산한다. LatentMoE는 들어오는 활성값을 먼저 **저차원 잠재공간 `d'`로 투영**한다. 라우팅과 전문가 연산을 이 압축된 잠재공간에서 수행하고, 결과를 다시 원래 차원 `d`로 복원한다.

라우팅과 전문가 계산을 모델의 은닉차원과 분리(decouple)한 것이 핵심이다. 전문가가 작은 `d'`에서 동작하므로 같은 FLOP·파라미터로 더 많은 전문가나 더 효율적인 표현을 확보할 수 있다.

---

## 결과

- **규모**: 최대 95B 파라미터, 1T 토큰 학습으로 검증
- **효율**: 표준 MoE 대비 FLOP당·파라미터당 정확도에서 일관되게 우위
- **채택**: NVIDIA Nemotron-3 Super 및 Ultra 모델에 적용

FLOP당·파라미터당이라는 비용 정규화 지표에서 표준 MoE를 넘었다는 것이 핵심이다. 절대 규모를 키우는 것이 아니라, 같은 비용으로 더 나은 정확도를 낸다는 방향이다.

---

## 한계

논문 초록만으로는 세부 아키텍처, 벤치마크 수치, 로드밸런싱 방법의 구체가 제한적이다. 잠재공간 차원 `d'`의 선택, 투영·복원의 추가 연산이 이득을 얼마나 상쇄하는지는 본문 확인이 필요하다.

---

## Kimi K3의 Stable LatentMoE

[Kimi K3](/2026-07-21-kimi-k3-kr/)는 이 LatentMoE 개념을 **Stable LatentMoE**라는 이름으로 변형 적용한다. K3는 여기에 자체 로드밸런싱 기법인 **Quantile Balancing**을 더한다. 라우터 점수의 상위 분위수에 드는 토큰을 전문가로 보내는 방식으로, 결정적이고 하이퍼파라미터가 없으며 죽은 전문가 없이 균등 활용을 보장한다고 주장한다.

다만 K3의 Stable LatentMoE와 Quantile Balancing의 정확한 수학적 세부는 아직 공개되지 않았다. K3의 896 전문가 구조가 이 방향 위에 서 있다는 점까지가 현재 확인되는 사실이다. 정식 기술 보고서가 나오면 NVIDIA LatentMoE와 Moonshot Stable LatentMoE의 차이가 분명해질 것이다.

---

## 레퍼런스

- Venmugil Elango et al. (NVIDIA). "LatentMoE: Toward Optimal Accuracy per FLOP and Parameter in Mixture of Experts." arXiv:2601.18089, 2026. [arXiv](https://arxiv.org/abs/2601.18089)
- 관련 글: [Kimi K3 분석](/2026-07-21-kimi-k3-kr/) · [Kimi Delta Attention](/2026-07-21-kimi-delta-attention-kr/) · [Attention Residuals](/2026-07-21-attention-residuals-kr/)

수치는 논문 보고값이다. 다이어그램은 논문 개념을 바탕으로 직접 제작했다. K3의 Stable LatentMoE 세부는 미공개이므로 추정하지 않았다.
