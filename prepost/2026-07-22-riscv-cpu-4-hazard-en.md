---
layout: post
title: "RISC-V CPU #4: The Pipeline in Depth — Hazards and Branch Prediction"
subtitle: "How hardware detects and resolves the conflicts between overlapping instructions"
tags: [CPU, RISC-V, Architecture, Pipeline, Computer-Architecture]
lang: en
translation-url: /2026-07-22-riscv-cpu-4-hazard-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| 1 | [What is RISC-V?](/2026-07-19-riscv-cpu-1-intro-en/) | ✅ |
| 2 | [What is an instruction: encoding and formats](/2026-07-20-riscv-cpu-2-instruction-en/) | ✅ |
| 3 | [The macro structure of the pipeline](/2026-07-21-riscv-cpu-3-pipeline-en/) | ✅ |
| 4 | The pipeline in depth: hazards and branch prediction | ✅ |
| 5 | Summary, advanced microarchitecture, other CPU architectures | 🔲 |

---

## Overlapping Means Conflicts

Part 3 showed the pipeline raises throughput by overlapping five instructions, and it foreshadowed that problems arise when instructions are entangled. This entanglement is called a **hazard**.

A hazard is any situation that prevents the pipeline from smoothly completing one instruction every clock. There are three kinds.

| Kind | Cause |
|:---|:---|
| Structural hazard | Two instructions need the same hardware resource at once |
| Data hazard | A later instruction needs an earlier one's result before it is ready |
| Control hazard | The next instruction to run depends on a branch outcome |

---

## Structural Hazards: Mostly Avoided by Design

A structural hazard occurs when two instructions try to use the same resource at once. The classic RISC-V pipeline designs most of these away up front.

- **Separate instruction and data memory**: the IF stage uses instruction memory; the MEM stage uses data memory. Being separate, IF and MEM overlapping in the same clock do not conflict over a memory port.
- **Half-clock split on the register file**: WB's write happens in the first half of the clock, ID's read in the second half. Even when one instruction writes and another reads in the same clock, they do not conflict.

Thanks to this design, structural hazards rarely occur in the basic 5-stage pipeline. The real remaining problems are data hazards and control hazards.

---

## Data Hazards: Wanting a Value That Doesn't Exist Yet

The most common data hazard is **RAW (Read After Write)** — a later instruction tries to read a value an earlier one will write.

```
add x5, x6, x7    ← computes x5
sub x8, x5, x9    ← uses x5
```

As seen in part 3, at the moment `sub` reads `x5` (ID, 3rd clock), `add` has not yet written `x5` to the register (WB, 5th clock). Left naive, `sub` reads a stale `x5`.

### Forwarding: Deliver the Result Early

The key to the fix is one observation. `add`'s result actually exists the instant EX finishes (end of the 3rd clock). There is no need to wait until it is written to a register (WB, 5th clock). That value sits in a pipeline register.

**Forwarding (bypassing)** delivers this value directly to where it is needed, without going through the register file.

![Data hazard: forwarding and the load-use stall](/assets/img/posts/riscv-cpu-4-hazard/data-hazard.png)

Panel ① above is this case. `add`'s EX output (C3) is taken from the `EX/MEM` pipeline register and sent straight to `sub`'s EX input (C4). Forwarding hardware detects it by comparing pipeline registers — "does the later instruction's source register number match the earlier instruction's destination register number?" If so, it selects the forwarded value as the ALU input instead of the register file. Resolved with no stall.

### The Load-Use Hazard: When Forwarding Isn't Enough

Forwarding does not always work. The problem is when the earlier instruction is a load.

```
lw  x5, 0(x6)     ← reads x5 from memory
sub x8, x5, x9    ← uses x5
```

`lw`'s value is not available until the MEM stage that reads memory finishes (end of C4). But `sub` wants that value in EX (C4). The value appears in the same clock it is needed, so forwarding cannot bridge the timing.

Panel ② above is this case. `sub`'s EX is delayed by one clock. This delay is called a **stall** or **bubble**. After the delay (C5), `lw`'s value (ready at the end of C4) can be forwarded. This situation — using a loaded value immediately after the load — is the **load-use hazard**, and even with forwarding, one bubble cannot be avoided.

The compiler can reduce this bubble. By inserting an unrelated instruction between the load and its use, it fills the bubble slot with useful work. This reordering optimization is called instruction scheduling.

---

## Control Hazards: Not Knowing Where to Go Yet

A branch instruction creates a different kind of problem. The next instruction to run depends on the branch outcome, but that outcome is only decided later.

```
beq x6, x7, LABEL   ← if x6 == x7 go to LABEL, else the next instruction
(next instruction)   ← which one should we fetch?
```

Whether a branch is taken can only be known by comparing two registers, and that comparison happens in EX. But the pipeline fetches an instruction every clock. By the time the branch reaches EX (3rd clock), the instructions after it are already in IF and ID. If the branch resolved in an unexpected direction, those wrongly fetched instructions must be discarded. This discard is called a **flush**.

```
If we blindly fetch following instructions until the branch resolves in EX:
  branch taken → the fall-through instructions already in IF/ID are wrong → flush
```

Flushed clocks are wasted. The way to reduce this waste is **branch prediction**.

### Static Prediction

The simplest prediction assumes one direction always.

- **Always not-taken**: assume the branch is not taken and keep fetching the next (fall-through) instruction. Flush if it is taken.
- **BTFN (Backward Taken, Forward Not-taken)**: predict backward branches as taken and forward branches as not-taken. A loop's closing branch goes backward and is usually taken, so this rule fits well.

Static prediction keeps the hardware simple but does not reflect the program's actual behavior.

### Dynamic Prediction: The 2-bit Saturating Counter

Dynamic prediction records a branch's past history to predict the next outcome. The most widely used form is the **2-bit saturating counter**.

![2-bit saturating counter branch predictor](/assets/img/posts/riscv-cpu-4-hazard/branch-predictor.png)

Each branch (indexed by PC) holds one of four states: Strongly Taken, Weakly Taken, Weakly Not-taken, Strongly Not-taken. If the branch is actually taken, the state moves one step toward the taken side; if not-taken, one step the other way. The prediction is taken if the current state is on the taken side, not-taken otherwise.

The reason for using 2 bits is **hysteresis**. A 1-bit predictor flips its prediction after a single miss. A loop is not-taken exactly once, at its last iteration; a 1-bit predictor mispredicts the next loop entry because of that single occurrence. With 2 bits, a single miss from a strong state only moves to a weak state, keeping the prediction direction. It is not swayed by one exceptional case.

Prediction needs not only direction but also the target address. A **BTB (Branch Target Buffer)** stores the past target address for a branch PC, so the next PC can be set immediately in the IF stage upon prediction.

### RISC-V's Choice: No Delay Slots

Here is one point about ISA design. Classic MIPS had a **branch delay slot**. It fixed into the ISA that the instruction right after a branch always executes regardless of the branch outcome, filling one flush slot in software.

RISC-V did not include delay slots. Delay slots fit a simple 5-stage pipeline but get in the way of deeper, wider modern pipelines. As seen in part 1, the ISA should not force a specific microarchitecture. RISC-V left this to the microarchitectural technique of branch prediction instead of delay slots. The pipeline structure can change while the ISA stays the same.

---

## Viewing It as Cost

Hazards eat into the pipeline's ideal throughput. Ideally it is one clock per instruction (CPI = 1), but stalls and mispredictions raise CPI.

A simple estimate of branch-misprediction cost: suppose branches are 20% of all instructions, prediction accuracy is 90%, and the penalty per misprediction is 2 clocks.

```
Extra CPI from branches ≈ 0.20 × (1 - 0.90) × 2 = 0.04
```

So CPI rises from 1 to about 1.04. If accuracy drops or the pipeline deepens so the penalty grows, this value climbs quickly. Deepening the pipeline raises the clock but also raises the misprediction penalty — a trade-off. This balance is a key factor in setting pipeline depth.

---

## Summary

| Hazard | Problem | Resolution |
|:---|:---|:---|
| Structural | Resource conflict | Separate memories, half-clock split register file (designed away) |
| Data (RAW) | Need a value that doesn't exist yet | Forwarding |
| Data (load-use) | Use a loaded value immediately | Forwarding + 1 bubble |
| Control (branch) | Next PC undecided | Branch prediction (static / dynamic 2-bit) |

Hazards are the price of overlapping the pipeline. Structural hazards are mostly designed away, and data hazards are resolved by forwarding (with one bubble added for load-use). Control hazards reduce their waste through branch prediction, where the 2-bit saturating counter provides a prediction unswayed by a single exceptional case. RISC-V left these problems to the microarchitecture rather than putting delay slots into the ISA. The next part goes beyond the simple 5-stage seen so far, surveying advanced techniques like superscalar and out-of-order execution and other CPU architectures to close the series.

Next: RISC-V CPU #5 — Summary, advanced microarchitecture, other CPU architectures (upcoming)
