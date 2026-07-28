---
layout: post
title: "Building a Knowledge Base: Lessons from Cerebras and a Tested Mockup"
subtitle: "Connect data where it lives, plus a prompt-tested KB pipeline proposal"
tags: [AI, LLM, RAG, Knowledge-Base]
lang: en
translation-url: /2026-07-28-knowledge-base-kr/
readtime: true
mathjax: false
---

Cerebras published an account of how they built their internal knowledge base. The approach connects data where it already lives instead of migrating everything into one place. This post distills that approach from the original post, then proposes a KB build sequence an individual or small team can follow — a mockup I tested directly by running the prompts.

## On sources

This summary is based on the original Cerebras post (`cerebras.ai/blog/how-we-built-our-knowledge-base`), obtained directly. The description below reflects only what the original states. I keep the exact configuration thresholds and tool names the post gives, and I flag as gaps anything the original does not state (for example, the names of the planner/synthesis LLMs, the embedding model, and the reranker model).

---

## The Cerebras approach

The **motivation** is explicit. Recording everything in one platform — the dream of a single "source of truth" — rarely works in practice. Information is generated wherever it is convenient: suggested edits in a document, threads in Slack, code references in GitHub, and status metadata in Jira. Each platform is optimized for its own domain, so forcing everything into one place breaks usability. So Cerebras aimed for a system that required minimal change to existing behavior, extracting data from each platform directly (meeting data where it lives). The internal tool is named `Cerebras Knowledge`.

The **scale** is over 15,000 queries per day. Users fall into three classes: people, automations, and agents. It is internal-only, and it became one of the most widely adopted internal tools roughly three months after launch.

The knowledge base provides three things: a platform for collecting and storing internal data, a platform for querying that data, and a layer that enforces authentication and authorization with auditing and analytics.

The core of the architecture is a single point where every source converges. The original describes it as "a single Postgres table that holds embeddings, raw summaries, and metadata." Every source, from Slack threads to netlists, lands in the same embeddings table, and anything in that table is immediately queryable through the same interface. In front of it sits a per-source connector that defines, for each source, what to connect, how, and how often to fetch. This post calls that convergence a **narrow waist** — the term is mine, not Cerebras's.

```
  MANY SOURCES                  NARROW WAIST                       ONE QUERY
 Slack threads  ─┐
 GitHub code    ─┤   per-source     common schema row      single Postgres
 Google Docs   ─┼─►  connector  ─►  (embedding +      ─►   table (stores    ─► single interface
 Jira metadata ─┘   (normalize)     summary + meta)         embeddings) + FTS
```

**Slack ingestion** was the most important data source to design for, since the most up-to-date engineering discussions happen there. A Slack bot runs in Socket Mode (WebSocket), receiving every message event in real time without polling. On arrival, each event is acknowledged immediately and deduplicated by its stable event ID. The ingest consumer does not store a message in isolation — it resolves the thread the message belongs to and re-fetches the entire conversation (parent and every reply), then writes the whole thread back as one row. Every Slack channel has its own data source, so ingestion cadence can be tuned per channel.

Raw text is keyword-searchable the moment it lands, via a Postgres full-text (GIN) index over the raw content. For vector search, additional processing follows: an LLM extracts structured data from the full thread — a one-line question an engineer would actually search for, a short summary, the resolution, and the systems and code references mentioned. These data points are embedded into the shared table; the original transcript is not embedded directly. Accuracy increased significantly once threads were normalized into a consistent format.

To surface important individual messages that a thread-level summary misses, they use **bursting**. A burst is a run of consecutive messages from the same author, embedded with the thread topic prepended as context. To keep low-signal data out, each burst must clear a threshold before embedding: it contains a relatively rare token (IDF ≥ 4.0), the combined burst is at least 200 characters, and one or more messages carry reactions (a social boost).

**Code indexing** uses the open-source `CocoIndex`. Even repos over 40GB are split coarse-to-fine along language-specific regex boundaries: higher-level boundaries such as classes are tried first, falling back to methods and then smaller blocks when a chunk is still too large. A single file can produce embeddings at several levels (file-level, function-level). CocoIndex tracks sync metadata in Postgres and, on each commit, re-embeds and re-exports only the changed chunks.

**Custom sources** are handled as plugin scripts. A team opens a PR with a small Python module that reads its own system and emits rows shaped like the shared embeddings table; the rest of the stack works unchanged.

**Retrieval and ranking** fuse four signals.

- Full-text search: exact token matches (error strings, flag names, hostnames)
- Embeddings: paraphrase coverage
- IDF: separating signal from filler
- Age decay: demoting stale answers

Query handling runs in this order: a Planner LLM inspects the query and active project to select tools, an Executor fans the calls out in parallel and normalizes results into a common evidence schema, and a final LLM synthesizes an answer with citations. The available tools include `search` (the unified vector pipeline), `search_slack`, `search_code` (ripgrep over repos), `subsystem_index` (per-file LLM summaries), `recent_prs`, and `who_knows`.

Reranking first combines the retrievers' result lists with reciprocal rank fusion (RRF): for each document, it adds `weight / (60 + rank)` for every list the document appears in, with a default weight of 1.0 and a smoothing constant of 60. Duplicate chunks are then merged to their source and per-file contributions capped to yield a diverse top twenty; a small reranker model scores each 0–10 and the top ten are kept. Once ranking is final, context is added back to the winners — matching a wiki section pulls in its two neighboring sections so the headings and preconditions that chunking split apart are not lost.

Search primitives are exposed over `MCP` for agents to use. These tools are intentionally simple and as LLM-free as possible, so clients can call them quickly and cheaply; orchestration is left to an MCP-compatible agent such as `Claude Code`.

**Projects** group related sources to scope search per team. They were introduced because "search everything everywhere" stopped being useful as the corpus grew. A project is a named bundle of specific Slack channels, code repos, internal databases, and document spaces. During onboarding a user picks a default project, and queries are automatically scoped to it thereafter.

The **explicit gaps** are stated as-is. The names of the planner/synthesis LLMs, the embedding model, and the reranker model were not disclosed. Whether their own inference hardware is used is not stated, so it is not assumed. Team size and development timeline were not reported. No accuracy, latency, or cost metrics are given — though configuration thresholds such as IDF 4.0, the 200-character burst floor, and the RRF constant of 60 are stated explicitly.

---

## A practical build sequence

Here is the same approach as an 11-phase pipeline, down-scaled for an individual or small team. Cerebras-derived ideas are marked [C] in the last column; general RAG best practices are marked [R].

| Phase | Goal | Tool options | Key decision / pitfall |
|:---|:---|:---|:---|
| 0 Scope & schema | Fix target sources and item schema | YAML registry | Narrow scope first. Do not ingest without a schema [R] |
| 1 Collect sources | Secure provenance and license | per-source adapter, crawler | No provenance/license means no citation later [C] |
| 2 Extract & normalize | Raw to common markdown | Prompt (a), unstructured | No adding/removing facts. Fix only OCR/encoding [R] |
| 3 Chunk | Split into retrievable pieces | header-aware splitter | Structure-aware, then token window 300-800, overlap 10-15% [R] |
| 4 Structure knowledge | Extract atomic items | Prompt (b) | Split compound statements. Preserve numbers/units/versions [C] |
| 5 Dedup & merge | Unify identical facts | Prompt (c), similarity top-k | Never drop a distinguishing number/version/condition [C] |
| 6 Tag & classify | Assign category and tags | Prompt (d) | Closed categories + normalized tags. Avoid near-synonyms [R] |
| 7 Embed & index | Load into unified table | pgvector, sqlite-vec | Single unified table + delta-sync. Re-embed only changes [C] |
| 8 Retrieve | Hybrid lookup | vector + full-text | RRF fusion, age-decay, rerank [C] |
| 9 Synthesize | Generate cited answers | Planner→Executor→Synthesizer | Citations required. "Not in KB" fallback [C] |
| 10 Evaluate | Measure retrieval quality | Prompt (e), ragas | Auto-generate Q&A from KB. recall@k, MRR, faithfulness [R] |
| 11 Maintain | Keep it fresh | scheduler, delta-sync | Per-source refetch, dedup sweep, version/superseded handling [R] |

The Cerebras-derived ideas ([C]) are the unified table, per-source adapters, distill-then-embed, RRF fusion, delta-sync, projects, Planner/Executor/Synthesizer, and MCP exposure. The rest ([R]) — chunking, normalization, a closed taxonomy, automated evaluation — are general RAG best practices.

---

## Prompt templates

Five prompts, one per step, to hand to the LLM. The prompt bodies are kept verbatim.

(a) Document extraction / normalization:

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

(b) Atomic knowledge item structuring:

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

(c) Duplicate decision / merge:

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

(d) Tagging / classification:

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

(e) Retrieval-evaluation Q&A generation:

```text
You generate an evaluation set for a knowledge base. For the ITEM below, write {{n}} distinct questions a real user would ask that THIS item answers.
Rules:
- Vary phrasing: 1 keyword-style, 1 natural-language, 1 paraphrase avoiding the item's exact terms.
- Each question answerable SOLELY from this item. Include one "hard negative" (topically close but not answered here). Provide concise gold answers.
ITEM (id={{item_id}}): {{item_json}}
Return JSON: { "positives": [ { "question": "...", "gold_answer": "...", "expected_item_id": "{{item_id}}", "style": "keyword|nl|paraphrase" } ], "hard_negative": { "question": "...", "why_not": "..." } }
```

---

## Test: what actually came out

To keep the pipeline from staying on paper, I applied prompts (b) and (d) to a real sample document. The input is a set of PagedAttention/vLLM notes.

> PagedAttention (vLLM) notes. The KV cache dominates GPU memory during LLM serving. Naive serving pre-allocates one contiguous buffer sized to max_seq_len per request, wasting 60-80% of KV memory through internal and external fragmentation. PagedAttention adapts OS virtual-memory paging: the KV cache is split into fixed-size blocks (default 16 tokens) stored non-contiguously and mapped through a per-request block table. This reduces waste to under 4% and enables copy-on-write block sharing, so parallel-sampling outputs and shared prefixes reuse the same physical blocks. On an A100-40GB with a 13B model, effective batch size grows roughly 2-4x versus contiguous allocation, lifting throughput similarly. The trade-off is a custom gather kernel that adds about 5-10% per-token latency, and block-table lookups require dedicated CUDA kernels.

Applying prompt (b) yielded six atomic items.

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

Then, applying prompt (d) to item #3 gave this tagging result.

```json
{ "primary_category": "LLM Serving", "secondary_categories": ["GPU Architecture"], "tags": ["paged-attention","kv-cache","vllm","memory-management","block-table"], "note": null }
```

Critique: the extraction cleanly separated six facts and preserved numbers and conditions. But items #4 and #5 each pack two facts into one item (#4 combines the sub-4% waste and copy-on-write sharing; #5 combines the 2-4x batch size and the throughput lift), so they are not fully atomic. The improvement is one added rule in prompt (b): "when a mechanism and its quantitative effect appear together, split them into separate items but link them by a shared topic." That buys atomicity and relationship tracking at once.

---

## The final mockup proposal

The end-to-end flow looks like this, with the prompt at each step marked.

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

The disk layout keeps items as the git-tracked source of truth and separates the index as a generated artifact.

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

One finished KB item takes this shape.

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

Three fields carry maintenance. `content_hash` detects whether the source content changed, enabling delta-sync that skips re-embedding when the value is unchanged. `status` and `superseded_by` mark stale items inactive instead of deleting them, supporting non-destructive maintenance that preserves history. The `sources[]` array accumulates citations from multiple origins into one item on merge, so the evidence that the same fact was confirmed in several places is never lost.

---

## Wrap-up

The Cerebras case offers four lessons. Connect data where it lives instead of migrating it. Embed the distillate, not the raw source. Fuse multiple retrieval signals rather than relying on one. Scope the search once the corpus grows.

The pipeline proposed here implements those lessons with five prompts. Extraction, structuring, dedup, tagging, and evaluation are each delegated to the LLM, and the results are collected into one unified table. At an individual scale, a unified table + atomic items + hybrid retrieval + automated Q&A evaluation is the practical minimum. From there, sources and signals can grow incrementally.

---

## References

- Cerebras, "How we built our knowledge base" - `cerebras.ai/blog/how-we-built-our-knowledge-base` (original obtained directly)
- Related secondary write-up: `zenn.dev/kun432/scraps/a207c3f2cc7f5c`
- CocoIndex - open-source code indexing framework
- ragas - RAG evaluation library (recall@k, faithfulness, and more)
- Diagrams are original.
