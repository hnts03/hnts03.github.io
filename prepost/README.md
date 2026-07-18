# prepost/ — 발행 대기 영역

발행 직전 단계의 완성 포스트를 두는 디렉토리다. Jekyll 빌드에서 제외되므로(`_config.yml`의 `exclude`), 배포된 블로그 UI로는 접근할 수 없다. GitHub 소스에서는 열람 가능하다.

## 워크플로우

```
draft/         →  prepost/          →  _posts/
(초안 작성)        (완성, 리뷰 대기)      (발행)
유저 작성          에이전트 작성          유저 OK 후 이동
```

1. **에이전트**가 완성한 포스트(한/영 쌍)를 `prepost/`에 둔다.
2. **유저**가 `prepost/`를 리뷰한다.
3. 유저가 **OK 판정**하면 해당 포스트를 `_posts/`로 이동해 발행한다.
4. 발행 시 이미지(`assets/img/posts/<slug>/`)와 vault 문서도 함께 처리한다.

## 규칙

- 파일명은 최종 형식 그대로 사용한다: `YYYY-MM-DD-slug-kr.md`, `YYYY-MM-DD-slug-en.md`.
- 한/영 쌍으로 둔다.
- 포스트 작성 규칙은 `CLAUDE.md`와 `draft/template.md`를 따른다.
- 발행(=`_posts/`로 이동)은 유저의 명시적 OK 이후에만 수행한다. 에이전트가 임의로 `_posts/`에 직접 쓰지 않는다.
