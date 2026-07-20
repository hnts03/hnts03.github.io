# taichi-pd-serving 이미지 출처

원 논문: Chao Wang et al., "Prefill-Decode Aggregation or Disaggregation? Unifying Both for Goodput-Optimized LLM Serving", arXiv:2508.01989v1. 아래 그림은 논문 원본 figure를 복제한 것이 아니라, 논문의 개념을 바탕으로 직접 제작한 다이어그램이다. 수치는 논문 보고값을 인용.

## serving-modes.png
- **source_type**: generated (custom matplotlib script)
- **content**: 세 가지 LLM 서빙 방식(PD Aggregation / Disaggregation / TaiChi hybrid)의 구조와 TTFT/TPOT 특성 비교. 논문 개념 기반 원작 다이어그램
- **license**: original diagram (concept from arXiv:2508.01989, fair-use summary)

## ablation.png
- **source_type**: generated (scripts/gen-diagram.py, bar chart)
- **content**: SLO 달성률에 대한 각 기법의 기여 (기준 66.6% → Flowing Decode 79.5% → Length-aware Prefill 91.2%). 수치 출처: 논문 Figure 18 (ablation)
- **license**: original chart, data from arXiv:2508.01989
