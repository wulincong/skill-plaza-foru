"""把课件成品原子登记进会话工作区 delivery.json（对齐平台 088 交付契约）。

先生成全部产物再调用本脚本；web[] 指向 output/site 目录，files[] 逐个
登记工作区内的交付文件（含 sha256，便于服务端指纹一致时稳定去重）。
清单最后原子替换，任何校验失败都保持旧清单不变。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


def _check_within(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or resolved.is_symlink():
        raise ValueError(f"{label} 必须位于工作区内且不能是符号链接：{path}")
    return resolved


def register(web_directory: Path, files: list[tuple[str, Path]], workspace: Path):
    root = workspace.resolve()
    site = _check_within(web_directory, root, "网页目录")
    entry = site / "index.html"
    if not entry.is_file():
        raise ValueError(f"网页入口不存在：{entry}")
    manifest_files = []
    for name, path in files:
        target = _check_within(path, root, "交付文件")
        if not target.is_file():
            raise ValueError(f"交付文件不存在：{path}")
        manifest_files.append({
            "name": name,
            "path": target.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
    manifest = root / "delivery.json"
    data = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    relative = site.relative_to(root).as_posix()
    web = [item for item in data.get("web", []) if item.get("directory") != relative]
    web.append({"name": "课件网页预览", "directory": relative, "entry": "index.html"})
    data["web"] = web
    data["files"] = manifest_files
    fd, scratch = tempfile.mkstemp(prefix=".delivery-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.chmod(scratch, 0o640)
        os.replace(scratch, manifest)
    finally:
        Path(scratch).unlink(missing_ok=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("web_directory", type=Path, help="网页目录（工作区相对，如 output/site）")
    parser.add_argument("--file", action="append", default=[], metavar="NAME=PATH",
                        help="交付文件，可重复，如 \"课件成品=courseware.pptx\"")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    files = []
    for item in args.file:
        name, sep, path = item.partition("=")
        if not sep or not name or not path:
            parser.error(f"--file 需要 NAME=PATH 形式：{item}")
        files.append((name, Path(path)))
    try:
        manifest = register(args.web_directory, files, args.workspace)
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok", "manifest": str(manifest)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
