#!/usr/bin/env python3
"""
포스트용 이미지 취득 스크립트.

지원 소스:
  - PDF 파일 (논문 figure 추출)
  - 웹 URL (이미지 직접 다운로드)

사용 예시:
  # PDF에서 figure 추출 (페이지 번호는 1-based)
  python scripts/fetch-post-image.py pdf path/to/paper.pdf --page 3 --post gpu-arch-1 --name fig1-sm-structure

  # 웹 이미지 다운로드
  python scripts/fetch-post-image.py url https://example.com/image.png --post gpu-arch-1 --name fig1-sm-structure

의존성:
  pip install pymupdf requests Pillow

저작권 주의:
  이 스크립트는 attribution.md를 함께 생성합니다.
  IEEE/ACM 논문 figure는 기술적으로 허가가 필요합니다.
  arXiv (CC BY) 논문은 출처 명시 시 사용 가능합니다.
  웹 이미지는 라이선스를 직접 확인하세요.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

POSTS_IMG_DIR = Path("assets/img/posts")
ATTRIBUTION_FILENAME = "attribution.md"


def ensure_post_dir(post_slug: str) -> Path:
    post_dir = POSTS_IMG_DIR / post_slug
    post_dir.mkdir(parents=True, exist_ok=True)
    return post_dir


def extract_from_pdf(pdf_path: str, page: int, post_slug: str, name: str, crop: tuple | None):
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("오류: PyMuPDF가 필요합니다. `pip install pymupdf`")
        sys.exit(1)

    pdf = fitz.open(pdf_path)
    if page < 1 or page > len(pdf):
        print(f"오류: 페이지 범위 초과 (총 {len(pdf)}페이지)")
        sys.exit(1)

    pg = pdf[page - 1]

    if crop:
        # crop = (x0, y0, x1, y1) in points
        clip = fitz.Rect(*crop)
        mat = fitz.Matrix(2, 2)  # 2x 해상도
        pix = pg.get_pixmap(matrix=mat, clip=clip)
    else:
        mat = fitz.Matrix(2, 2)
        pix = pg.get_pixmap(matrix=mat)

    post_dir = ensure_post_dir(post_slug)
    out_path = post_dir / f"{name}.png"
    pix.save(str(out_path))
    print(f"저장: {out_path}")

    return {
        "file": f"{name}.png",
        "source_type": "pdf",
        "source_path": pdf_path,
        "page": page,
        "extracted": str(date.today()),
        "license": "확인 필요 — IEEE/ACM은 허가 필요, arXiv CC BY는 출처 명시 후 사용 가능",
    }


def download_from_url(url: str, post_slug: str, name: str):
    try:
        import requests
    except ImportError:
        print("오류: requests가 필요합니다. `pip install requests`")
        sys.exit(1)

    response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp", "image/svg+xml": ".svg"}
    ext = next((v for k, v in ext_map.items() if k in content_type), Path(url.split("?")[0]).suffix or ".png")

    post_dir = ensure_post_dir(post_slug)
    out_path = post_dir / f"{name}{ext}"
    out_path.write_bytes(response.content)
    print(f"저장: {out_path}")

    return {
        "file": f"{name}{ext}",
        "source_type": "url",
        "source_url": url,
        "downloaded": str(date.today()),
        "license": "확인 필요 — 원본 페이지의 라이선스를 직접 확인하세요",
    }


def update_attribution(post_slug: str, entry: dict):
    post_dir = POSTS_IMG_DIR / post_slug
    attr_path = post_dir / ATTRIBUTION_FILENAME

    lines = attr_path.read_text(encoding="utf-8").splitlines() if attr_path.exists() else [
        f"# {post_slug} 이미지 출처\n",
        "포스트에 사용된 이미지의 출처 및 라이선스 정보.\n",
    ]

    lines.append(f"\n## {entry['file']}")
    for k, v in entry.items():
        if k != "file":
            lines.append(f"- **{k}**: {v}")

    attr_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Attribution 업데이트: {attr_path}")


def main():
    parser = argparse.ArgumentParser(description="포스트용 이미지 취득 스크립트")
    sub = parser.add_subparsers(dest="mode", required=True)

    # PDF 모드
    pdf_p = sub.add_parser("pdf", help="PDF에서 페이지 추출")
    pdf_p.add_argument("pdf_path", help="PDF 파일 경로")
    pdf_p.add_argument("--page", type=int, required=True, help="추출할 페이지 번호 (1-based)")
    pdf_p.add_argument("--crop", nargs=4, type=float, metavar=("X0", "Y0", "X1", "Y1"),
                       help="크롭 영역 (points 단위, PDF 좌표계)")
    pdf_p.add_argument("--post", required=True, help="포스트 슬러그 (예: gpu-arch-1)")
    pdf_p.add_argument("--name", required=True, help="저장할 파일명 (확장자 제외, 예: fig1-sm-structure)")

    # URL 모드
    url_p = sub.add_parser("url", help="웹 URL에서 이미지 다운로드")
    url_p.add_argument("url", help="이미지 URL")
    url_p.add_argument("--post", required=True, help="포스트 슬러그 (예: gpu-arch-1)")
    url_p.add_argument("--name", required=True, help="저장할 파일명 (확장자 제외)")

    args = parser.parse_args()

    if args.mode == "pdf":
        crop = tuple(args.crop) if args.crop else None
        entry = extract_from_pdf(args.pdf_path, args.page, args.post, args.name, crop)
    else:
        entry = download_from_url(args.url, args.post, args.name)

    update_attribution(args.post, entry)

    print(f"\n마크다운 삽입:")
    ext = Path(entry["file"]).suffix
    print(f'![설명 텍스트](/assets/img/posts/{args.post}/{args.name}{ext if args.mode == "url" else ".png"})')


if __name__ == "__main__":
    main()
