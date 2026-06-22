#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib", "numpy"]
# ///
"""
포스트용 기술 다이어그램 생성 스크립트.

에이전트가 직접 호출한다. 포스트 주제에 맞는 다이어그램을
matplotlib으로 생성해 assets/img/posts/<slug>/ 에 저장한다.

지원 타입:
  block       : 블록 구조도 (GPU SM 구조, 메모리 계층 등)
  memory      : 메모리 레이아웃 비교 (before/after)
  timeline    : 타임라인 / 파이프라인
  bar         : 성능 비교 막대그래프
  custom      : --script 로 직접 matplotlib 코드 지정

사용 예시:
  uv run scripts/gen-diagram.py --post gpu-arch-1 --name sm-block --type block --spec spec.json
  uv run scripts/gen-diagram.py --post llm-serving-overview --name paged-attn --type memory --spec spec.json
  uv run scripts/gen-diagram.py --post gpu-arch-1 --name perf-bar --type bar --spec spec.json
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

POSTS_IMG_DIR = Path("assets/img/posts")
DPI = 150

# 한글 지원 폰트 자동 탐색 (macOS Apple SD Gothic Neo 우선)
def _resolve_font() -> str:
    candidates = [
        "Apple SD Gothic Neo",
        "AppleGothic",
        "NanumGothic",
        "D2Coding",
        "DejaVu Sans",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c
    return "DejaVu Sans"

FONT_FAMILY = _resolve_font()
matplotlib.rcParams["font.family"] = FONT_FAMILY


# ── 공통 스타일 ──────────────────────────────────────────────
PALETTE = {
    "blue":    "#4A90D9",
    "green":   "#5BA85A",
    "orange":  "#E07B39",
    "gray":    "#888888",
    "light":   "#F0F4F8",
    "dark":    "#2C3E50",
    "red":     "#C0392B",
    "purple":  "#7D5BA6",
    "border":  "#CCCCCC",
    "bg":      "#FFFFFF",
}

def base_fig(w=10, h=6):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(PALETTE["bg"])
    ax.set_facecolor(PALETTE["bg"])
    ax.axis("off")
    return fig, ax


def draw_box(ax, x, y, w, h, label, sublabel=None,
             fc=None, ec=None, fontsize=11, labelsize=9):
    fc = fc or PALETTE["light"]
    ec = ec or PALETTE["border"]
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0.02",
                         facecolor=fc, edgecolor=ec, linewidth=1.2)
    ax.add_patch(box)
    cy = y + h / 2
    if sublabel:
        ax.text(x + w / 2, cy + h * 0.12, label,
                ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=PALETTE["dark"])
        ax.text(x + w / 2, cy - h * 0.15, sublabel,
                ha="center", va="center", fontsize=labelsize,
                color=PALETTE["gray"])
    else:
        ax.text(x + w / 2, cy, label,
                ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=PALETTE["dark"])


# ── 타입별 생성 함수 ─────────────────────────────────────────

def gen_block(spec: dict, out_path: Path):
    """블록 구조도: spec = {title, groups: [{label, color, items: [{label, sub}]}]}"""
    title  = spec.get("title", "Block Diagram")
    groups = spec.get("groups", [])

    n = len(groups)
    fig, ax = base_fig(w=max(10, n * 3.5), h=7)
    ax.set_xlim(0, n * 3.5)
    ax.set_ylim(0, 7)

    ax.text(n * 1.75, 6.6, title, ha="center", va="center",
            fontsize=14, fontweight="bold", color=PALETTE["dark"])

    gw = 3.0
    for gi, grp in enumerate(groups):
        gx = gi * 3.5 + 0.25
        gy_top = 6.1
        color = PALETTE.get(grp.get("color", "blue"), PALETTE["blue"])

        # 그룹 헤더
        draw_box(ax, gx, gy_top - 0.5, gw, 0.45,
                 grp["label"], fc=color, ec=color, fontsize=10)
        ax.texts[-1].set_color("white")

        # 아이템
        items = grp.get("items", [])
        item_h = min(0.7, (gy_top - 0.6) / max(len(items), 1))
        for ii, item in enumerate(items):
            iy = gy_top - 0.55 - (ii + 1) * (item_h + 0.05)
            draw_box(ax, gx + 0.05, iy, gw - 0.1, item_h,
                     item.get("label", ""), item.get("sub"),
                     fc=PALETTE["light"], ec=color, fontsize=9, labelsize=7)

    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"저장: {out_path}")


def gen_memory(spec: dict, out_path: Path):
    """메모리 레이아웃 비교: spec = {title, before: [{label, size, color}], after: [...]}"""
    title  = spec.get("title", "Memory Layout")
    before = spec.get("before", [])
    after  = spec.get("after", [])

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    fig.patch.set_facecolor(PALETTE["bg"])
    fig.suptitle(title, fontsize=14, fontweight="bold", color=PALETTE["dark"])

    for ax, blocks, subtitle in zip(axes, [before, after], ["Before", "After"]):
        ax.set_facecolor(PALETTE["bg"])
        ax.axis("off")
        ax.set_xlim(0, 1)
        total = sum(b.get("size", 1) for b in blocks)
        y = 0.05
        ax.text(0.5, 0.95, subtitle, ha="center", va="center",
                fontsize=12, fontweight="bold", color=PALETTE["dark"],
                transform=ax.transAxes)
        for b in blocks:
            h = (b.get("size", 1) / total) * 0.85
            color = PALETTE.get(b.get("color", "blue"), PALETTE["blue"])
            rect = mpatches.FancyBboxPatch(
                (0.1, y), 0.8, h,
                boxstyle="round,pad=0.01",
                facecolor=color, edgecolor=PALETTE["border"],
                linewidth=1, alpha=0.85,
                transform=ax.transAxes, clip_on=False)
            ax.add_patch(rect)
            ax.text(0.5, y + h / 2, b.get("label", ""),
                    ha="center", va="center", fontsize=9,
                    fontweight="bold", color="white",
                    transform=ax.transAxes)
            y += h + 0.01

    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"저장: {out_path}")


def gen_bar(spec: dict, out_path: Path):
    """성능 비교 막대그래프: spec = {title, xlabel, ylabel, groups: [{label, values, colors}], categories: [...]}"""
    import numpy as np

    title      = spec.get("title", "Performance")
    xlabel     = spec.get("xlabel", "")
    ylabel     = spec.get("ylabel", "")
    groups     = spec.get("groups", [])
    categories = spec.get("categories", [f"C{i}" for i in range(4)])

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(PALETTE["bg"])
    ax.set_facecolor(PALETTE["bg"])

    n_cat = len(categories)
    n_grp = len(groups)
    x = np.arange(n_cat)
    width = 0.8 / max(n_grp, 1)

    for gi, grp in enumerate(groups):
        color = PALETTE.get(grp.get("color", "blue"), PALETTE["blue"])
        offset = (gi - n_grp / 2 + 0.5) * width
        ax.bar(x + offset, grp.get("values", [0] * n_cat),
               width=width * 0.9, label=grp.get("label", f"G{gi}"),
               color=color, alpha=0.85, edgecolor=PALETTE["border"])

    ax.set_title(title, fontsize=14, fontweight="bold", color=PALETTE["dark"], pad=12)
    ax.set_xlabel(xlabel, fontsize=11, color=PALETTE["gray"])
    ax.set_ylabel(ylabel, fontsize=11, color=PALETTE["gray"])
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=10)
    ax.legend(fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"저장: {out_path}")


def gen_timeline(spec: dict, out_path: Path):
    """파이프라인/타임라인: spec = {title, rows: [{label, segments: [{start, end, label, color}]}]}"""
    title = spec.get("title", "Timeline")
    rows  = spec.get("rows", [])
    total_time = spec.get("total_time", 10)

    fig, ax = base_fig(w=12, h=max(4, len(rows) * 1.2 + 2))
    ax.set_xlim(-0.5, total_time + 0.5)
    ax.set_ylim(-0.5, len(rows) + 0.5)

    ax.text(total_time / 2, len(rows) + 0.2, title,
            ha="center", va="bottom", fontsize=14,
            fontweight="bold", color=PALETTE["dark"])

    for ri, row in enumerate(rows):
        y = len(rows) - ri - 1
        ax.text(-0.4, y + 0.5, row["label"], ha="right", va="center",
                fontsize=10, color=PALETTE["dark"])
        for seg in row.get("segments", []):
            color = PALETTE.get(seg.get("color", "blue"), PALETTE["blue"])
            x0, x1 = seg["start"], seg["end"]
            rect = mpatches.FancyBboxPatch(
                (x0, y + 0.1), x1 - x0, 0.8,
                boxstyle="round,pad=0.02",
                facecolor=color, edgecolor="white",
                linewidth=1, alpha=0.85)
            ax.add_patch(rect)
            if x1 - x0 > 0.5:
                ax.text((x0 + x1) / 2, y + 0.5, seg.get("label", ""),
                        ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold")

    ax.set_xlabel("Time", fontsize=10, color=PALETTE["gray"])
    ax.xaxis.set_visible(True)
    ax.yaxis.set_visible(False)
    ax.spines[["top", "right", "left"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"저장: {out_path}")


# ── 메인 ─────────────────────────────────────────────────────

GENERATORS = {
    "block":    gen_block,
    "memory":   gen_memory,
    "bar":      gen_bar,
    "timeline": gen_timeline,
}


def main():
    parser = argparse.ArgumentParser(description="포스트용 기술 다이어그램 생성")
    parser.add_argument("--post", required=True, help="포스트 슬러그 (예: gpu-arch-1)")
    parser.add_argument("--name", required=True, help="파일명 (확장자 제외)")
    parser.add_argument("--type", required=True, choices=list(GENERATORS),
                        help="다이어그램 타입")
    parser.add_argument("--spec", required=True,
                        help="다이어그램 명세 JSON 파일 경로")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"오류: spec 파일 없음 — {spec_path}")
        sys.exit(1)

    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    out_dir = POSTS_IMG_DIR / args.post
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name}.png"

    GENERATORS[args.type](spec, out_path)

    # attribution 기록
    attr_path = out_dir / "attribution.md"
    lines = attr_path.read_text(encoding="utf-8").splitlines() if attr_path.exists() else [
        f"# {args.post} 이미지 출처\n",
    ]
    lines += [f"\n## {args.name}.png",
              "- **source_type**: generated",
              f"- **spec**: {args.spec}",
              "- **license**: original (no restrictions)"]
    attr_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n마크다운 삽입:")
    print(f"![{spec.get('title', args.name)}](/assets/img/posts/{args.post}/{args.name}.png)")


if __name__ == "__main__":
    main()
