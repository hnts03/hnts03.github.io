---
layout: post
title: "RISC-V CPU #1: What Is RISC-V?"
subtitle: "The ISA as a contract, the RISC philosophy, and RISC-V as an open ISA"
tags: [CPU, RISC-V, Architecture, Computer-Architecture]
lang: en
translation-url: /2026-07-19-riscv-cpu-1-intro-kr/
readtime: true
mathjax: false
---

## Series Roadmap

This series builds up how a CPU executes instructions, from the ground up, using RISC-V as the reference.

| # | Topic | Status |
|:--:|:---|:---:|
| 1 | What is RISC-V? | ✅ |
| 2 | What is an instruction: encoding and formats | 🔲 |
| 3 | The macro pipeline and each unit's hardware structure | 🔲 |
| 4 | Pipeline in depth: hazard handling and branch prediction | 🔲 |
| 5 | Summary, advanced microarchitecture, other CPU architectures | 🔲 |

---

## The ISA: A Contract Between Hardware and Software

To understand a CPU, you first need to understand the **ISA (Instruction Set Architecture)**. The ISA is the contract between hardware and software.

![The ISA is a contract between hardware and software](/assets/img/posts/riscv-cpu-1-intro/isa-contract.png)

Software uses only the instructions the ISA defines. Hardware must simply execute those instructions, by whatever means. Because this contract stays stable, hardware implementations can change without changing the software.

It helps to separate what the ISA specifies from what it does not.

| Specified by the ISA (architecture) | Not specified (microarchitecture) |
|:---|:---|
| Instruction types and encoding | Number of pipeline stages |
| Register count and width | Cache size and structure |
| Memory addressing modes | Branch prediction scheme |
| Exception/interrupt behavior | Clock speed, number of execution units |

The ISA defines what `add`, `ld`, and `beq` do. Whether those instructions are processed by a 5-stage pipeline or out-of-order execution is the hardware designer's freedom. The pipeline covered in parts 3 and 4 of this series belongs to the latter — the **microarchitecture**.

---

## RISC and CISC: Two Design Philosophies

ISA design has two opposing philosophies: **CISC (Complex Instruction Set Computer)** and **RISC (Reduced Instruction Set Computer)**.

In CISC, a single instruction performs a complex task. x86 is the classic example. Reading a value from memory, computing on it, and writing it back can be done in one instruction. Instruction length is also variable (1 to 15 bytes).

RISC is the opposite. It keeps instructions simple and handles complex tasks through combinations of simple instructions.

| Item | CISC (x86) | RISC (RISC-V) |
|:---|:---|:---|
| Instruction complexity | Complex (multi-step) | Simple (one task) |
| Instruction length | Variable (1–15 bytes) | Fixed (4 bytes, 2 when compressed) |
| Memory access | Most instructions | load/store only |
| Register count | Few (x86-64: 16) | Many (32) |
| Decoding | Complex | Simple |

RISC's core principle is the **load/store architecture**. The only instructions that touch memory are `load` (read) and `store` (write). Every other operation computes on registers alone. To add a value in memory, you first `load` it into a register, add, then `store` it back.

Why is this constraint a benefit? Simple, fixed-length instructions are easy to decode. Easy decoding makes it favorable to overlap instruction execution in a pipeline. RISC's simplicity is not an end in itself but a foundation for fast pipelined execution. Part 3 makes this connection concrete.

---

## The Arrival of RISC-V: An Open ISA

**RISC-V** is an open ISA that began at UC Berkeley in 2010. What fundamentally sets it apart from existing ISAs is ownership.

x86 is owned by Intel and AMD; Arm by Arm Ltd. Building chips with those ISAs requires a license. RISC-V is an open standard. Anyone can design and manufacture RISC-V-based processors with no license fee.

The problem RISC-V solved was fragmentation. Earlier open ISAs used in education and research (such as MIPS) carried commercial constraints or dated design corners. RISC-V was designed cleanly from scratch, reflecting 40 years of ISA design lessons, with no legacy-compatibility burden.

RISC-V's design goals reduce to three:

- **Openness**: free to use with no license
- **Simplicity**: one ISA scaling from education to servers
- **Modularity**: implement only the features you need

---

## RISC-V's Structure: A Modular ISA

RISC-V's defining trait is its **modular structure**. Rather than one huge instruction set, it uses a small base with optionally attached extensions.

![RISC-V modular ISA structure](/assets/img/posts/riscv-cpu-1-intro/modular-isa.png)

The **base integer instruction set** is the foundation.

- `RV32I`: 32-bit integer base. 32 registers, each 32 bits.
- `RV64I`: 64-bit integer base. 32 registers, each 64 bits.

The base set is tiny — about 47 instructions. Integer operations, load/store, branches, and jumps are all of it. That alone can run a complete program.

Onto this, you attach **extensions**.

| Extension | Function |
|:---|:---|
| `M` | Multiply, divide |
| `A` | Atomic operations (synchronization) |
| `F` | Single-precision floating point |
| `D` | Double-precision floating point |
| `C` | Compressed instructions (16-bit, code-size savings) |
| `V` | Vector (SIMD) |

Combining extensions forms a name. `RV64GC` means `RV64I + M + A + F + D + C` (`G` is shorthand for the `IMAFD` bundle). An embedded microcontroller stays small like `RV32IMC`; a server processor grows large, adding vectors on top of `RV64GC`. The same ISA family scales freely.

---

## The RV32I Base: Registers and the PC

This series uses `RV32I` (the 32-bit integer base) as its reference — the simplest yet complete set for explaining a pipeline.

RV32I's state consists of a register file and a program counter.

```
RV32I register file (32 registers, 32 bits each):
┌──────┬─────────┬────────────────────────────────┐
│ x0   │ zero    │ always 0 (writes ignored)      │
│ x1   │ ra      │ return address                 │
│ x2   │ sp      │ stack pointer                  │
│ x3   │ gp      │ global pointer                 │
│ x4   │ tp      │ thread pointer                 │
│ x5-7 │ t0-t2   │ temporaries                    │
│ x8-9 │ s0-s1   │ saved registers                │
│x10-17│ a0-a7   │ function arguments / returns   │
│x18-27│ s2-s11  │ saved registers                │
│x28-31│ t3-t6   │ temporaries                    │
└──────┴─────────┴────────────────────────────────┘
        + PC (Program Counter): address of the next instruction
```

Note that **`x0` is always 0**. Whatever you write to `x0`, its value stays 0. This design saves instructions. For example, no separate `mov` instruction is needed to copy a value: `add x5, x6, x0` (x6 + 0) is a copy. Comparison with zero, a no-op (nop), and more are all expressed via `x0`.

The register names `x0`–`x31` are hardware numbers. Names like `zero`, `ra`, and `sp` are role-based aliases set by the software calling convention. The hardware knows only the numbers; role distinctions belong to the compiler and the convention.

The program counter **PC** holds the memory address of the next instruction to execute. Each time an instruction runs, the PC moves to the next one. Branches and jumps are the instructions that change this PC.

---

## Why RISC-V Became a Standard

RISC-V quickly became a standard across three domains: education, research, and industry.

- **Education**: a clean, simple ISA is ideal for teaching computer architecture. It replaced the teaching-standard role MIPS once held.
- **Research**: being an open ISA, new hardware ideas can be freely implemented and validated. Custom extensions can be defined too.
- **Industry**: no license fees, and scalable to the needed size. Adoption is spreading from embedded microcontrollers to the control cores of datacenter accelerators.

This series chose RISC-V for the same reason. Because its instructions are simple and regular, it can show how a CPU actually executes instructions without clutter.

---

## Summary

| Item | Detail |
|:---|:---|
| ISA | The hardware-software contract. Defines what is executed |
| Microarchitecture | The implementation of how the ISA is executed (pipelines, etc.) |
| RISC philosophy | Simple fixed-length instructions, load/store, many registers |
| RISC-V | Open ISA, modular (base + extensions) |
| Base set | RV32I / RV64I (integer, 32 registers) |
| x0 | A special register that is always 0 |

RISC-V defines the ISA — the hardware-software contract — in a modular way, layering extensions onto a simple base. The RISC philosophy's simplicity is a foundation for fast pipelined execution. The next part looks at the smallest unit of this contract: the instruction itself. We examine how an instruction is encoded as a bit pattern, and why RISC-V organizes this into a small set of fixed formats.

Next: RISC-V CPU #2 — What is an instruction: encoding and formats (upcoming)
