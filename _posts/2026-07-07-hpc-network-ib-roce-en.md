---
layout: post
title: "InfiniBand and RoCE — The Network Foundation of GPU Clusters"
subtitle: "RDMA mechanics, Verbs API, lossless Ethernet, DCQCN, GPUDirect RDMA"
tags: [Network, InfiniBand, RoCE, RDMA, HPC, NCCL, GPU-Cluster]
lang: en
translation-url: /2026-07-07-hpc-network-ib-roce-kr/
readtime: true
mathjax: false
---

## The Physical Limits of GPU Cluster Communication

LLM training synchronizes gradients across all GPUs on every parameter update. The **AllReduce** operation, performed by NCCL or RCCL, moves `2 × (N-1)/N × message_size` of data through the network per execution. Hundreds of GPUs repeat this on every step.

Running this over TCP/IP sockets introduces three compounding bottlenecks.

**Kernel involvement**: every socket call crosses a syscall boundary, triggering a context switch. Interrupt handling burns CPU cycles.

**Memory copies**: GPU memory → PCIe → system DRAM → kernel socket buffer → NIC → network. The reverse path is identical. At minimum two to three memcpy operations occur per transfer.

**Latency**: TCP/IP software processing adds at least 50μs per message on top of wire latency.

In a 128-GPU benchmark, MPI+NCCL+RDMA delivers approximately twice the training throughput of gRPC (TCP).

---

## RDMA: Bypassing the Kernel

**RDMA** (Remote Direct Memory Access) removes the CPU and kernel from the data path entirely.

```
[TCP/IP path]
GPU HBM → PCIe → System DRAM → CPU (TCP stack) → NIC → Network
← Reverse: NIC → DRAM → CPU → DRAM → PCIe → GPU HBM

[RDMA + GPUDirect path]
GPU HBM → PCIe → NIC → Network
← NIC → PCIe → GPU HBM
```

The enabling mechanism is **Memory Registration**. The application calls `ibv_reg_mr()` to register a memory region with the NIC. The registered pages are pinned in physical memory and mapped into the NIC's IOMMU. All subsequent transfers are handled by the NIC directly via DMA. No CPU involvement. No intermediate copy buffers.

---

## InfiniBand

### The Verbs API

RDMA programming is built on **libibverbs**. Unlike socket APIs, the hot path involves no kernel entry.

```
Application
   │
   ├─ ibv_reg_mr()           ← Register memory (once, at init)
   │
   ├─ ibv_post_send(QP, WR)  ← Submit WR (ring buffer write, no syscall)
   │     └─ NIC polls WR → DMA → transmit packet
   │
   └─ ibv_poll_cq(CQ)        ← Poll for completion (busy poll, no interrupt)
```

Three core objects:

| Object | Description |
|:---|:---|
| **QP** (Queue Pair) | Send Queue + Receive Queue pair. Unit of a connection |
| **CQ** (Completion Queue) | Notifies WR completion. SQ and RQ can share one |
| **MR** (Memory Region) | Registered pinned memory. Shared between NIC and app |

Work Request operations:

| Operation | Description | Transport Types |
|:---|:---|:---|
| SEND / RECV | Standard transfer involving both QPs | RC, UC, UD |
| RDMA WRITE | Write to remote memory without receiver CPU involvement | RC, UC |
| RDMA READ | Read from remote memory | RC |
| ATOMIC (CAS/FAA) | Compare-and-Swap, Fetch-and-Add | RC (optional) |

NCCL primarily uses **RDMA WRITE over RC QPs**: reliable transfer with zero receiver-side CPU involvement.

### Transport Types: RC / UC / UD

| | RC | UC | UD |
|:---|:---|:---|:---|
| Full Name | Reliable Connected | Unreliable Connected | Unreliable Datagram |
| Reliability | ACK / retransmit | None | None |
| Connection | 1:1 QP | 1:1 QP | Connectionless (1:N) |
| RDMA READ | Supported | Not supported | Not supported |
| Primary Uses | NCCL AllReduce | Rarely used | MPI control messages, multicast |

### Generations and Bandwidth

| Generation | Bandwidth (4x port) | Deployed |
|:---|:---:|:---:|
| QDR | 40 Gbps | 2008 |
| FDR | 56 Gbps | 2012 |
| EDR | 100 Gbps | 2015 |
| HDR | 200 Gbps | 2019 |
| **NDR** | **400 Gbps** | 2022 |
| XDR | 800 Gbps | 2025 |

The NVIDIA Quantum-2 NDR switch delivers **130ns** port-to-port latency. NDR NIC latency for an 8-byte message is approximately **0.9μs**. MPI application latency on NDR reaches **1–2μs**.

InfiniBand operates as a dedicated fabric. The **Subnet Manager** assigns 16-bit LIDs to all ports in the cluster and computes routing tables. Fat-tree topologies provide multiple paths per source-destination pair, enabling fault tolerance and ECMP load balancing.

---

## RoCE — RDMA over Ethernet

**RoCE** (RDMA over Converged Ethernet) ports the InfiniBand transport layer to run over Ethernet. The libibverbs API is identical.

### v1 vs v2

| | RoCE v1 | RoCE v2 |
|:---|:---:|:---:|
| Transport | L2 Ethernet (Ethertype 0x8915) | **UDP/IP** (port 4791) |
| Routing | Within a VLAN only | **Routable across subnets (L3)** |
| Status | Deprecated | **Current standard** |

RoCE v2 (RRoCE) adds standard IP/UDP headers, enabling integration with existing IP infrastructure.

### Lossless Ethernet: PFC

Unlike TCP, RDMA RC QPs only retransmit after a timeout fires. In large-scale AllReduce, a single packet loss causes the affected QP to stall for tens of milliseconds — and every GPU waits at that synchronization point. Even 0.01% packet loss measurably degrades training throughput.

RoCE eliminates this with **PFC** (Priority Flow Control, IEEE 802.1Qbb).

```
[PFC mechanism]
Node A ──→ Switch Port ──→ Switch Queue ──→ Node B
                                │
                     Buffer threshold reached
                                │
               PAUSE frame sent upstream (to Node A)
                                │
                     (Traffic resumes when congestion clears)
```

RDMA traffic is isolated into Traffic Class 3. Only that TC is paused during congestion; other traffic classes continue unaffected.

PFC's structural problem is **Head-of-Line (HOL) Blocking**: all flows within the same TC are paused together, even uncongested ones. In rare cases, PAUSE frames cycle between switches and cause a PFC Pause Storm — a fabric-wide deadlock.

### DCQCN — Congestion Control

PFC is a last resort. Proactive congestion control is handled by **DCQCN** (Data Center Quantized Congestion Notification), introduced by Zhu et al. at SIGCOMM 2015.

```
[Switch = Congestion Point (CP)]
  Queue depth > threshold
    → Set IP header CE bit (ECN mark)

[Receiver NIC = Notification Point (NP)]
  ECN-marked packet received
    → Generate CNP (Congestion Notification Packet) → send to sender

[Sender NIC = Reaction Point (RP)]
  On CNP reception (multiplicative decrease):
    α(t) = (1 - g) × α(t-1) + g          ← EWMA congestion signal
    Rate_new = Rate_cur × (1 - α / 2)     ← Applied immediately

  When no CNP received (rate recovery):
    Phase 1: binary increase toward half of target rate  ← Fast Recovery
    Phase 2: linear increase thereafter                  ← Additive Increase
```

DCQCN is **rate-based**, unlike TCP's window-based control. The feedback loop from ECN marking to rate reduction operates in microseconds.

---

## GPUDirect RDMA

**GPUDirect RDMA** bypasses system DRAM on the path between GPU HBM and the NIC.

```
[Without GPUDirect RDMA]
GPU HBM → PCIe → System DRAM → CPU memcpy → DRAM → NIC → Network

[With GPUDirect RDMA]
GPU HBM → PCIe → NIC → Network
```

GPU memory BAR (Base Address Register) is mapped directly into PCIe address space, allowing the NIC to DMA directly from and to GPU HBM. At 400Gbps line rate, the memory copy overhead without GPUDirect RDMA accounts for 40% of total network latency.

On NVIDIA GPUs, the `nvidia_peermem.ko` module must be loaded. On AMD GPUs, P2P support is built into the `amdkfd` driver, referred to as **ROCmRDMA**.

NCCL's GPUDirect RDMA level is controlled by `NCCL_NET_GDR_LEVEL`:

| Value | Scope |
|:---|:---|
| `PIX` | GPU-NIC pairs within the same PCIe switch |
| `PHB` | GPU-NIC pairs within the same CPU socket |
| `SYS` | Across NUMA boundaries |

Other key NCCL IB/RoCE environment variables:

| Variable | Description |
|:---|:---|
| `NCCL_IB_HCA` | Which HCAs to use (`=mlx5_0,mlx5_1`) |
| `NCCL_IB_GID_INDEX` | RoCE GID index (check with `ibv_show_gids`) |
| `NCCL_IB_QPS_PER_CONNECTION` | QPs per connection (1–128, improves fat-tree ECMP entropy) |

---

## InfiniBand vs RoCE v2 vs iWARP

| | InfiniBand (NDR) | RoCE v2 | iWARP | TCP/IP |
|:---|:---:|:---:|:---:|:---:|
| App Latency | **1–2μs** | 5–7μs | >3μs | 50μs+ |
| Switch Latency | **130ns** | 230ns | — | High |
| Max Bandwidth | **400Gbps** | 400Gbps | Lower | — |
| Lossless | Hardware built-in | PFC+ECN required | TCP retransmit | None |
| Infrastructure Cost | High | **Low (shared Ethernet)** | Low | Lowest |
| Switch Cost vs IB | Baseline | **49–70% lower** | — | — |

**Choose InfiniBand when**: microsecond tail latency directly affects outcome — tightly coupled HPC simulations, NVIDIA DGX/Base Command deployments.

**Choose RoCE v2 when**: hyperscale deployments (thousands of nodes), reusing existing Ethernet infrastructure, AMD Instinct clusters (Broadcom Thor2 NIC based).

---

## Summary

| | InfiniBand | RoCE v2 |
|:---|:---|:---|
| Transport | Dedicated IB fabric | UDP/IP over Ethernet |
| Lossless | Hardware built-in | PFC + DCQCN configuration required |
| App Latency | 1–2μs | 5–7μs |
| Infrastructure Cost | High | Low |
| Primary Use Cases | HPC, NVIDIA DGX | Large-scale AI clusters, AMD MI |

The essentials of GPU cluster networking: remove the kernel from the data path with RDMA, expose GPU memory directly to the NIC with GPUDirect RDMA, and eliminate packet loss through a lossless fabric.

---

## References

- Zhu et al. *Congestion Control for Large-Scale RDMA Deployments* (DCQCN). ACM SIGCOMM 2015. [DOI](https://dl.acm.org/doi/10.1145/2785956.2787484)
- Hu et al. *RDMA over Ethernet for Distributed AI Training at Meta Scale*. ACM SIGCOMM 2024. [PDF](https://cs.stanford.edu/~keithw/sigcomm2024/sigcomm24-final246-acmpaginated.pdf)
- NVIDIA. *NCCL Documentation: Environment Variables*. [Link](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/env.html)
- NVIDIA. *Scaling Deep Learning Training with NCCL*. NVIDIA Developer Blog. [Link](https://developer.nvidia.com/blog/scaling-deep-learning-training-nccl/)
- Red Hat. *Configuring InfiniBand and RDMA Networks* (RHEL 9). [Link](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/configuring_infiniband_and_rdma_networks/)
- AMD ROCm. *What is RCCL?*. ROCm Documentation. [Link](https://rocm.docs.amd.com/projects/rccl/en/docs-6.4.0/what-is-rccl.html)
- DatenLord. *The Evolution and Implementation of GPUDirect RDMA*. Medium. [Link](https://medium.com/@datenlord/the-evolution-and-implementation-of-gpudirect-rdma-19751f7b9413)
- Wikipedia. *RDMA over Converged Ethernet*. [Link](https://en.wikipedia.org/wiki/RDMA_over_Converged_Ethernet)
