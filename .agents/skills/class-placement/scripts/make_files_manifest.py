#!/usr/bin/env python3
"""为一次分班产物生成 register_delivery.py 的 --files-from 清单。

用法（在会话工作区运行）：
    python3 <技能目录>/scripts/make_files_manifest.py output/placement-<时间戳> --out files.json

扫描输出目录下的 result.json、audit/manifest.json、audit/solver-log.jsonl 与 roster/*.csv，
写 {"files": [{name, path, sha256}]}，名称用可直接公示的中文。
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="生成分班交付文件清单")
    ap.add_argument("out_dir", type=Path, help="assign.py 的 --out 输出目录")
    ap.add_argument("--out", type=Path, required=True, help="清单写入路径（如 files.json）")
    args = ap.parse_args()

    root = args.out_dir.resolve()
    if not root.is_dir():
        print(f"make_files_manifest.py: 目录不存在：{args.out_dir}", file=sys.stderr)
        raise SystemExit(2)
    workspace = Path.cwd().resolve()
    if not root.is_relative_to(workspace):
        print("make_files_manifest.py: 输出目录必须位于当前工作区内", file=sys.stderr)
        raise SystemExit(2)

    files = []

    def add(path: Path, name: str):
        if path.is_file() and path.stat().st_size:
            files.append({"name": name, "path": path.relative_to(workspace).as_posix(), "sha256": sha256_file(path)})

    add(root / "result.json", "分班结果与统计（JSON）")
    add(root / "audit" / "manifest.json", "审计清单：种子、指纹与复现命令")
    add(root / "audit" / "solver-log.jsonl", "求解日志（哈希链）")
    roster = sorted((root / "roster").glob("*.csv")) if (root / "roster").is_dir() else []
    for csv_path in sorted(roster, key=lambda p: p.name):
        name = "全员分班名册" if csv_path.name == "roster-all.csv" else f"班级名册·{csv_path.stem.split('-', 1)[1] if '-' in csv_path.stem else csv_path.stem}"
        add(csv_path, name)

    if not files:
        print("make_files_manifest.py: 未找到可登记的产物文件", file=sys.stderr)
        raise SystemExit(2)
    args.out.write_text(json.dumps({"files": files}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(args.out), "files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
