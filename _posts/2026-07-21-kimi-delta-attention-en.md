---
layout: post
title: "Paper Review: Kimi Delta Attention — When Linear Attention Surpasses Full Attention"
subtitle: "Kimi Linear — handling a 1M context with channel-wise gating and a hybrid design"
tags: [AI, LLM, Attention, Paper-Review]
lang: en
translation-url: /2026-07-21-kimi-delta-attention-kr/
readtime: true
mathjax: true
---

## Paper Info

- **Title**: Kimi Linear: An Expressive, Efficient Attention Architecture
- **Authors**: Kimi Team (Moonshot AI)
- **arXiv**: [2510.26692](https://arxiv.org/abs/2510.26692) (October 2025)
- **Code**: [MoonshotAI/Kimi-Linear](https://github.com/MoonshotAI/Kimi-Linear) · [Model (48B/3B)](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct)

This post covers the source paper for **Kimi Delta Attention (KDA)**, one of the three in-house techniques mentioned in the [Kimi K3 analysis](/2026-07-21-kimi-k3-en/).

---

## Background: The Full-vs-Linear Attention Trade-off

The transformer's standard full attention is expressive but quadratically expensive in sequence length. At a 1M-token context, its KV cache and computation become hard to sustain.

**Linear attention** lowers this to linear cost. It compresses the attention state into a fixed-size recurrent state (RNN-like), so it does not pile up KV endlessly per token. The catch is expressiveness. Cramming information into a fixed-size state, it was conventionally believed to fall behind full attention on long dependencies.

The paper's question is clear: can linear attention actually surpass full attention under a fair comparison?

---

## Kimi Delta Attention

KDA extends **Gated DeltaNet**. DeltaNet is a linear-attention family that updates a recurrent state with the delta rule. Gated DeltaNet adds a decay gate on top — controlling how much of the previous state to forget.

The key difference is the **granularity of the gating**.

```
Gated DeltaNet:  previous state × (scalar decay)
                 → every hidden dimension forgets at the same rate

KDA:             previous state × (per-channel vector decay, diagonal matrix)
                 → each dimension has its own forgetting rate
```

Standard Gated DeltaNet multiplies the recurrent state by a single scalar decay, meaning every hidden dimension forgets at the same rate. KDA replaces that scalar with a **per-channel vector** turned into a diagonal matrix, giving each dimension its own forgetting rate. This fine-grained gating uses the finite recurrent-state memory more effectively.

Mathematically, it uses a **DPLR (Diagonal-Plus-Low-Rank)** transition matrix — a specialized variant that reduces computation versus the general DPLR form while staying more consistent with the classical delta rule. For hardware efficiency it is implemented with a chunkwise algorithm, and the authors open-sourced the `FlashKDA` kernel and a vLLM implementation.

---

## The Hybrid Design

KDA does not fully replace full attention on its own. The paper interleaves KDA with **MLA (Multi-head Latent Attention)** at the layer level.

![Kimi Linear hybrid attention](/assets/img/posts/kimi-delta-attention/kda-hybrid.png)

The ratio is **KDA 3 : MLA 1**. Three linear layers handle local sequence structure cheaply, while one full-attention layer preserves global information flow. Because most layers do not accumulate a KV cache, memory drops sharply.

This arrangement takes the best of both: linear attention's low cost and full attention's global expressiveness. It is neither purely linear nor purely full — a deliberate compromise.

---

## Results

The paper validates with a Kimi Linear model of 3B activated / 48B total parameters.

- **KV cache**: up to 75% reduction versus full MLA
- **Decode throughput**: up to 6× at 1M context
- **Quality**: under identical training recipes, it beats full MLA by a sizeable margin across all evaluated tasks

The last point is the notable one. The paper claims this is the first time linear attention surpasses full attention under fair comparison across diverse regimes — short-context, long-context, and RL scaling. The result is that linear attention leads not only on efficiency but on quality.

---

## Limitations

The abstract does not enumerate specific failure modes. Still, some structural caveats stand: the hybrid ratio (3:1) and the DPLR form are design choices, and the optimal ratio may shift at other model scales or tasks. Since it still includes full-attention layers rather than being purely linear, tasks that need global information rely on those layers.

---

## Connection to Kimi K3

KDA is the core attention mechanism of [Kimi K3](/2026-07-21-kimi-k3-en/). K3 scales this Kimi Linear KDA to 2.8T to handle its 1M context. The "6.3× decoding, 75% KV reduction" claims mentioned in the K3 analysis trace back to this paper. Moonshot's contribution of the KDA implementation to vLLM also originates here.

---

## References

- Kimi Team. "Kimi Linear: An Expressive, Efficient Attention Architecture." arXiv:2510.26692, 2025. [arXiv](https://arxiv.org/abs/2510.26692)
- Code/model: [GitHub](https://github.com/MoonshotAI/Kimi-Linear) · [HuggingFace](https://huggingface.co/moonshotai/Kimi-Linear-48B-A3B-Instruct)
- Related: [Kimi K3 analysis](/2026-07-21-kimi-k3-en/)

The numbers are the paper's reported values. The diagram is original, built from the paper's concepts.
