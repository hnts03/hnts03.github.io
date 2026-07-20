---
layout: post
title: "Paper Review: Attention Residuals — Turning the Residual Connection into Learned Attention"
subtitle: "Replacing the decade-old fixed residual with attention over layer depth"
tags: [AI, LLM, Transformer, Paper-Review]
lang: en
translation-url: /2026-07-21-attention-residuals-kr/
readtime: true
mathjax: false
---

## Paper Info

- **Title**: Attention Residuals
- **Authors**: Kimi Team (Moonshot AI), Guangyu Chen et al.
- **arXiv**: [2603.15031](https://arxiv.org/abs/2603.15031) (March 2026)
- **Code**: [MoonshotAI/Attention-Residuals](https://github.com/MoonshotAI/Attention-Residuals)

This post covers the source paper for **Attention Residuals (AttnRes)**, one of the three in-house techniques mentioned in the [Kimi K3 analysis](/2026-07-21-kimi-k3-en/).

---

## Background: The Old Inertia of Residual Connections

The **residual connection** has been the standard for deep networks since ResNet in 2015. Modern LLMs combine it with PreNorm, adding each layer's output to a residual stream.

The problem is that this accumulation is uniform. Every layer's output is accumulated with a **fixed weight of 1**. This uniform summation causes three side effects.

- **Uncontrolled hidden-state growth**: as layers deepen, outputs keep piling up and the state grows without control.
- **Representation dilution**: each layer's individual contribution gets progressively diluted with depth.
- **No selection**: with fixed weights, the model cannot pick representations from specific depths based on content.

The paper's starting point is to make this decade-old fixed scheme learnable.

---

## Attention Residuals

**AttnRes** replaces the fixed accumulation with **softmax attention over preceding layer outputs**.

![Standard residual vs Attention Residuals](/assets/img/posts/attention-residuals/attnres.png)

Each layer acts like a query looking back over earlier layers, selecting only the representations it needs with learned, input-dependent weights. It does not treat all preceding layers equally. The model dynamically decides which depth's representation matters for a given input.

It redefines the residual stream as "attention over all prior layer outputs" — introducing attention along the layer (depth) axis.

### Block AttnRes: A Compromise for Scale

Attending over every preceding layer output is costly in memory and communication at large-scale training. The paper introduces **Block AttnRes**: partition layers into blocks and attend over block-level representations. This lowers the complexity from the full-layer count to the block count while preserving most of the gains of full AttnRes. Combined with cache-based pipeline communication and a two-phase computation strategy, it becomes a practical drop-in replacement for standard residual connections.

---

## Results

- **GPQA-Diamond**: +7.5 points on the 48B model
- **Training efficiency**: about 25% higher at under 2% additional cost
- **Performance parity**: an AttnRes-equipped model matches a baseline trained with more compute
- **Depth effects**: more uniform output magnitudes and gradient distribution across depth (mitigating the uncontrolled-growth/dilution problems noted above)
- **Scaling**: the improvement is consistent across model sizes (scaling-law experiments)

The key point is that a meaningful gain came simply from making the "residual connection" — a component almost never touched — learnable. A +7.5 on GPQA-Diamond is not a small margin at 48B scale.

---

## Limitations

The abstract does not state limitations, but structural caveats exist. Full AttnRes, attending over all preceding layers, has high memory and communication cost, requiring the Block AttnRes approximation. Block AttnRes is described as preserving "most of the gains," implying some performance-efficiency trade-off versus the full version. At inference, the depth-axis softmax may add slight latency.

---

## Connection to Kimi K3

AttnRes underwrites the training efficiency of [Kimi K3](/2026-07-21-kimi-k3-en/). The "about 25% higher training efficiency at under 2% additional cost" claim in the K3 analysis traces back to this paper. In K3's narrative of ~2.5× scaling efficiency over K2, if [KDA](/2026-07-21-kimi-delta-attention-en/) handles inference efficiency, AttnRes handles training efficiency.

---

## References

- Kimi Team. "Attention Residuals." arXiv:2603.15031, 2026. [arXiv](https://arxiv.org/abs/2603.15031)
- Code: [GitHub](https://github.com/MoonshotAI/Attention-Residuals)
- Related: [Kimi K3 analysis](/2026-07-21-kimi-k3-en/) · [Kimi Delta Attention](/2026-07-21-kimi-delta-attention-en/)

The numbers are the paper's reported values. The diagram is original, built from the paper's concepts.
