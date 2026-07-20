---
layout: post
title: "논문 리뷰: Attention Residuals, 잔차 연결을 학습된 어텐션으로"
subtitle: "10년 된 고정 잔차를 계층 깊이에 대한 어텐션으로 대체하다"
tags: [AI, LLM, Transformer, Paper-Review]
lang: kr
translation-url: /2026-07-21-attention-residuals-en/
readtime: true
mathjax: false
---

## 논문 정보

- **제목**: Attention Residuals
- **저자**: Kimi Team (Moonshot AI), Guangyu Chen 외
- **arXiv**: [2603.15031](https://arxiv.org/abs/2603.15031) (2026년 3월)
- **코드**: [MoonshotAI/Attention-Residuals](https://github.com/MoonshotAI/Attention-Residuals)

이 글은 [Kimi K3 분석](/2026-07-21-kimi-k3-kr/)에서 언급한 세 자체 기법 중 하나인 **Attention Residuals(AttnRes)** 의 원 논문을 다룬다.

---

## 배경: 잔차 연결의 오래된 관성

**잔차 연결(residual connection)** 은 2015년 ResNet 이후 딥 네트워크의 표준이다. 현대 LLM은 여기에 PreNorm을 결합해 쓴다. 각 계층의 출력을 잔차 스트림에 더하는 방식이다.

문제는 이 누적이 획일적이라는 점이다. 모든 계층의 출력이 **고정 가중치 1로 동일하게** 누적된다. 이 균일 합산은 세 가지 부작용을 낳는다.

- **은닉 상태의 무제어 증가**: 계층이 깊어질수록 출력이 계속 쌓여 상태 크기가 통제 없이 커진다.
- **표현 희석**: 각 계층의 개별 기여가 깊이에 따라 점점 묽어진다.
- **선택 불가**: 고정 가중치이므로 내용에 따라 특정 깊이의 표현을 골라 쓸 수 없다.

10년 된 이 고정 방식을 학습 가능한 것으로 바꾸자는 것이 논문의 출발점이다.

---

## Attention Residuals

**AttnRes**는 고정 누적을 **이전 계층 출력들에 대한 softmax 어텐션**으로 대체한다.

![표준 잔차 vs Attention Residuals](/assets/img/posts/attention-residuals/attnres.png)

각 계층이 하나의 질의처럼 이전 계층들을 되돌아보고, 학습된 입력 의존 가중치로 필요한 표현만 선택해 가져온다. 모든 이전 계층을 동일하게 취급하지 않는다. 입력에 따라 어느 깊이의 표현이 중요한지를 모델이 동적으로 판단한다.

잔차 스트림을 "이전까지의 모든 계층 출력에 대한 어텐션"으로 재정의한 것이다. 계층 방향(깊이 축)으로 어텐션을 도입했다고 볼 수 있다.

### Block AttnRes: 규모를 위한 절충

모든 이전 계층 출력에 어텐션을 걸면 대규모 학습에서 메모리와 통신 비용이 크다. 논문은 **Block AttnRes**를 제시한다. 계층을 블록으로 묶고 블록 단위 표현에 어텐션을 건다. 복잡도를 전체 계층 수 기준에서 블록 수 기준으로 낮추면서 전체 AttnRes 이득의 대부분을 유지한다. 캐시 기반 파이프라인 통신과 2단계 연산 전략을 더해, 표준 잔차 연결의 실용적 drop-in 대체가 된다.

---

## 결과

- **GPQA-Diamond**: 48B 모델에서 7.5점 향상
- **학습 효율**: 2% 미만의 추가 비용으로 약 25% 향상
- **성능 등가**: AttnRes 적용 모델이 더 많은 컴퓨트로 학습한 기준선과 대등
- **깊이 효과**: 계층 간 출력 크기와 그래디언트 분포가 더 균일해짐 (앞서 지적한 무제어 증가/희석 문제의 완화)
- **스케일링**: 여러 모델 크기에서 개선이 일관됨 (스케일링 법칙 실험)

핵심은 "잔차 연결"이라는 거의 손대지 않던 컴포넌트를 학습 가능하게 만든 것만으로 의미 있는 이득을 얻었다는 점이다. GPQA-Diamond 7.5점은 48B 규모에서 작지 않은 폭이다.

---

## 한계

논문 초록은 한계를 명시하지 않지만 구조상 유의점이 있다. 모든 이전 계층에 어텐션을 거는 전체 AttnRes는 메모리·통신 부담이 커 Block AttnRes 근사가 필요하다. Block AttnRes는 "대부분의 이득"을 유지한다고 표현되므로, 전체 대비 일부 성능-효율 절충이 존재한다. 추론 시 깊이 축 softmax 연산이 약간의 지연을 더할 수 있다.

---

## Kimi K3와의 연결

AttnRes는 [Kimi K3](/2026-07-21-kimi-k3-kr/)의 학습 효율을 뒷받침하는 기법이다. K3 분석에서 언급한 "2% 미만 추가 비용으로 학습 효율 약 25% 향상" 주장의 근거가 이 논문이다. K2 대비 약 2.5배 스케일링 효율이라는 K3의 서사에서, [KDA](/2026-07-21-kimi-delta-attention-kr/)가 추론 효율을 맡는다면 AttnRes는 학습 효율을 맡는다.

---

## 레퍼런스

- Kimi Team. "Attention Residuals." arXiv:2603.15031, 2026. [arXiv](https://arxiv.org/abs/2603.15031)
- 코드: [GitHub](https://github.com/MoonshotAI/Attention-Residuals)
- 관련 글: [Kimi K3 분석](/2026-07-21-kimi-k3-kr/) · [Kimi Delta Attention](/2026-07-21-kimi-delta-attention-kr/)

수치는 논문 보고값이다. 다이어그램은 논문 개념을 바탕으로 직접 제작했다.
