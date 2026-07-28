---
layout: post
title: "지식 베이스 구축: Cerebras 사례와 실전 목업"
subtitle: "데이터를 옮기지 않고 연결하는 접근, 그리고 프롬프트로 테스트한 KB 파이프라인 제안"
tags: [AI, LLM, RAG, Knowledge-Base]
lang: kr
translation-url: /2026-07-28-knowledge-base-en/
readtime: true
mathjax: false
---

Cerebras가 사내 지식 베이스 구축기를 공개했습니다. 그 접근은 데이터를 한곳으로 이관하는 대신 데이터가 있는 자리에서 연결하는 방식입니다. 이 글은 그 접근을 원문에 근거해 정리한 뒤, 개인이나 소규모 팀이 그대로 따라 할 수 있는 KB 구축 시퀀스를 프롬프트로 직접 테스트해 목업으로 제안합니다.

## 출처에 관하여

이 요약은 Cerebras 원문(`cerebras.ai/blog/how-we-built-our-knowledge-base`)을 직접 확보해 정리한 것입니다. 아래 서술은 원문이 밝힌 내용만 반영합니다. 원문이 명시한 구성 임계값과 도구 이름은 그대로 옮기고, 원문에 없는 항목(플래너·합성 LLM, 임베딩, 리랭커 모델의 이름 등)은 공백으로 표시합니다.

---

## Cerebras의 접근

**동기**는 명확합니다. 모든 정보를 한 플랫폼에 기록하는 "단일 진실 소스(single source of truth)"는 실무에서 거의 작동하지 않습니다. 정보는 편리하고 손에 맞는 자리에서 생성됩니다. 문서의 편집 제안, Slack 스레드, GitHub의 코드 참조, Jira의 상태 메타데이터가 그 예입니다. 각 플랫폼은 자기 도메인에 최적화되어 있어 강제 이관은 사용성을 무너뜨립니다. 그래서 Cerebras는 기존 행동을 최소한으로만 바꾸는 시스템을 목표로, 각 플랫폼에서 데이터를 직접 추출하는 방식(meet data where it lives)을 택했습니다. 이 사내 도구의 이름은 `Cerebras Knowledge`입니다.

**규모**는 하루 15,000건 이상의 질의입니다. 사용자는 사람, 자동화, 에이전트 세 부류입니다. 사내 전용이며, 출시 약 3개월 만에 가장 널리 쓰이는 사내 도구의 하나가 됐습니다.

지식 베이스는 세 가지를 제공합니다. 사내 데이터를 수집하고 저장하는 플랫폼, 그 데이터를 질의하는 플랫폼, 그리고 인증과 인가에 감사와 분석을 더한 계층입니다.

아키텍처의 핵심은 모든 소스가 하나로 수렴하는 지점입니다. 원문은 이를 "임베딩, 원문 요약, 메타데이터를 담는 단일 Postgres 테이블"로 서술합니다. Slack 스레드부터 넷리스트까지 모든 소스가 같은 임베딩 테이블에 적재되고, 그 테이블은 동일한 인터페이스로 즉시 질의됩니다. 소스마다 "무엇을, 어떻게 연결하고, 얼마나 자주 가져올지"를 각자 정의하는 per-source 커넥터가 앞단에 붙습니다. 이 글에서는 이 수렴 구조를 **narrow waist**로 부릅니다.

```
  많은 소스                    좁은 허리(narrow waist)                단일 질의
 Slack 스레드   ─┐
 GitHub 코드    ─┤   per-source     공통 스키마 행         단일 Postgres
 Google Docs   ─┼─►  커넥터    ─►  (embedding +      ─►   테이블 (embedding    ─► 단일 인터페이스
 Jira 메타데이터 ─┘  (정규화)        summary + meta)        저장) + FTS
```

**Slack 처리**가 가장 중요한 설계 대상이었습니다. 최신 엔지니어링 논의가 이곳에서 일어나기 때문입니다. `Socket Mode`(WebSocket)로 모든 메시지 이벤트를 실시간 수신해 폴링 없이 갱신을 받습니다. 이벤트가 도착하면 즉시 확인 응답을 보내고 안정적 event ID로 중복을 제거합니다. 수집 소비자는 개별 메시지를 따로 저장하지 않고, 그 메시지가 속한 스레드 전체(부모와 모든 답글)를 다시 가져와 한 행으로 저장합니다. Slack 채널마다 별도 데이터 소스를 두어 채널별로 수집 주기를 조정합니다.

원본 텍스트는 적재 즉시 Postgres 전문검색(GIN 인덱스)으로 키워드 검색이 가능합니다. 벡터 검색을 위해서는 추가 처리를 거칩니다. LLM이 스레드 전체에서 구조화 데이터를 추출합니다. 엔지니어가 실제로 검색할 법한 한 줄 질문, 짧은 요약, 해결책, 언급된 시스템과 코드 참조입니다. 이 항목들을 임베딩해 공유 테이블에 기록하고, 원본 전사는 직접 임베딩하지 않습니다. 스레드를 일관된 형식으로 정규화했을 때 정확도가 크게 올랐습니다.

긴 스레드 안의 중요한 개별 메시지가 스레드 요약에 반영되지 않는 문제를 위해 **bursting**을 씁니다. burst는 같은 작성자의 연속 메시지 묶음입니다. 스레드 주제를 컨텍스트로 앞에 붙여 개별 burst를 임베딩합니다. 저품질 데이터를 막기 위해 각 burst는 임베딩 전에 임계값을 통과해야 합니다. 코퍼스 기준 희소 토큰을 포함해 IDF가 4.0 이상일 것, 묶음 길이가 200자 이상일 것, 하나 이상의 메시지에 리액션이 있을 것입니다.

**코드 인덱싱**은 오픈소스 `CocoIndex`를 사용합니다. 40GB가 넘는 리포도 언어별 정규식 경계로 coarse에서 fine으로 분할합니다. 먼저 클래스 같은 상위 경계를 시도하고, 청크가 여전히 크면 메서드, 더 작은 블록 순으로 내려갑니다. 한 파일이 파일 수준과 함수 수준처럼 여러 특이도의 임베딩을 만들 수 있습니다. CocoIndex는 동기화 메타데이터를 Postgres에 두고, 커밋마다 변경된 청크만 재임베딩하고 재반영하는 증분 방식입니다.

커스텀 소스는 플러그인 스크립트로 다룹니다. 팀이 자기 시스템을 읽어 공용 임베딩 테이블과 같은 형태의 행을 내보내는 작은 Python 모듈을 PR로 제출하면, 나머지 스택은 그대로 동작합니다.

**검색과 랭킹**은 네 신호를 융합합니다.

- 전문검색: 정확 토큰 일치(에러 문자열, 플래그명, 호스트명)
- 임베딩: 패러프레이즈 대응
- IDF: 신호와 잡음 분리
- age decay: 오래된 답 강등

질의 처리는 다음 순서입니다. Planner LLM이 질의와 활성 프로젝트를 보고 도구를 선택하고, Executor가 병렬로 팬아웃해 결과를 공통 증거 스키마로 정규화한 뒤, 최종 LLM이 인용과 함께 답을 합성합니다. 사용 가능한 도구에는 `search`(통합 벡터 파이프라인), `search_slack`, `search_code`(리포에 대한 ripgrep), `subsystem_index`(파일별 LLM 요약), `recent_prs`, `who_knows`가 있습니다.

재랭킹은 서로 다른 검색기의 결과 목록을 reciprocal rank fusion(RRF)으로 먼저 합칩니다. 각 문서에 대해 그 문서가 등장한 목록마다 `weight / (60 + rank)`를 더합니다. 기본 가중치는 1.0, 평활 상수는 60입니다. 이후 중복 청크를 원본 단위로 병합하고 파일당 기여 수를 제한해 상위 20개를 만든 뒤, 작은 리랭커 모델이 0에서 10점을 매겨 상위 10개를 남깁니다. 최종 순위가 정해지면 승자에 컨텍스트를 되붙입니다. 위키 섹션이 걸리면 인접한 두 섹션을 함께 가져와 청킹이 끊은 제목과 전제를 복원합니다.

에이전트가 쓸 수 있도록 검색 프리미티브를 `MCP`로 노출했습니다. 이 도구들은 의도적으로 단순하고 가능한 한 LLM을 배제해, 클라이언트가 빠르고 저렴하게 호출합니다. 오케스트레이션은 `Claude Code` 같은 MCP 호환 에이전트가 맡습니다.

**Projects**는 관련 소스를 묶어 팀별 검색 범위를 지정하는 기능입니다. 코퍼스가 커지자 "모든 것을 전부 검색"하는 방식이 쓸모를 잃었기 때문에 도입했습니다. 프로젝트는 특정 Slack 채널, 코드 리포, 내부 DB, 문서 공간을 묶은 이름 있는 번들입니다. 온보딩에서 사용자는 기본 프로젝트를 선택하고, 이후 질의는 그 범위로 자동 한정됩니다.

**명시적 공백**도 그대로 밝혀 둡니다. 사용한 플래너와 합성 LLM, 임베딩, 리랭커 모델의 이름은 공개되지 않았습니다. 자체 추론 하드웨어 사용 여부는 원문에 없으므로 가정하지 않습니다. 팀 규모와 개발 기간도 보고되지 않았습니다. 정확도, 지연, 비용 같은 성능 지표는 제시되지 않았습니다. 다만 IDF 4.0, burst 200자, RRF 상수 60 같은 구성 임계값은 원문에 명시되어 있습니다.

---

## 실전 구축 시퀀스

위 접근을 개인이나 소규모 팀 규모로 축소한 11단계 파이프라인입니다. Cerebras에서 유도한 아이디어는 표의 마지막 열에 [C]로, 일반 RAG 베스트프랙티스는 [R]로 표기합니다.

| 단계 | 목표 | 도구 옵션 | 핵심 결정·함정 |
|:---|:---|:---|:---|
| 0 스코프·스키마 설계 | 대상 소스와 아이템 스키마 확정 | YAML 레지스트리 | 범위를 먼저 좁힐 것. 스키마 없이 수집 시작 금지 [R] |
| 1 소스 수집 | provenance와 라이선스 확보 | per-source 어댑터, 크롤러 | 출처와 라이선스 미기록 시 나중에 인용 불가 [C] |
| 2 추출·정규화 | 원본을 공통 markdown으로 | Prompt (a), unstructured | 사실 추가/삭제 금지. OCR/인코딩만 교정 [R] |
| 3 청킹 | 검색 가능한 조각으로 분할 | 헤더 인지 분할 | 구조 인지 후 토큰 윈도우 300-800, 오버랩 10-15% [R] |
| 4 지식 구조화 | 원자적 아이템 추출 | Prompt (b) | 복합 문장은 분리. 수치/단위/버전 보존 [C] |
| 5 중복 제거·병합 | 동일 사실 통합 | Prompt (c), 유사도 top-k | 구별 수치/버전/조건은 유사해 보여도 삭제 금지 [C] |
| 6 태깅·분류 | 카테고리와 태그 부여 | Prompt (d) | 닫힌 카테고리 + 정규화 태그. 근사 동의어 난립 방지 [R] |
| 7 임베딩·인덱싱 | 통합 테이블에 적재 | pgvector, sqlite-vec | 단일 통합 테이블 + 델타싱크. 변경분만 재임베딩 [C] |
| 8 검색 | 하이브리드 조회 | 벡터 + 전문검색 | RRF 융합, age-decay, 리랭크 [C] |
| 9 답 합성 | 인용된 답 생성 | Planner→Executor→Synthesizer | 인용 필수. "KB에 없음" 폴백 [C] |
| 10 평가 | 검색 품질 측정 | Prompt (e), ragas | KB에서 Q&A 자동생성. recall@k, MRR, faithfulness [R] |
| 11 유지보수 | 최신성 유지 | 스케줄러, 델타싱크 | 소스별 주기 재수집, 중복 정리, 버전/superseded 관리 [R] |

Cerebras 유도 아이디어([C])는 통합 테이블, per-source 어댑터, 증류 후 임베딩, RRF 융합, 델타싱크, projects, Planner/Executor/Synthesizer, MCP 노출입니다. 나머지([R])는 청킹, 정규화, 닫힌 taxonomy, 자동 평가 같은 일반 RAG 베스트프랙티스입니다.

---

## 프롬프트 템플릿

각 단계에서 LLM에 넘길 프롬프트 다섯 종입니다. 프롬프트 본문은 영어 원문 그대로 둡니다.

(a) 문서 추출/정규화:

```text
You are a document normalizer. Convert the RAW content below into clean Markdown WITHOUT adding, removing, or inventing any facts.
Rules:
- Fix OCR/encoding errors, broken line-wraps, and mangled tables. Reconstruct tables as Markdown only when structure is unambiguous; otherwise keep as text.
- Remove navigation, ads, cookie banners, headers/footers, boilerplate.
- Preserve all headings, lists, code blocks, equations, and numbers exactly.
- Do NOT summarize or paraphrase. If a passage is unrecoverable, replace with [UNREADABLE].
SOURCE_TYPE: {{source_type}}  TITLE: {{title}}  URI: {{uri}}
RAW:
"""{{raw_content}}"""
Return only the cleaned Markdown.
```

(b) 원자적 지식 아이템 구조화:

```text
You are a knowledge extractor. From the SOURCE chunk, extract ATOMIC knowledge items. An atomic item states exactly ONE self-contained fact, claim, definition, or procedure.
Rules:
- Every item must be fully supported by the SOURCE. Never add outside knowledge.
- Split compound statements into separate items. Preserve specific numbers, units, versions, names, conditions.
- Put conditions in `context`. Quote exact supporting text in `source_span`. If nothing extractable, return [].
Output JSON array; each item:
{ "statement": "...", "detail": "...", "context": "... or null", "entities": ["..."], "item_type": "fact|definition|procedure|tradeoff|metric", "confidence": "high|medium|low", "source_span": "verbatim quote" }
SOURCE (id={{doc_id}}, title="{{title}}"):
"""{{chunk_text}}"""
Return only the JSON array.
```

(c) 중복 판정/병합:

```text
You decide whether a NEW knowledge item duplicates any EXISTING item.
Return JSON: { "decision": "merge|keep_both|supersede", "target_id": "... or null", "reason": "one line", "merged_item": { ...item schema... } }
Guidance:
- merge: same fact, only wording differs. Union entities; keep ALL source citations; keep more precise numbers; widen context.
- supersede: NEW contradicts/updates OLD (newer version, corrected number). merged_item = new fact.
- keep_both: related but distinct (different condition/metric/scope).
- NEVER drop a distinguishing number, version, or condition just because items look similar.
NEW item: {{new_item_json}}
EXISTING candidates (top-k by similarity): {{candidate_items_json}}
Return only the JSON.
```

(d) 태깅/분류:

```text
You are a KB librarian. Assign each item ONE primary category from the CLOSED list, optional secondary categories, and 2-6 normalized free tags.
CLOSED categories (primary from these ONLY): {{taxonomy_categories}}
Existing tag vocabulary (reuse; avoid near-synonyms): {{known_tags}}
Rules:
- Tags lowercase, singular, hyphenate multiword (e.g. "kv-cache"). Reuse existing tags over near-duplicates. Max 6.
- If no closed category fits, set primary_category to "UNCLASSIFIED" and explain in note.
- Base tags on statement+detail+entities only.
ITEM: {{item_json}}
Return JSON: { "primary_category": "...", "secondary_categories": ["..."], "tags": ["..."], "note": "... or null" }
```

(e) 검색 평가 Q&A 생성:

```text
You generate an evaluation set for a knowledge base. For the ITEM below, write {{n}} distinct questions a real user would ask that THIS item answers.
Rules:
- Vary phrasing: 1 keyword-style, 1 natural-language, 1 paraphrase avoiding the item's exact terms.
- Each question answerable SOLELY from this item. Include one "hard negative" (topically close but not answered here). Provide concise gold answers.
ITEM (id={{item_id}}): {{item_json}}
Return JSON: { "positives": [ { "question": "...", "gold_answer": "...", "expected_item_id": "{{item_id}}", "style": "keyword|nl|paraphrase" } ], "hard_negative": { "question": "...", "why_not": "..." } }
```

---

## 테스트: 실제로 돌려본 결과

파이프라인이 종이 위 설계에 그치지 않도록, 실제 샘플 문서에 프롬프트 (b)와 (d)를 적용했습니다. 입력 문서는 PagedAttention/vLLM 노트입니다.

> PagedAttention (vLLM) notes. The KV cache dominates GPU memory during LLM serving. Naive serving pre-allocates one contiguous buffer sized to max_seq_len per request, wasting 60-80% of KV memory through internal and external fragmentation. PagedAttention adapts OS virtual-memory paging: the KV cache is split into fixed-size blocks (default 16 tokens) stored non-contiguously and mapped through a per-request block table. This reduces waste to under 4% and enables copy-on-write block sharing, so parallel-sampling outputs and shared prefixes reuse the same physical blocks. On an A100-40GB with a 13B model, effective batch size grows roughly 2-4x versus contiguous allocation, lifting throughput similarly. The trade-off is a custom gather kernel that adds about 5-10% per-token latency, and block-table lookups require dedicated CUDA kernels.

프롬프트 (b)를 적용한 결과, 원자적 아이템 6개가 나왔습니다.

```json
[
 {"statement":"The KV cache is the dominant GPU memory consumer during LLM serving.","detail":"During inference serving, KV cache memory outweighs other allocations, making it the primary target for memory optimization.","context":null,"entities":["KV cache","LLM serving"],"item_type":"fact","confidence":"high","source_span":"The KV cache dominates GPU memory during LLM serving."},
 {"statement":"Naive contiguous KV allocation wastes 60-80% of KV memory via fragmentation.","detail":"Pre-allocating one contiguous buffer sized to max_seq_len per request causes internal and external fragmentation, wasting 60-80% of KV memory.","context":"Applies to naive serving that pre-allocates per request to max_seq_len.","entities":["max_seq_len","internal fragmentation","external fragmentation"],"item_type":"metric","confidence":"high","source_span":"Naive serving pre-allocates one contiguous buffer sized to max_seq_len per request, wasting 60-80% of KV memory through internal and external fragmentation."},
 {"statement":"PagedAttention stores the KV cache in fixed-size non-contiguous blocks mapped by a per-request block table.","detail":"Adapting OS virtual-memory paging, PagedAttention splits the KV cache into fixed-size blocks (default 16 tokens) stored non-contiguously and mapped through a per-request block table.","context":"Default block size is 16 tokens.","entities":["PagedAttention","block table","virtual memory paging"],"item_type":"definition","confidence":"high","source_span":"the KV cache is split into fixed-size blocks (default 16 tokens) stored non-contiguously and mapped through a per-request block table"},
 {"statement":"PagedAttention reduces KV memory waste to under 4% and enables copy-on-write block sharing.","detail":"Waste drops to under 4%; copy-on-write block sharing lets parallel-sampling outputs and shared prefixes reuse the same physical blocks.","context":null,"entities":["copy-on-write","prefix sharing","parallel sampling"],"item_type":"fact","confidence":"high","source_span":"This reduces waste to under 4% and enables copy-on-write block sharing, so parallel-sampling outputs and shared prefixes reuse the same physical blocks."},
 {"statement":"PagedAttention raises effective batch size roughly 2-4x on A100-40GB with a 13B model.","detail":"Versus contiguous allocation, effective batch size grows about 2-4x, lifting throughput by a similar factor.","context":"Measured on A100-40GB with a 13B model.","entities":["A100-40GB","13B model","batch size","throughput"],"item_type":"metric","confidence":"high","source_span":"On an A100-40GB with a 13B model, effective batch size grows roughly 2-4x versus contiguous allocation, lifting throughput similarly."},
 {"statement":"PagedAttention adds about 5-10% per-token latency and requires custom CUDA kernels.","detail":"A custom gather kernel adds roughly 5-10% per-token latency, and block-table lookups require dedicated CUDA kernels.","context":null,"entities":["gather kernel","CUDA kernels","per-token latency"],"item_type":"tradeoff","confidence":"high","source_span":"The trade-off is a custom gather kernel that adds about 5-10% per-token latency, and block-table lookups require dedicated CUDA kernels."}
]
```

이어서 아이템 #3에 프롬프트 (d)를 적용한 태깅 결과입니다.

```json
{ "primary_category": "LLM Serving", "secondary_categories": ["GPU Architecture"], "tags": ["paged-attention","kv-cache","vllm","memory-management","block-table"], "note": null }
```

비평: 추출은 6개 사실을 정확히 분리했고 수치와 조건도 보존됐습니다. 다만 아이템 #4와 #5가 각각 두 사실(#4는 낭비 4% 미만과 copy-on-write 공유, #5는 배치 2-4배와 처리량 향상)을 한 아이템에 담아 완전히 원자적이지는 않습니다. 개선점은 프롬프트 (b)에 규칙 한 줄을 추가하는 것입니다. "메커니즘과 정량 효과가 함께 오면 별도 아이템으로 분리하되 공통 topic으로 연결"하도록 명시하면, 원자성과 관계 추적을 동시에 얻습니다.

---

## 최종 목업 제안

전체 흐름을 종단 간으로 표현하면 다음과 같습니다. 각 단계에 붙는 프롬프트를 함께 표기했습니다.

```
  SOURCES                    PIPELINE (prompt at each step)                 STORE
 docs/PDF, notes/MD,   [1]Collect   [2]Extract    [3]Chunk   [4]Structure
 web/HTML, papers,  ─► manifest ──► normalize ──► split ──► atomic items
 code                 +license      (Prompt a)    hdr-aware  (Prompt b)
   per-source                                                    │
   plugin adapter ───────────────────────────────►              ▼
   (common schema)                                        [5]Dedup (Prompt c)
                                                                 ▼
                                                        [6]Tag/Taxonomy (Prompt d)
                                                                 ▼
                    ┌────────────────────────────────────────────────────┐
                    │ [7] UNIFIED KB TABLE                                │
                    │ id | statement | detail | embedding | category |   │
                    │ tags | sources[] | meta  + FTS index + delta-sync  │
                    └────────────────────────────────────────────────────┘
        QUERY ─► [8]Retrieve: vector ⨁ FTS ─RRF─► rerank +age-decay
                     ▼
        [9]Synthesize: Planner→Executor→Synthesizer, cited ("not in KB" fallback)
                     ▼
        [10]Eval: Q&A gen (Prompt e) ─► recall@k, MRR, faithfulness
        [11]Maintain: per-source refetch, delta-sync, dedup sweep  (loops back to store)
```

디스크 레이아웃은 아이템을 git으로 추적하는 source of truth로 두고, 인덱스는 생성물로 분리합니다.

```
kb/
├── sources.yaml       # 소스 레지스트리: uri, type, license, refresh cadence
├── taxonomy.yaml      # 닫힌 카테고리 + 알려진 태그 어휘
├── raw/               # [1] 원본 그대로
├── normalized/        # [2] 정제된 markdown + meta.json
├── items/             # [4-6] 원자적 아이템 (git 추적, source of truth)
│   └── <category>/<item_id>.json
├── index/             # [7] 생성물, gitignore (SQLite: items + FTS5 + sqlite-vec, 또는 pgvector)
├── eval/              # [10] qa_gold.jsonl + 결과
├── plugins/           # 소스별 어댑터 -> 공통 스키마 행 생성
└── logs/              # 병합 로그, 중복 판정, staleness 리포트
```

완성된 KB 아이템 하나는 다음 형태입니다.

```json
{
  "id": "kb_2026_llmserv_00042",
  "statement": "PagedAttention stores the KV cache in fixed-size non-contiguous blocks mapped by a per-request block table.",
  "detail": "Adapting OS virtual-memory paging, PagedAttention splits the KV cache into fixed-size blocks (default 16 tokens) stored non-contiguously, mapped through a per-request block table. This decouples logical token positions from physical memory placement.",
  "context": "Default block size is 16 tokens; mechanism used by vLLM.",
  "item_type": "definition",
  "topic": "paged-attention-memory-model",
  "primary_category": "LLM Serving",
  "secondary_categories": ["GPU Architecture"],
  "tags": ["paged-attention","kv-cache","vllm","memory-management","block-table"],
  "entities": ["PagedAttention","block table","KV cache","virtual memory paging"],
  "confidence": "high",
  "sources": [ { "doc_id": "vllm-paged-attention-notes", "uri": "local://notes/vllm-paged-attention-notes.md", "source_type": "personal_note", "license": "internal", "source_span": "the KV cache is split into fixed-size blocks (default 16 tokens) stored non-contiguously and mapped through a per-request block table", "fetched_at": "2026-07-28" } ],
  "related_items": ["kb_2026_llmserv_00043","kb_2026_llmserv_00044"],
  "status": "active",
  "superseded_by": null,
  "content_hash": "sha256:9f2c...",
  "embedding_ref": "index/kb.db#vec:00042",
  "created_at": "2026-07-28T09:12:00Z",
  "updated_at": "2026-07-28T09:12:00Z"
}
```

이 스키마의 세 필드가 유지보수를 지탱합니다. `content_hash`는 소스 내용의 변경 여부를 판별해, 값이 그대로면 재임베딩을 건너뛰는 델타싱크를 가능하게 합니다. `status`와 `superseded_by`는 오래된 아이템을 삭제하지 않고 비활성으로 표시해, 이력을 보존하는 비파괴 유지보수를 지원합니다. `sources[]` 배열은 병합 시 여러 출처의 인용을 하나의 아이템에 누적해, 같은 사실을 여러 곳에서 확인했다는 근거를 잃지 않게 합니다.

---

## 정리

Cerebras 사례의 핵심 교훈은 넷입니다. 데이터를 이관하지 않고 있는 자리에서 연결할 것, 원본이 아니라 증류본을 임베딩할 것, 검색은 단일 신호가 아니라 다신호를 융합할 것, 코퍼스가 커지면 범위를 스코핑할 것입니다.

이 글이 제안한 파이프라인은 그 교훈을 프롬프트 다섯 종으로 구현합니다. 추출, 구조화, 중복 판정, 태깅, 평가를 각각 LLM에 위임하고, 결과를 단일 통합 테이블에 모읍니다. 개인 규모에서는 통합 테이블 + 원자적 아이템 + 하이브리드 검색 + 자동 Q&A 평가가 실용적 최소 구성입니다. 여기서부터 시작해 소스와 신호를 점진적으로 늘리면 됩니다.

---

## 레퍼런스

- Cerebras, "How we built our knowledge base" - `cerebras.ai/blog/how-we-built-our-knowledge-base` (원문 직접 확보)
- 관련 2차 정리: `zenn.dev/kun432/scraps/a207c3f2cc7f5c`
- CocoIndex - 오픈소스 코드 인덱싱 프레임워크
- ragas - RAG 평가 라이브러리 (recall@k, faithfulness 등)
- 다이어그램은 원작입니다.
