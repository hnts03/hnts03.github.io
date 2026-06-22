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
- 초안은 `_drafts/`에 작성. 빌드 시 `--future` 플래그 없이는 미래 날짜 포스트가 제외된다.

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

### 이미지 취득 스크립트

`scripts/fetch-post-image.py` — PDF 논문 figure 추출 또는 웹 이미지 다운로드.

```bash
# PDF에서 3페이지 전체 추출
python scripts/fetch-post-image.py pdf paper.pdf --page 3 --post gpu-arch-1 --name fig1-sm-structure

# PDF에서 특정 영역만 크롭 (x0 y0 x1 y1, PDF points 단위)
python scripts/fetch-post-image.py pdf paper.pdf --page 3 --crop 50 400 500 700 --post gpu-arch-1 --name fig1-sm-structure

# 웹 URL에서 다운로드
python scripts/fetch-post-image.py url https://example.com/image.png --post gpu-arch-1 --name fig1-sm-structure

# 의존성
pip install pymupdf requests
```

실행 시 `assets/img/posts/<slug>/attribution.md`에 출처가 자동 기록된다.

### 저작권 원칙

| 소스 | 조건 |
|:---|:---|
| arXiv 논문 (CC BY) | attribution.md에 출처 명시 후 사용 가능 |
| IEEE/ACM 논문 | 기술적으로 허가 필요. 사용 시 반드시 출처 명시 |
| 웹 이미지 | 원본 페이지 라이선스 직접 확인 후 결정 |

`attribution.md`가 없는 이미지 디렉토리는 커밋하지 않는다.

## 아키텍처 개요

**Beautiful Jekyll** 기반 정적 사이트. GitHub Pages로 자동 배포.

```
_config.yml          # 사이트 전역 설정 (네비바, 색상, 플러그인 등)
_posts/              # 발행된 포스트 (한/영 쌍)
_drafts/             # 미발행 초안
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
