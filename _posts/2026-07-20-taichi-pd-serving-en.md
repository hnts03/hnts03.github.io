---
layout: post
title: "Paper Review: TaiChi — Unifying Prefill-Decode for Goodput-Optimized LLM Serving"
subtitle: "Aggregation or disaggregation? Combine both to win under balanced SLOs"
tags: [AI, LLM, Serving, GPU, Paper-Review]
lang: en
translation-url: /2026-07-20-taichi-pd-serving-kr/
readtime: true
mathjax: false
---

## Paper Info

- **Title**: Prefill-Decode Aggregation or Disaggregation? Unifying Both for Goodput-Optimized LLM Serving
- **Authors**: Chao Wang, Pengfei Zuo, Zhangyu Chen, Yunkai Liang, Zhou Yu, Ming-Chang Yang (CUHK, Huawei Cloud, Sun Yat-sen University)
- **arXiv**: [2508.01989v1](https://arxiv.org/abs/2508.01989)

LLM serving has a long-running debate: should prefill and decode run on the same GPU (aggregation) or be separated (disaggregation)? TaiChi answers "both." Let's start from the background.

---

## Background: Two Phases, Two Metrics

LLM inference splits into two phases of different character. This was covered in the [LLM serving overview](/2026-06-19-llm-serving-overview-en/), but here is the essence again.

- **Prefill**: processes the entire input prompt at once to produce the first token. Compute-bound.
- **Decode**: generates tokens one at a time, autoregressively. Memory-bandwidth-bound.

The two phases are judged by different latency metrics.

- **TTFT (Time To First Token)**: time to the first token. Determined by prefill.
- **TPOT (Time Per Output Token)**: time per generated token. Determined by decode.

A serving system's goal is not throughput but **goodput** — the rate of requests that satisfy **both** the TTFT and TPOT SLOs (service-level objectives). No matter how many requests are processed, those that miss a latency target do not count toward goodput.

---

## The Problem: Both Aggregation and Disaggregation Are Half-Solutions

There are two ways to place prefill and decode, and each does well on only one metric.

![Three LLM serving modes](/assets/img/posts/taichi-pd-serving/serving-modes.png)

**PD Aggregation**

Prefill and decode run on the same instance. vLLM's continuous batching combined with chunked prefill is the representative approach. GPU utilization is high and prefill is fast, so **TTFT is good**. But prefill and decode interfere on the same GPU. When a heavy prefill cuts in, ongoing decodes are delayed, so **TPOT worsens**.

**PD Disaggregation**

Dedicated prefill instances and dedicated decode instances are separated — the DistServe / Splitwise family. Prefill does not interfere with decode, so **TPOT is good**. When prefill finishes, the KV cache is transferred to a decode instance. The problem is that the number of prefill instances is limited, so prefill capacity is insufficient. Under load, prefill queuing grows and **TTFT worsens**.

**Key observation**: when only one SLO is tight, one approach wins. Tight TTFT with loose TPOT favors aggregation; the reverse favors disaggregation. But under the **balanced SLOs** common in real deployments (both TTFT and TPOT moderately tight), both fail.

The paper's Table 2 shows this numerically. Under a balanced SLO of TTFT 6s and TPOT 100ms, SLO attainment is only 16% for aggregation and 50% for disaggregation. Neither can handle the balanced condition.

---

## The Key Idea: Unification and Latency Shifting

TaiChi unifies the two approaches into one system. The core concept is **latency shifting** — reclaiming GPU resources from requests that already meet their SLO with slack, and reallocating them to requests at risk of violation. Latency slack is moved between requests.

Three axes support this.

1. **Hybrid mode**: batch in aggregated fashion for high utilization, but control requests in disaggregated fashion for fine-grained control.
2. **Differentiated-capability instances**: two kinds of instances with different character.
3. **Two scheduling mechanisms**: flowing decode scheduling and length-aware prefill scheduling.

---

## Architecture: Differentiated Instances and Three Sliders

TaiChi splits instances into two kinds. The difference is the prefill **chunk size**, which sets how finely prefill is split to interleave between decodes.

- **P-heavy instances**: large chunks (e.g., 1024). Raise prefill throughput and TTFT, at the cost of heavier interference with decode.
- **D-heavy instances**: small chunks (e.g., 128–512). Reduce prefill-decode interference for lower TPOT, at the cost of slower prefill.

This is expressed with three configurable sliders.

| Slider | Meaning |
|:---:|:---|
| `R_PD` | Ratio of P-heavy to D-heavy instances |
| `S_P` | Prefill chunk size for P-heavy |
| `S_D` | Prefill chunk size for D-heavy |

Adjusting these sliders places the system near pure aggregation, near pure disaggregation, or anywhere in between. The paper finds optimal slider values via offline search and reconfigures only on significant workload shifts.

---

## Scheduling 1: Flowing Decode (TPOT Control)

Decode requests flow between instances to manage TPOT per request. It works in three stages.

```
1. Low-interference initialization
   All decode starts on D-heavy
   → so short-output requests don't violate TPOT prematurely

2. Longest-first degradation
   When D-heavy memory hits a threshold,
   migrate the longest-output requests to P-heavy
   → requests that already benefited long can tolerate some degradation

3. TPOT-aware backflow
   Requests nearing the TPOT SLO migrate back to D-heavy
   → to preserve quality
```

The key is redistributing latency slack. A long-output request has already generated many tokens at low latency, so it has slack. It yields that slack to requests at risk.

---

## Scheduling 2: Length-Aware Prefill (TTFT Control)

Prefill requests are routed by length to manage TTFT.

- Estimate TTFT feasibility on each instance (queuing + execution + transfer time).
- Choose the instance with the fewest queued prefill tokens.
- **Preferentially assign short requests to the slower D-heavy instances**, reserving fast P-heavy for long, time-sensitive requests.

A short request can meet its TTFT even on a slow instance. The strategy conserves fast resources for the requests that truly need them — another form of latency shifting.

---

## Results

These are the numbers the paper reports, on Qwen2.5-14B and 32B models, chatbot (ShareGPT) and summarization (ArXiv) workloads, on a single node with 8 A100 GPUs.

**Goodput Improvement**

| Baseline | Chatbot | Summarization |
|:---|:---:|:---:|
| vs PD Aggregation | 9–25% | 20–47% |
| vs PD Disaggregation | 29–49% | 30–77% |

On summarization, it reports up to 77% goodput improvement over disaggregation.

**Latency Reduction at Maximum Goodput**

- TTFT: 2.42×–13.20× reduction vs. disaggregation
- TPOT: 1.11×–1.69× reduction vs. aggregation

**Each Technique's Contribution (ablation)**

![Each technique's contribution to SLO attainment](/assets/img/posts/taichi-pd-serving/ablation.png)

From the baseline (CP256, fixed chunk 256), SLO attainment is 66.6%. Adding flowing decode reaches 79.5% (+12.9%), and adding length-aware prefill on top reaches 91.2% (+11.7%). The two scheduling mechanisms contribute in similar measure.

**Overhead**

The cost TaiChi adds is small. KV cache transfer is 0.20% of total request time, prefill scheduling 0.01%, decode scheduling 0.89%.

---

## Limitations

The limitations the paper states are as follows.

- **Single-node evaluation**: validated only on a single node with 8 A100 GPUs. Multi-node performance is unexplored — meaning inter-node KV-transfer factors are not accounted for.
- **Offline configuration search**: optimal slider values must be found offline, reconfigured only on significant workload shifts. Not real-time adaptation. Auto-tuning these heuristics could be a direction for new research.
- **Reactive scheduling**: output length is not known in advance, so requests are migrated reactively rather than predictively. A paper called WindServe takes a similar approach.
- **Prediction-accuracy dependence**: scheduling accuracy depends on execution-time prediction (tens of microseconds).

---

## Takeaways and Perspective

TaiChi's contribution is reframing the "aggregation vs. disaggregation" dichotomy itself. The two approaches are each optimal for different SLO conditions; neither is absolutely superior. Under the balanced SLOs common in real deployments, the answer is to mix both and shift latency slack between requests.

The striking part is the unified lens of latency shifting. Flowing decode and length-aware prefill look like different techniques on the surface, but both apply one principle — "move resources from slack-rich requests to at-risk ones" — to decode and prefill respectively. Parameterizing the system with three sliders that include aggregation and disaggregation as extremes is a clean design.

The limitations are clear. Single-node validation and offline slider search do not transfer directly to the dynamic workloads of large clusters. Scaling to multiple nodes and online adaptation remain future work. Still, in my view, the perspective of turning the PD debate into a problem of unification is worth referencing in future serving-system design.

---

## References

- Chao Wang, Pengfei Zuo, Zhangyu Chen, Yunkai Liang, Zhou Yu, Ming-Chang Yang. "Prefill-Decode Aggregation or Disaggregation? Unifying Both for Goodput-Optimized LLM Serving." arXiv:2508.01989v1, 2025. [arXiv](https://arxiv.org/abs/2508.01989) | [HTML](https://arxiv.org/html/2508.01989v1)

The numbers and concepts in this post are cited from the paper above. The diagrams are original, built from the concepts rather than reproduced from the paper.
