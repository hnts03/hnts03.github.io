# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 블로그 정체성

- **운영자**: AI System Software Engineer (AMD GPU 클러스터 기반 LLM 추론 최적화 전문)
- **주요 주제**: 컴퓨터 아키텍처, GPU 아키텍처, CUDA/HIP, LLM 서빙, HPC
- **언어**: 한국어(메인) + 영어(서브) — 모든 포스트는 한/영 쌍으로 작성
- **성격**: INTJ, 정확한 내용만 작성. 불확실한 정보는 명시하거나 생략

## 빌드 / 로컬 서버

```bash
# 의존성 설치
bundle install && bundle exec appraisal install

# 로컬 미리보기 (http://localhost:4000)
bundle exec jekyll serve

# 프로덕션 빌드 (CI와 동일)
bundle exec appraisal jekyll build --future --config _config.yml
```

Jekyll 3.9 / 4.3 두 버전 모두 지원 (`Appraisals` 파일 참고). CI는 `appraisal jekyll build`로 두 버전 모두 검증한다.

## 포스트 작성 규칙

### 파일명 형식

```
_posts/YYYY-MM-DD-slug-kr.md   # 한국어
_posts/YYYY-MM-DD-slug-en.md   # 영어
```

### Front Matter 필수 항목

```yaml
---
layout: post
title: "제목"
subtitle: "부제목"
tags: [Tag1, Tag2]
lang: kr          # 또는 en
translation-url: /YYYY-MM-DD-slug-en/   # 반대 언어 URL
readtime: true
mathjax: true     # 수식 포함 시
---
```

- `lang` + `translation-url` 쌍이 있어야 포스트 상단에 언어 전환 버튼이 표시된다 (`_includes/lang-switch.html`).
- permalink 형식: `/:year-:month-:day-:title/` — URL에 슬러그가 그대로 쓰인다.
- 빌드 시 `--future` 플래그 없이는 미래 날짜 포스트가 제외된다.

### 발행 워크플로우 (반드시 준수)

포스트는 `_posts/`에 바로 쓰지 않는다. `prepost/`를 거쳐 리뷰 후 발행한다. `prepost/`로 들어오는 경로는 둘이다.

```
[유저 경로]   draft/ ──(에이전트가 이어받아 다듬음)──┐
                                                    ├──→  prepost/ ──(유저 OK)──→  _posts/
[에이전트 경로]  (곧바로 prepost/부터 작성) ──────────┘        리뷰 대기            발행
```

- **`draft/`**: 유저가 직접 초안 소스를 쓸 때만 사용하는 파이프. `draft/template.md`가 표준 템플릿. 에이전트는 여기서 시작하지 않고, 유저 초안을 이어받을 때 참조한다.
- **`prepost/`**: 발행 대기 영역. **에이전트가 새 포스트를 쓸 때는 `draft/`를 거치지 않고 곧바로 `prepost/`부터 작성한다.** `_posts/`에 직접 쓰지 않는다. Jekyll 빌드에서 제외되어 블로그 UI로 접근 불가(GitHub 소스는 열람 가능). 자세한 규칙은 `prepost/README.md`.
- **유저가 `prepost/`를 리뷰하고 OK 판정하면**, 해당 포스트(한/영 쌍)를 `_posts/`로 이동해 발행한다. 이때 이미지(`assets/img/posts/<slug>/`)와 vault 문서도 함께 처리한다.
- `prepost/`, `draft/`는 `_config.yml`의 `exclude`에 등록되어 배포 사이트에 빌드되지 않는다.

### 콘텐츠 스타일

- 핵심 개념은 ASCII 다이어그램 또는 표로 시각화
- 코드 블록에 언어 명시 (` ```c `, ` ```cuda ` 등)
- MathJax 수식: `$inline$`, `$$block$$`
- 시리즈 포스트에는 서두에 시리즈 로드맵 표 포함

## 포스트 에이전트 페르소나

개인 작성 노트에서 추출한 작문 규칙. 포스트 생성 시 반드시 준수.

### 문체

- **정중 문어체**: `~입니다`, `~합니다`, `~됩니다`. 구어체(`~이에요`, `~거든요`) 금지.
- **단문 우선**: 한 문장에 하나의 사실. 접속사로 늘어지는 문장 금지.
- **쿠션 언어 금지**: "~인 것 같습니다", "아마도", "비교적" 등 회피. 불확실하면 "~로 알려져 있습니다" 또는 생략.
- **감탄/수사 금지**: "정말 혁신적인", "놀랍게도" 등 과도한 수식어 금지.
- **한국어 em-dash/세미콜론 금지**: 한국어 포스트에서 em-dash(—)와 세미콜론(;)을 산문·제목에 사용하지 않는다. 대신 콜론(:), 일반 대시(-), 또는 문장 분리를 사용한다. 영어 포스트에서는 em-dash 사용 가능. 표에서 N/A 값이나 코드 외부 ASCII 다이어그램에서도 `—` 대신 `-`를 사용한다.

### 구조 패턴

- **맥락 → 문제 → 기술 순서**: 개념을 바로 설명하지 않고, 그것이 등장한 배경(왜 필요한가)부터 시작.
- **의문형 섹션 제목 허용**: "GPU는 어디서 왔는가", "왜 별도의 서빙 프레임워크가 필요한가". 주제를 직접 드러내는 서술형도 가능.
- **메타 문장 금지**: "이 포스트에서는 X를 다루겠습니다" 같은 서론 불필요. 본론 바로 시작.
- **섹션 구분**: 주요 섹션 끝에 `---` 수평선.
- **마무리**: 포스트 끝에 비교/요약 표 + 다음 글 예고 한 문장.

### 강조 규칙

- `**볼드**`: 핵심 개념의 **첫 등장**에만 사용. 반복 사용 금지.
- `` `인라인 코드` ``: 기술 고유명사(API, 파라미터, 함수명, 아키텍처 코드명).
- **수치와 구체성 선호**: "성능이 향상됩니다" 대신 "메모리 낭비를 60~80% 제거합니다"처럼 구체적 수치 사용. 수치가 불확실하면 생략.
- **괄호 보충**: 핵심 내용 뒤에 짧은 보충 설명을 괄호로 삽입. (예: Copy-on-Write 방식으로 블록 공유도 가능해 prefix 재사용, 병렬 샘플링(beam search 등)에서도 메모리를 절약합니다.)

### 시각화

- **ASCII 다이어그램**: 구조, 메모리 레이아웃, 계층 관계를 코드블록으로 표현. 텍스트 설명만으로 부족한 경우 필수.
- **비교 전후 나란히**: 기존 방식 vs 새 방식을 ASCII로 병렬 표현.
- **표**: 여러 대상을 비교할 때 표로 압축. 표 다음에 선택 기준 또는 요약 불릿 추가.

### 금지 패턴

```
❌ "이 포스트에서는 X를 살펴보겠습니다."
❌ "X는 정말 중요한 개념입니다."
❌ "다양한 방법들이 존재하는데..."
❌ "~인 것 같습니다 / ~할 수도 있을 것 같습니다"
❌ 불확실한 수치를 마치 사실처럼 서술
❌ 한국어 산문·제목에서 em-dash(—) 또는 세미콜론(;) 사용
```

## 포스트 이미지 관리

### 디렉토리 구조

포스트별로 `assets/img/posts/<slug>/` 디렉토리를 사용한다. slug는 날짜·언어 접미사를 제외한 주제 식별자.

```
assets/img/posts/
├── gpu-arch-1/              # GPU 아키텍처 #1 포스트
│   ├── fig1-sm-structure.png
│   └── attribution.md       # 이미지 출처 기록 (필수)
└── llm-serving-overview/
    └── attribution.md
```

마크다운 삽입:
```markdown
![SM 구조도](/assets/img/posts/gpu-arch-1/fig1-sm-structure.png)
```

### 에이전트 이미지 워크플로우

포스트 작성 시 에이전트가 직접 이미지를 취득한다. 유저 개입 없이 자동으로 처리하는 것과 유저 가이드가 필요한 것을 구분한다.

**에이전트가 자율적으로 처리:**
- WebSearch + WebFetch로 arXiv, 오픈소스 블로그에서 관련 이미지 탐색·다운로드
- `scripts/gen-diagram.py`로 기술 다이어그램 코드 생성 (GPU 구조도, 메모리 레이아웃, 흐름도 등)
- `assets/img/posts/<slug>/attribution.md`에 출처 자동 기록

**유저 가이드 후 에이전트 처리:**
- PDF에서 특정 figure 추출: 유저가 "이 논문 Figure N 써줘" 지시 → 에이전트가 `uv run scripts/fetch-post-image.py pdf ...` 실행

**이미지 우선순위:**
1. 코드 생성 다이어그램 (`scripts/gen-diagram.py`) — 정밀도 최우선, 저작권 문제 없음
2. arXiv/CC 라이선스 웹 이미지 — 출처 명시 후 사용
3. 논문 figure (비상업 블로그 fair use) — 반드시 출처 명시

### 스크립트

```bash
# uv가 의존성 자동 설치·실행 (pip install 불필요)

# PDF에서 figure 추출 (에이전트가 직접 실행)
uv run scripts/fetch-post-image.py pdf paper.pdf --page 3 --post gpu-arch-1 --name fig1-sm-structure
uv run scripts/fetch-post-image.py pdf paper.pdf --page 3 --crop 50 400 500 700 --post gpu-arch-1 --name fig1-sm-structure

# 웹 URL에서 다운로드 (에이전트가 직접 실행)
uv run scripts/fetch-post-image.py url https://example.com/img.png --post gpu-arch-1 --name fig1

# 다이어그램 생성 (에이전트가 직접 실행)
uv run scripts/gen-diagram.py --post gpu-arch-1 --name sm-structure --type block
```

### 저작권 원칙

| 소스 | 처리 방식 |
|:---|:---|
| 코드 생성 다이어그램 | 제한 없음 |
| arXiv 논문 (CC BY) | attribution.md에 논문 제목·저자·arXiv ID 기록 |
| 논문 figure (IEEE/ACM 등) | 비상업 블로그 fair use. attribution.md에 DOI·저자 기록 필수 |
| 웹 이미지 | 출처 URL·라이선스 attribution.md에 기록 |

`attribution.md` 없는 이미지 디렉토리는 커밋하지 않는다.

## 아키텍처 개요

**Beautiful Jekyll** 기반 정적 사이트. GitHub Pages로 자동 배포.

```
_config.yml          # 사이트 전역 설정 (네비바, 색상, 플러그인 등)
_posts/              # 발행된 포스트 (한/영 쌍)
draft/               # 유저 초안 작성 공간 (빌드 제외). template.md 표준 템플릿
prepost/             # 에이전트 완성 포스트, 발행 대기 (빌드 제외, UI 접근 불가)
_layouts/            # base → default/post/page/home/minimal 상속 구조
_includes/           # 재사용 컴포넌트
  lang-switch.html   # 한/영 전환 버튼 (front matter의 lang + translation-url로 동작)
  mathjax.html       # MathJax 로더
assets/
  img/               # 포스트 이미지
  css/beautifuljekyll.css  # 테마 메인 CSS
```

네비게이션(`navbar-links`)은 `_config.yml`에서 직접 편집. 현재 카테고리: Computer Architecture / GPU Architecture / RTL / C·C++ / Python / CUDA / ROCm / Metal / SYCL / AI / Simulation / Project.

## Vault 연동

`vault/` — Research vault(`/Users/hanets/workspace/my-github-repos/Research/`)의 심볼릭 링크. `.gitignore`에 등록되어 블로그 repo에는 추적되지 않음.

**워크플로우**: 포스트 작성 후 해당 주제의 지식을 `vault/post/<카테고리>/` 에 문서화.

```
vault/post/
├── gpu-architecture/   # GPU 아키텍처 시리즈 관련 지식
└── llm-serving/        # LLM 서빙 프레임워크 관련 지식
```

새 카테고리가 생기면 `vault/post/` 아래 디렉토리를 추가하고 `vault/post/README.md` 목록도 업데이트.

## 배포

`master` 브랜치에 push하면 GitHub Actions (`ci.yml`)가 자동으로 빌드·배포.

### 브랜치 규칙 (반드시 준수)

- **작업 브랜치**: `dev-blog`. 모든 커밋과 push는 `dev-blog`에만 한다.
- **`master` 직접 push 절대 금지.** master는 에이전트가 직접 조작하지 않는다.
- **브랜치 간 merge 금지**: 사용자의 명시적 허가 없이 임의로 merge하지 않는다.
- non-fast-forward 오류가 발생해도 임의로 merge하지 않는다. 상황을 설명하고 사용자에게 처리 방법을 묻는다.

> 과거에 master에 직접 push 후 non-fast-forward 해결을 위해 origin/master를 dev-blog에 merge했다가 upstream Beautiful Jekyll 커밋이 섞이고 히스토리가 오염된 이력이 있다.
