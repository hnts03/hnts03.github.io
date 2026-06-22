---
layout: post
title: "LLM 서빙 프레임워크 #1: vLLM 심층 분석"
subtitle: "다중 프로세스 아키텍처, Scheduler, KVCacheManager, 병렬화 전략 (V1 기준)"
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

[개요 포스트](/2026-06-19-llm-serving-overview-kr/)에서 PagedAttention과 Continuous Batching의 개념을 다뤘습니다. 이번 글에서는 vLLM V1(v0.8.0 이후 default) 내부 구조와 병렬화 전략을 다룹니다.

---

## 1. vLLM이란

**vLLM**은 UC Berkeley에서 2023년 공개한 오픈소스 LLM 서빙 프레임워크입니다. SOSP 2023에서 발표된 PagedAttention 논문을 기반으로 하며, 목표는 단일 GPU 및 분산 환경에서의 LLM 추론 처리량 최대화입니다.

핵심 기여는 세 가지입니다.

- **PagedAttention**: KV Cache 메모리를 OS 페이징 방식으로 관리해 메모리 낭비를 제거
- **Continuous Batching**: 매 iteration마다 완료 요청을 배치에서 제거하고 새 요청을 삽입
- **다중 하드웨어 지원**: NVIDIA, AMD(ROCm), Google TPU, AWS Inferentia

---

## 2. 전체 아키텍처

![vLLM V1 Architecture](/assets/img/posts/llm-serving-1-vllm/arch-overview.png)

V1은 **다중 프로세스 아키텍처**입니다. 역할에 따라 세 종류의 프로세스로 분리됩니다.

```
HTTP 요청
    ↓
[API Server]          ─── FastAPI, OpenAI API 호환
    ↓
[AsyncLLM]            ─── 토크나이징·디토크나이징·스트리밍  (메인 프로세스)
    │  ZMQ 소켓
    ↓
[EngineCore]          ─── 스케줄링·KV 관리 루프           (별도 프로세스)
    ├── [Scheduler]           ─── 요청 스케줄링, 선점 결정
    │       └── [KVCacheManager]  ─── KV Cache 블록 할당·해제
    └── [MultiprocExecutor]
            └── [GPUWorker × N]   ─── GPU당 별도 프로세스
                    └── [GPUModelRunner]  ─── 모델 forward pass
```

**V0과의 가장 큰 차이**는 `EngineCore`가 별도 프로세스로 분리된 점입니다. `AsyncLLM`과 `EngineCore`는 ZMQ 소켓으로 통신하며, Python GIL 제약 없이 각각의 루프를 독립적으로 실행합니다.

---

## 3. Frontend

### API Server

`vllm.entrypoints.openai.api_server`가 FastAPI 기반 HTTP 서버를 구동합니다. `/v1/chat/completions`, `/v1/completions` 엔드포인트가 OpenAI API 스펙을 그대로 구현하므로 기존 OpenAI SDK를 변경 없이 사용할 수 있습니다.

### AsyncLLM

`AsyncLLM`(`vllm/v1/engine/async_llm.py`)은 V1의 비동기 진입점입니다. 역할은 세 가지입니다.

1. 동시 요청을 받아 토크나이징 후 `EngineCore`로 전달
2. `EngineCore`로부터 출력 토큰을 받아 디토크나이징
3. `AsyncGenerator`로 클라이언트에 토큰 스트리밍

`EngineCore`는 별도 프로세스(`EngineCoreProc`)로 실행되며, `AsyncLLM`은 `EngineCoreClient`를 통해 ZMQ로 요청을 전달하고 출력을 수신합니다. 입출력 처리와 스케줄링 루프가 분리되므로 하나가 지연되더라도 다른 쪽에 영향을 주지 않습니다.

---

## 4. Scheduler와 KVCacheManager

### Scheduler

`Scheduler`(`vllm/v1/core/sched/scheduler.py`)는 두 개의 큐를 관리합니다.

```
waiting  ─── 아직 처리 시작 전 요청
running  ─── 현재 GPU에서 실행 중인 요청
```

V1에서 **Swap 선점은 제거됐습니다.** 선점 발생 시 `KVCacheManager`가 해당 요청의 블록을 해제하고, 요청은 `waiting` 큐로 돌아가 **Recompute(재계산)** 방식으로 prefill을 다시 수행합니다.

**Chunked Prefill**은 V1에서 **항상 활성화**됩니다. 긴 프롬프트를 `max_num_batched_tokens` 단위 청크로 나눠 decode 요청과 함께 배치합니다. decode 요청이 prefill로 인해 차단되는 현상을 방지하고, TTFT와 TPOT 간 균형을 조정합니다.

### KVCacheManager

**KVCacheManager**(`vllm/v1/core/kv_cache_manager.py`)는 PagedAttention의 메모리 관리자입니다. V0의 `BlockSpaceManager`에 해당합니다.

```
논리 블록(Logical Block)  ──→  물리 블록(Physical Block)
  [req A: block 0]        ──→  [GPU block #42]
  [req A: block 1]        ──→  [GPU block #7 ]
  [req B: block 0]        ──→  [GPU block #42]  ← prefix 공유
```

주요 동작은 다음과 같습니다.

- `allocate_slots()`: 실행 중인 요청에 새 토큰 슬롯 할당
- `free()` / `free_slots()`: 완료 요청의 블록 반환
- **해시 기반 prefix 캐싱**: 블록 내용의 해시로 동일 prefix를 감지해 자동 재사용. V1에서 기본 활성화.

내부적으로 `KVCacheCoordinator`가 어텐션 레이어 타입별 `SingleTypeKVCacheManager`를 조율해 이기종 어텐션(예: 일부 레이어는 슬라이딩 윈도우, 일부는 전체 어텐션)에 대응합니다.

---

## 5. Worker

### MultiprocExecutor

V1에서 Worker 조율은 `MultiprocExecutor`가 담당합니다. TP/PP 설정에 따라 필요한 수의 `GPUWorker` 프로세스를 생성하고, 각 프로세스에 실행 명령을 브로드캐스트합니다.

### GPUWorker

`GPUWorker`(`vllm/v1/worker/gpu_worker.py`)는 하나의 GPU rank에 대응하는 프로세스입니다. 초기화 단계에서 모델 가중치를 로드하고, TP/PP 설정에 따라 가중치를 분할합니다. `EngineCore`가 결정한 KV Cache 텐서를 `bind_kv_cache()`로 전달받아 `GPUModelRunner`에 바인딩합니다.

### GPUModelRunner

`GPUModelRunner`(`vllm/v1/worker/gpu_model_runner.py`)가 실제 forward pass를 담당합니다. 실행 순서는 다음과 같습니다.

1. **입력 준비**: token IDs, position IDs, attention metadata (block table, context lengths) 구성
2. **CUDA Graph 또는 eager 실행**: decode phase에서 batch size가 작고 고정적이면 CUDA Graph로 kernel launch overhead 제거
3. **모델 forward**: attention → FFN → LayerNorm 순으로 레이어 통과
4. **샘플링**: logits에서 temperature, top-p, top-k 적용해 다음 토큰 선택

KV Cache 텐서는 `EngineCore`가 시작 시 프로파일링을 통해 가용 GPU 메모리를 측정한 후 레이어별로 일괄 할당합니다. `GPUModelRunner`는 이를 `bind_kv_cache()`로 바인딩해 forward pass 중 직접 접근합니다. V0의 `CacheEngine`(swap\_in/swap\_out)은 V1에서 제거됐으며, Recompute 전략으로 대체됐습니다.

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
| `AsyncLLM` | 비동기 요청 관리, 토크나이징·스트리밍 (메인 프로세스) |
| `EngineCore` | 스케줄링·KV 관리 루프 (별도 프로세스, ZMQ) |
| `Scheduler` | 2큐(waiting/running), Recompute 선점, Chunked Prefill |
| `KVCacheManager` | PagedAttention 블록 할당·해제, 해시 기반 prefix 캐싱 |
| `MultiprocExecutor` | GPUWorker 조율, 실행 브로드캐스트 |
| `GPUWorker` / `GPUModelRunner` | GPU forward pass 실행, KV Cache 바인딩 |
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
