---
layout: post
title: "RISC-V CPU #3: The Macro Structure of the Pipeline"
subtitle: "The five stages one instruction passes through, and the hardware unit behind each"
tags: [CPU, RISC-V, Architecture, Pipeline, Computer-Architecture]
lang: en
translation-url: /2026-07-21-riscv-cpu-3-pipeline-kr/
readtime: true
mathjax: false
---

## Series Roadmap

| # | Topic | Status |
|:--:|:---|:---:|
| 1 | [What is RISC-V?](/2026-07-19-riscv-cpu-1-intro-en/) | ✅ |
| 2 | [What is an instruction: encoding and formats](/2026-07-20-riscv-cpu-2-instruction-en/) | ✅ |
| 3 | The macro structure of the pipeline and its hardware units | ✅ |
| 4 | Pipeline in depth: hazard handling and branch prediction | 🔲 |
| 5 | Summary, advanced microarchitecture, other CPU architectures | 🔲 |

---

## The Five Jobs of Processing One Instruction

Part 2 showed an instruction is a 32-bit number, and decoding extracts its fields. But actually executing an instruction takes more than decoding. To finish one instruction, the CPU must do five different jobs in order.

Take `lw x5, 8(x6)` (read a value from memory into x5):

1. Fetch the instruction itself from memory.
2. Interpret it and read the needed register (`x6`).
3. Compute the address (`x6 + 8`).
4. Read data memory at that address.
5. Write the read value into the register (`x5`).

These five jobs are the five stages of the classic RISC-V pipeline.

| Stage | Name | Job |
|:---:|:---|:---|
| `IF` | Instruction Fetch | Fetch the instruction from memory |
| `ID` | Instruction Decode | Interpret + read registers |
| `EX` | Execute | ALU operation (compute, address calc) |
| `MEM` | Memory | Data-memory access (load/store) |
| `WB` | Write Back | Write the result to a register |

This post takes a macro view of what each stage does and which hardware unit handles it. The conflicts between stages (hazards) are covered in part 4.

---

## Why Split into Five Stages

The simplest CPU processes one instruction from start to finish in a single clock — the single-cycle approach. The problem is the clock period. One clock must be long enough to hold all five jobs. Since the clock must accommodate the slowest instruction, clock speed drops.

A pipeline splits these five jobs into stages and places a different instruction in each stage at once. It is like a factory assembly line. Rather than waiting for one product to finish every step, a different product flows through each step.

![Pipeline overlap timing](/assets/img/posts/riscv-cpu-3-pipeline/pipeline-timing.png)

Finishing one instruction still takes five clocks (latency is unchanged). But in steady state, one instruction completes every clock. Throughput becomes fivefold. The clock period only needs to fit the longest single job of the five, so clock speed can rise.

The pipeline's benefit is throughput, not latency. This distinction is the key to understanding pipelines.

---

## The Datapath: Five Stages and Their Hardware Units

Each stage has a dedicated hardware unit. Because each stage uses a different unit, five overlapping instructions do not conflict over resources.

![RISC-V 5-stage pipeline datapath](/assets/img/posts/riscv-cpu-3-pipeline/datapath-5stage.png)

### IF: Fetch the Instruction

- **PC (program counter)**: holds the address of the next instruction to execute.
- **Instruction memory**: reads the 32-bit instruction at the address the PC points to.
- **PC + 4 adder**: computes the next instruction address. Base RISC-V instructions are 4 bytes, so it adds 4 to the PC.

When this stage ends, the 32-bit instruction and `PC+4` are ready.

### ID: Interpret and Read Registers

- **Control/decode**: looks at the opcode and funct fields to decide what operation this is and how to control each unit in later stages.
- **Register file (read)**: as seen in part 2, because `rs1` and `rs2` are at fixed positions, the two source register values are read in parallel with decoding.
- **Immediate generator**: reassembles the scattered immediate bits and sign-extends them.

The register file can be read on one side and written on another. Reads happen in ID, writes in WB.

### EX: Compute

- **ALU (arithmetic-logic unit)**: does the actual computation. Addition, subtraction, logical operations, and comparison happen here.
- **Branch target adder**: computes the destination address of a branch (`PC + offset`).

The ALU's inputs depend on the instruction type. R-type takes two register values; I-type takes a register value and an immediate. That choice is made by control signals generated in ID. Load/store address calculation (`base + offset`) is also handled by the ALU as an addition.

### MEM: Memory Access

- **Data memory**: a load reads a value from the computed address; a store writes a value to that address.

Only loads and stores access memory (the load/store architecture from part 1). Every other instruction does nothing in this stage and passes through. The result of an ALU operation passes straight through this stage to WB.

### WB: Write the Result

- **Result-select MUX**: chooses the value to write to the register — the ALU result (R/I type), or the value read from memory (load). Depending on the instruction, one of the two is selected.
- **Register file (write)**: writes the selected value into the destination register `rd`.

Stores and branches have no result to write to a register, so they write nothing in this stage.

---

## Pipeline Registers: The Boundaries Linking Stages

In the datapath figure, the gray bars between stages are the **pipeline registers** — the essential element that makes a pipeline work.

Each stage works for one clock and must hand its result to the next stage. Pipeline registers handle that handoff. At the rising edge of the clock, each stage's output is stored in the next pipeline register. On the following clock, that value becomes the next stage's input.

```
IF ─[IF/ID]─ ID ─[ID/EX]─ EX ─[EX/MEM]─ MEM ─[MEM/WB]─ WB
    register     register    register       register
```

Without pipeline registers, one stage's result would flow into the next before it settled, and the values would mix. Pipeline registers isolate each stage in time, so five instructions belonging to different clocks advance simultaneously without interfering.

Each pipeline register carries everything the next stage needs. For example, the `ID/EX` register holds the read register values, the immediate, and even the control signals for stages after EX, and passes them to EX. The destination register number `rd` also flows along with the instruction all the way to WB.

---

## One Instruction's Journey

Here is `add x5, x6, x7` passing through the pipeline.

```
IF  : read instruction 0x... at the PC. Compute PC+4.
ID  : decode as R-type add. Read x6, x7. Generate control signals.
EX  : ALU computes x6 + x7.
MEM : (no memory access) pass the result through.
WB  : write the result to x5.
```

For a load `lw x5, 8(x6)`, EX computes the address `x6 + 8`, MEM reads the value at that address, and WB writes it to x5. For a store `sw x7, 8(x6)`, EX computes the address, MEM writes x7 to that address, and WB does nothing.

The important point is that every instruction passes through all five stages regardless of type. Some instructions do nothing in a particular stage, but the stage itself is passed through, not skipped. This is what lets every instruction flow through the pipeline in the same rhythm.

---

## A Problem Still Remaining

So far we assumed instructions are independent. But in real programs, instructions are entangled.

```
add x5, x6, x7    ← computes x5 (WB is the 5th clock)
sub x8, x5, x9    ← uses x5 (ID is the 3rd clock)
```

At the moment the second instruction tries to read `x5` (ID, 3rd clock), the first has not yet written `x5` (WB, 5th clock). This conflict arises precisely because the pipeline overlaps. Such problems are called **hazards**.

Branches are a problem too. Where a branch goes is only settled in EX, but by then the pipeline has already started fetching the following instructions in IF. If it fetched the wrong ones, they must be undone.

How hardware detects and resolves these problems, and how it predicts branches, is the subject of the next part.

---

## Summary

| Item | Detail |
|:---|:---|
| Five stages | IF / ID / EX / MEM / WB |
| IF | PC, instruction memory, PC+4 |
| ID | decode, register read, immediate generation |
| EX | ALU operation, branch target calculation |
| MEM | data memory (load/store) |
| WB | select result, then write to register |
| Pipeline registers | isolate stages so 5 instructions advance at once |
| Benefit | throughput, not latency (one completes per clock) |

The RISC-V pipeline splits processing one instruction into five stages, with a dedicated hardware unit for each. Pipeline registers between stages isolate each instruction in time, so five instructions flow overlapped without conflict. This structure raises throughput. But when instructions depend on one another or a branch intervenes, the pipeline cannot flow smoothly. The next part enters how hardware handles these hazards and how it predicts branches.

Next: RISC-V CPU #4 — Pipeline in depth: hazard handling and branch prediction (upcoming)
