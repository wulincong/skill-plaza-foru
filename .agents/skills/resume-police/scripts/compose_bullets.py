"""Compose resume bullets from excerpts found in the candidate's source text."""

import argparse
import json
import sys
from pathlib import Path


def compose(source, bullets):
    if not isinstance(source, str) or not source.strip():
        raise ValueError("缺少候选人原文")
    if not isinstance(bullets, list) or not bullets:
        raise ValueError("bullets 应为非空条目列表")

    lines = []
    for index, excerpts in enumerate(bullets, start=1):
        if not isinstance(excerpts, list) or not excerpts:
            raise ValueError(f"第 {index} 条缺少原文摘录")
        parts = []
        for excerpt in excerpts:
            if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in source:
                raise ValueError(f"第 {index} 条含无法在原文定位的片段，请删去或改为稿外追问")
            parts.append(excerpt.strip().rstrip("，。；,;"))
        lines.append("- " + "，".join(parts) + "。")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="原始 UTF-8 简历或已提取的正文")
    args = parser.parse_args()
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("输入须为含 bullets 的 JSON 对象")
        source = args.source.read_text(encoding="utf-8-sig") if args.source else data.get("source")
        print(compose(source, data.get("bullets")))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
