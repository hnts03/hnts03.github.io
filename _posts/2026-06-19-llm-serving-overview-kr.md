---
layout: post
title: "LLM 서빙 프레임워크 개요: vLLM, SGLang, TensorRT-LLM"
subtitle: "세 프레임워크의 설계 철학과 핵심 기술 비교"
tags: [LLM, Inference, vLLM, SGLang, TensorRT-LLM, GPU, AI]
lang: kr
translation-url: /2026-06-19-llm-serving-overview-en/
readtime: true
mathjax: false
---

## 시리즈 로드맵

| # | 주제 |
|:--:|:---|
| **0** | **개요 및 비교 — vLLM, SGLang, TensorRT-LLM** |
| 1 | vLLM 심층 분석 — PagedAttention과 스케줄링 |
| 2 | SGLang 심층 분석 — RadixAttention과 구조화 생성 |
| 3 | TensorRT-LLM 심층 분석 — 컴파일 최적화와 배포 |

---

## 왜 별도의 서빙 프레임워크가 필요한가

LLM 추론은 일반적인 딥러닝 추론과 다른 특성을 가집니다.

**Autoregressive 생성**: 출력 토큰을 한 번에 하나씩 생성합니다. 각 스텝에서 이전 토큰들의 Key-Value(KV)를 재계산하는 대신 캐시해두고 재사용합니다(KV Cache). 이 KV Cache가 메모리 관리의 핵심 병목입니다.

**요청 길이의 불균일성**: 입력 프롬프트와 출력 길이가 요청마다 다릅니다. 정적 배치(Static Batching)로는 짧게 끝난 요청이 가장 긴 요청이 끝날 때까지 GPU를 낭비하며 기다립니다.

**Prefill-Decode 비대칭**: 프롬프트 처리(Prefill)는 compute-bound, 토큰 생성(Decode)은 memory-bound입니다. 두 단계를 어떻게 스케줄링하느냐가 전체 처리량과 지연 시간을 결정합니다.

범용 딥러닝 프레임워크(PyTorch, TensorFlow)는 이 특성들을 최적화하지 않습니다. LLM 서빙 전용 프레임워크가 등장한 이유입니다.

---

## vLLM

> UC Berkeley, 2023. 오픈소스 LLM 서빙의 사실상 표준.

### 핵심 기술: PagedAttention

KV Cache 메모리를 OS의 가상 메모리 페이징 방식으로 관리합니다. 각 요청의 KV Cache를 고정 크기의 물리 블록(block)에 비연속적으로 할당하고, 논리 블록 → 물리 블록 매핑 테이블을 유지합니다.

기존 방식에서는 최대 시퀀스 길이만큼 연속된 메모리를 사전 할당해야 했습니다. 이는 평균 60~80%의 메모리 낭비를 유발했습니다. PagedAttention은 실제 사용한 만큼만 블록을 할당하므로 메모리 낭비를 거의 없애고, 같은 GPU 메모리에서 더 많은 동시 요청을 처리할 수 있습니다.

```
기존 KV Cache 할당
요청 A: [████████████████████████______] (뒤 공간 낭비)
요청 B: [████████████__________________] (뒤 공간 낭비)

PagedAttention
물리 블록: [Block0][Block1][Block2][Block3][Block4]...
요청 A → Block0, Block2, Block4 (비연속, 낭비 없음)
요청 B → Block1, Block3       (비연속, 낭비 없음)
```

Copy-on-Write 방식으로 블록 공유도 가능해 prefix 재사용, 병렬 샘플링(beam search 등)에서도 메모리를 절약합니다.

### Continuous Batching

iteration 단위로 배치를 재구성합니다. 각 forward pass가 끝날 때마다 완료된 시퀀스를 배치에서 제거하고 대기 중인 새 요청을 삽입합니다. GPU 유휴 시간을 최소화해 처리량을 높입니다.

### 주요 특징

- OpenAI API 호환 서버 내장
- 하드웨어: NVIDIA, AMD(ROCm), Google TPU, AWS Inferentia 등 다중 지원
- Multi-LoRA 동시 서빙
- Chunked Prefill, Speculative Decoding 지원
- 활발한 오픈소스 커뮤니티 (가장 많은 기여자)

---

## SGLang

> Stanford, 2024. 복잡한 LLM 프로그램과 prefix 재사용에 특화.

### 핵심 기술: RadixAttention

KV Cache를 Radix Tree로 관리합니다. 공통 prefix를 가진 요청들이 자동으로 캐시를 공유합니다.

```
Radix Tree 예시
"시스템 프롬프트 + 유저A의 대화 이력" → 캐시 히트
"시스템 프롬프트 + 유저B의 대화 이력" → 시스템 프롬프트 부분 캐시 히트
```

Multi-turn 대화, Few-shot 프롬프팅, Agent 루프처럼 공통 prefix가 반복되는 워크로드에서 prefill 비용을 크게 줄입니다. vLLM의 prefix caching이 수동 설정을 요구하는 것과 달리, SGLang은 이를 자동으로 처리합니다.

### Structured Generation

JSON Schema, 정규식, EBNF 문법에 맞는 출력을 고속으로 생성합니다. XGrammar를 사용해 문법 제약 조건을 CUDA 레벨에서 적용하므로, CPU 기반 구현 대비 지연 시간이 크게 낮습니다.

### 주요 특징

- CUDA Graph를 decode에 적극 활용 → GPU kernel 호출 오버헤드 감소
- FlashInfer 커널 통합
- torch.compile 지원
- 하드웨어: NVIDIA, AMD(ROCm) 지원

---

## TensorRT-LLM

> NVIDIA 공식, 2023. 컴파일 시점 최적화로 최대 raw throughput 추구.

### 핵심 기술: TensorRT 엔진 컴파일

모델을 실행 전에 TensorRT 엔진으로 컴파일합니다. 컴파일 과정에서:

- **Kernel Fusion**: 여러 연산(Layer Norm → Linear → Activation)을 단일 CUDA 커널로 합침
- **Layer/Tensor Fusion**: 계산 그래프를 최적화
- **Quantization**: FP8, INT8(SmoothQuant), INT4(AWQ, GPTQ) 등 다양한 양자화를 컴파일 시 적용

런타임에 최적화된 엔진을 그대로 실행하므로 raw throughput이 높습니다.

### In-flight Batching

NVIDIA의 Continuous Batching 구현으로, Triton Inference Server와 통합됩니다.

### 주요 특징

- 다양한 Quantization 지원 (FP8, INT8, INT4)
- Tensor Parallelism, Pipeline Parallelism 내장
- Triton Inference Server와 공식 연동
- 하드웨어: NVIDIA GPU 전용
- 단점: 모델별 TRT-LLM 구현 필요, 엔진 빌드 시간이 김, AMD/기타 GPU 미지원

---

## 비교

| | vLLM | SGLang | TensorRT-LLM |
|:---|:---:|:---:|:---:|
| 출처 | UC Berkeley | Stanford | NVIDIA |
| 핵심 기술 | PagedAttention | RadixAttention | TRT 엔진 컴파일 |
| Prefix Caching | 수동 설정 | 자동 (Radix Tree) | 제한적 |
| Structured Generation | 기본 지원 | 특화 (XGrammar) | 제한적 |
| 하드웨어 | 멀티 벤더 | NVIDIA, AMD | NVIDIA 전용 |
| 배포 난이도 | 낮음 | 낮음 | 높음 (빌드 필요) |
| Raw Throughput | 높음 | 높음 | 최고 (NVIDIA 환경) |
| 적합한 Use Case | 범용 서빙 | Agent, 복잡한 LLM 프로그램 | NVIDIA 프로덕션 배포 |

**선택 기준:**

- **범용 서빙, 멀티 벤더 환경** → vLLM
- **Multi-turn 대화, Agent, Structured Output 비중이 높은 서비스** → SGLang
- **NVIDIA 환경에서 최대 처리량이 목표인 프로덕션** → TensorRT-LLM

---

다음 글에서는 vLLM의 내부 구조 — PagedAttention 구현 방식과 스케줄러 설계 — 를 상세히 다룹니다.

---

*이 포스트의 영문 버전은 상단 언어 스위처를 통해 확인할 수 있습니다.*
