---
layout: post
title: "LLM 서빙 프레임워크 #1: vLLM 심층 분석"
subtitle: "Frontend·Scheduler·Executor·Worker 구조와 병렬화 전략"
tags: [LLM, Inference, vLLM, PagedAttention, GPU, AI, Parallelism]
lang: kr
translation-url: /2026-06-22-llm-serving-1-vllm-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 | 상태 |
|:--:|:---|:---:|
| 0 | [개요 및 비교 — vLLM, SGLang, TensorRT-LLM](/2026-06-19-llm-serving-overview-kr/) | ✅ |
| **1** | **vLLM 심층 분석** | |
| 2 | SGLang 심층 분석 | |
| 3 | TensorRT-LLM 심층 분석 | |

[개요 포스트](/2026-06-19-llm-serving-overview-kr/)에서 PagedAttention과 Continuous Batching의 개념을 다뤘습니다. 이번 글에서는 vLLM 내부 구조 — Frontend, Scheduler, Executor, Worker — 와 병렬화 전략을 다룹니다.

---

## 1. vLLM이란

**vLLM**은 UC Berkeley에서 2023년 공개한 오픈소스 LLM 서빙 프레임워크입니다. SOSP 2023에서 발표된 PagedAttention 논문을 기반으로 하며, 목표는 단일 GPU 및 분산 환경에서의 LLM 추론 처리량 최대화입니다.

핵심 기여는 세 가지입니다.

- **PagedAttention**: KV Cache 메모리를 OS 페이징 방식으로 관리해 메모리 낭비를 제거
- **Continuous Batching**: 매 iteration마다 완료 요청을 배치에서 제거하고 새 요청을 삽입
- **다중 하드웨어 지원**: NVIDIA, AMD(ROCm), Google TPU, AWS Inferentia

---

## 2. 전체 아키텍처

![vLLM Architecture](/assets/img/posts/llm-serving-1-vllm/arch-overview.png)

요청이 처리되는 흐름은 다음과 같습니다.

```
HTTP 요청
    ↓
[API Server]  ─── FastAPI, OpenAI API 호환
    ↓
[AsyncLLMEngine]  ─── 비동기 요청 큐 관리
    ↓
[LLMEngine]
    ├── [Scheduler]         ─── 요청 스케줄링, 선점 결정
    │       └── [BlockSpaceManager]  ─── KV Cache 블록 할당
    └── [ExecutorBase]
            └── [Worker × N GPU]
                    ├── [ModelRunner]   ─── 모델 forward pass
                    └── [CacheEngine]  ─── KV Cache 초기화·이동
```

---

## 3. Frontend

### API Server

`vllm.entrypoints.openai.api_server`가 FastAPI 기반 HTTP 서버를 구동합니다. `/v1/chat/completions`, `/v1/completions` 엔드포인트가 OpenAI API 스펙을 그대로 구현하므로 기존 OpenAI SDK를 변경 없이 사용할 수 있습니다.

### AsyncLLMEngine

`AsyncLLMEngine`은 `LLMEngine`의 비동기 래퍼입니다. 역할은 두 가지입니다.

1. 동시 요청을 받아 내부 큐에 적재
2. 백그라운드 루프에서 `LLMEngine.step()`을 반복 호출해 스케줄링·실행 루프를 돌림

각 요청은 고유 `request_id`를 부여받고, 생성된 토큰은 `AsyncGenerator`로 스트리밍됩니다.

---

## 4. Scheduler와 BlockSpaceManager

### Scheduler

`Scheduler`는 세 개의 큐를 관리합니다.

```
waiting  ─── 아직 처리 시작 전 요청
running  ─── 현재 GPU에서 실행 중인 요청
swapped  ─── 선점당해 KV Cache가 CPU로 이동된 요청
```

매 `step()`마다 스케줄러는 다음을 결정합니다.

- `running` 큐 중 실행할 요청 선택 (FCFS 기본)
- KV Cache 블록이 부족하면 실행 중인 요청을 **선점(preemption)**

**선점 정책**은 두 가지입니다.

| 정책 | 방법 | 비용 |
|:---|:---|:---|
| **Swap** | KV Cache를 CPU RAM으로 이동, 나중에 복원 | swap I/O 비용 |
| **Recompute** | KV Cache 삭제, 나중에 prefill 재수행 | 재계산 비용 |

기본값은 Recompute입니다. 시퀀스가 짧을수록 재계산이 더 저렴하고, 길수록 Swap이 유리합니다.

**Chunked Prefill**은 긴 프롬프트를 `max_num_batched_tokens` 단위 청크로 나눠 decode 요청과 함께 배치합니다. prefill이 decode iteration을 완전히 차단하던 문제를 해결해 TTFT(Time To First Token)와 TPOT(Time Per Output Token) 간 트레이드오프를 조정할 수 있습니다.

### BlockSpaceManager

**BlockSpaceManager**는 PagedAttention의 메모리 관리자입니다.

```
논리 블록(Logical Block)  ──→  물리 블록(Physical Block)
  [seq 0: block 0]        ──→  [GPU block #42]
  [seq 0: block 1]        ──→  [GPU block #7 ]
  [seq 1: block 0]        ──→  [GPU block #42]  ← 공유 (prefix 동일)
```

주요 동작은 다음과 같습니다.

- `allocate()`: 새 요청에 물리 블록 할당
- `free()`: 완료 요청의 블록 반환
- `fork()`: prefix 공유 시 블록 ref_count 증가 (Copy-on-Write)
- `can_allocate()`: 스케줄러가 새 요청 수락 가능 여부 판단에 사용

---

## 5. Executor와 Worker

### ExecutorBase

`ExecutorBase`는 Worker들을 추상화하는 레이어입니다. 실행 환경에 따라 세 가지 구현체가 있습니다.

| 구현체 | 대상 환경 |
|:---|:---|
| `GPUExecutor` | 단일 GPU |
| `MultiprocessingGPUExecutor` | 단일 노드, 다중 GPU |
| `RayGPUExecutor` | 다중 노드 (Ray 클러스터) |

`execute_model()`을 호출하면 Executor가 각 Worker에 동일한 명령을 브로드캐스트합니다. TP/PP가 설정된 경우 Worker들은 NCCL을 통해 서로 통신하며 실행합니다.

### Worker

`Worker`는 하나의 GPU rank에 대응하는 프로세스입니다. 초기화 단계에서 모델 가중치를 로드하고, TP/PP 설정에 따라 가중치를 분할합니다.

### ModelRunner

`ModelRunner`는 실제 forward pass를 담당합니다. `execute_model()` 호출 시 다음 순서로 실행됩니다.

1. **입력 준비**: token IDs, position IDs, attention metadata (block table, context lengths) 구성
2. **CUDA Graph 실행 또는 eager 실행**: decode phase에서 batch size가 작고 고정적이면 CUDA Graph로 kernel launch overhead 제거
3. **모델 forward**: attention → FFN → LayerNorm 순으로 레이어 통과
4. **샘플링**: logits에서 temperature, top-p, top-k 적용해 다음 토큰 선택

### CacheEngine

`CacheEngine`은 GPU KV Cache 텐서를 관리합니다.

- `allocate_gpu_cache()`: 시작 시 레이어별 KV Cache 텐서 일괄 할당
- `swap_in(blocks)` / `swap_out(blocks)`: 선점 시 CPU↔GPU KV Cache 이동
- `copy(src, dst)`: Copy-on-Write 시 블록 복사

---

## 6. Transfer Layer

### 분산 Worker 간 통신 (NCCL)

TP, PP가 활성화되면 Worker들은 NCCL을 통해 통신합니다.

| 병렬화 | 통신 연산 | 발생 시점 |
|:---|:---|:---|
| Tensor Parallel | `all_reduce` | attention + FFN 레이어마다 |
| Pipeline Parallel | `send` / `recv` (P2P) | 스테이지 경계마다 |
| Expert Parallel | `all_to_all` | MoE 토큰 라우팅 시 |

### Disaggregated Prefill (P/D 분리)

**Disaggregated Prefill**은 prefill 연산과 decode 연산을 별도 인스턴스로 분리하는 서빙 아키텍처입니다.

```
Prefill Instance                Decode Instance
─────────────────               ─────────────────
prompt → prefill 연산           KV Cache 수신
KV Cache 생성         ──────→   decode 반복 실행
                   KV Transfer  토큰 생성·반환
```

prefill은 compute-bound, decode는 memory-bandwidth-bound이므로 두 단계에 최적화된 하드웨어나 설정을 분리 적용할 수 있습니다.

vLLM은 `KVConnector` 인터페이스로 이 전송 레이어를 추상화합니다. Mooncake, nixl 등의 구현체가 존재하며, 커스텀 커넥터를 작성해 연결하는 것도 가능합니다.

---

## 7. 지원 병렬화

### Tensor Parallelism

![Tensor Parallelism Layout](/assets/img/posts/llm-serving-1-vllm/tp-layout.png)

**Tensor Parallelism(TP)**은 하나의 레이어 연산을 여러 GPU에 분산합니다.

- **Attention**: Q/K/V projection을 head 단위로 분할 (`ColumnParallelLinear`). 각 GPU가 담당 head의 attention을 계산하고 `all_reduce`로 합산.
- **FFN**: up-projection은 column parallel, down-projection은 row parallel. 마찬가지로 `all_reduce`.

매 레이어마다 `all_reduce`가 발생하므로 통신 대역폭이 중요합니다. **동일 노드 내 NVLink 연결 GPU에서 사용하는 것을 권장합니다.** 노드 간 InfiniBand로도 동작하지만 통신 overhead가 커집니다.

```python
# 설정 예시
vllm serve meta-llama/Llama-3-70B \
  --tensor-parallel-size 4
```

### Pipeline Parallelism

![Pipeline Parallelism Schedule](/assets/img/posts/llm-serving-1-vllm/pp-schedule.png)

**Pipeline Parallelism(PP)**은 Transformer 레이어를 스테이지로 분할해 각 GPU에 할당합니다.

```
Stage 0 (Layer 0-7)   → Stage 1 (Layer 8-15) → Stage 2 (Layer 16-23) → Stage 3 (Layer 24-31)
       ↓ activation            ↓ activation           ↓ activation
     send/recv               send/recv              send/recv
```

스테이지 간 activation을 NCCL P2P (`send`/`recv`)로 전달합니다. 위 다이어그램처럼 여러 micro-batch를 파이프라인에 흘려 스테이지 유휴 시간(**pipeline bubble**)을 줄입니다.

PP는 주로 **다중 노드 환경**에서 TP와 함께 사용합니다. 예를 들어 2노드 × 8GPU 환경에서 `TP=8, PP=2` 설정이 일반적입니다.

```python
vllm serve meta-llama/Llama-3-70B \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 2
```

### Expert Parallelism

**Expert Parallelism(EP)**은 MoE(Mixture of Experts) 모델에서 expert를 여러 GPU에 분산합니다.

```
토큰 → Top-K 라우터 → all_to_all 통신 → 담당 GPU의 expert 실행 → all_to_all 복귀
```

DeepSeek-V2, Mixtral 같은 MoE 모델에서 expert 수가 수십~수백 개에 달하므로, 모든 expert를 단일 GPU에 적재하는 것은 불가능합니다. EP는 각 GPU가 일부 expert만 보유하고, `all_to_all` 통신으로 토큰을 담당 expert GPU로 라우팅합니다.

```python
vllm serve deepseek-ai/DeepSeek-V2 \
  --tensor-parallel-size 4 \
  --expert-parallel-size 8
```

### Sequence Parallelism

**Sequence Parallelism(SP)**은 긴 컨텍스트 추론 시 attention 연산을 시퀀스 차원으로 분산합니다. vLLM은 Ulysses 방식의 SP를 부분 지원합니다. 각 GPU가 시퀀스의 일부를 담당하고 `all_to_all`로 Q/K/V를 교환합니다.

---

## 정리

| 구성요소 | 역할 |
|:---|:---|
| `AsyncLLMEngine` | 비동기 요청 관리, 스트리밍 출력 |
| `Scheduler` | FCFS + 선점, Chunked Prefill 스케줄링 |
| `BlockSpaceManager` | PagedAttention 물리 블록 할당·해제 |
| `ExecutorBase` | Worker 추상화, 실행 브로드캐스트 |
| `Worker` / `ModelRunner` | GPU forward pass 실행 |
| `CacheEngine` | KV Cache 할당·swap |
| NCCL 통신 | TP all_reduce, PP send/recv, EP all_to_all |
| `KVConnector` | Disaggregated Prefill KV Cache 전송 |

| 병렬화 | 분할 단위 | 통신 | 권장 환경 |
|:---|:---|:---|:---|
| TP | 레이어 내 (head/weight) | all_reduce | 동일 노드 NVLink |
| PP | 레이어 간 (stage) | send/recv | 다중 노드 |
| EP | Expert | all_to_all | MoE 모델 |
| SP | 시퀀스 | all_to_all | 장문 컨텍스트 |

---

다음 글에서는 SGLang의 내부 구조 — RadixAttention 구현과 CUDA Graph 최적화 — 를 다룹니다.

---

*이 포스트의 영문 버전은 상단 언어 스위처를 통해 확인할 수 있습니다.*
