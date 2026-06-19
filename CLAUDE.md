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

## 배포

`master` 브랜치에 push하면 GitHub Actions (`ci.yml`)가 자동으로 빌드·배포.
