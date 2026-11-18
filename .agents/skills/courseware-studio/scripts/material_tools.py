"""教师材料读取工具：按页提取文本、清点/提取教材图片。

子命令：
  text <file> [--pages m-n]   逐页文本（pdftotext，按换页符切页；md/txt/docx 原样分段）
  images <pdf> [--out DIR] [--min-bytes N]  pdfimages 清点并提取较大嵌入图（默认 >=48KB）
  read <file>                 按扩展名自动分派

输出 JSON（status=ok/empty），失败时 stderr 给原因、退出码非 0。
出处需要页码锚定：PDF 文本每页带 page 字段，引用时写「教材 p.N」。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

MIN_IMAGE_BYTES = 48 * 1024
TEXT_BATCH_PAGES = 20


def _emit(payload):
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("status") == "ok" else 1


def _pages_from_pdf(path: Path, first: int, last: int) -> list[dict]:
    # -layout 保留视觉对齐，便于对照教材版面核页码
    result = subprocess.run(
        ["pdftotext", "-layout", "-f", str(first), "-l", str(last), str(path), "-"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext 失败：{result.stderr.strip()[:200]}")
    chunks = result.stdout.split("\f")
    pages = []
    for offset, chunk in enumerate(chunks):
        text = chunk.strip("\n")
        if text.strip():
            pages.append({"page": first + offset, "text": text})
    return pages


def _docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def cmd_text(path: Path, pages: str | None) -> int:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True)
        if info.returncode != 0:
            raise RuntimeError(f"pdfinfo 失败：{info.stderr.strip()[:200]}")
        match = re.search(r"^Pages:\s+(\d+)$", info.stdout, re.MULTILINE)
        total = int(match.group(1)) if match else 0
        if pages:
            first, last = (int(x) for x in pages.split("-"))
        else:
            first, last = 1, total
        last = min(last, total)
        entries = []
        cursor = first
        while cursor <= last:  # 分批提取，避免整本教材一次性进上下文
            batch_last = min(cursor + TEXT_BATCH_PAGES - 1, last)
            entries += _pages_from_pdf(path, cursor, batch_last)
            cursor = batch_last + 1
        if not entries:
            return _emit({"status": "empty", "reason": "PDF 无文本层（可能是扫描件）", "pages": total})
        return _emit({"status": "ok", "kind": "pdf", "pages": total, "entries": entries})
    if suffix in (".md", ".txt"):
        text = path.read_text(encoding="utf-8", errors="replace")
        return _emit({"status": "ok", "kind": "text", "entries": [{"page": 1, "text": text}]})
    if suffix == ".docx":
        text = _docx_text(path)
        return _emit({"status": "ok", "kind": "docx", "entries": [{"page": 1, "text": text}]})
    raise RuntimeError(f"不支持的文本材料格式：{suffix}（支持 pdf/docx/md/txt）")


def cmd_images(path: Path, out: Path, min_bytes: int) -> int:
    if path.suffix.lower() != ".pdf":
        raise RuntimeError("images 只处理 PDF 教材")
    if shutil.which("pdfimages") is None:
        raise RuntimeError("系统缺少 pdfimages（poppler-utils）")
    listing = subprocess.run(
        ["pdfimages", "-list", str(path)], capture_output=True, text=True, timeout=120,
    )
    if listing.returncode != 0:
        raise RuntimeError(f"pdfimages -list 失败：{listing.stderr.strip()[:200]}")
    header, rows = None, []
    for line in listing.stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "page":
            header = fields
            continue
        if header is None or len(fields) < len(header):
            continue
        try:
            row = dict(zip(header, fields))
            if row.get("type") != "image":
                continue
            rows.append({"page": int(row["page"]), "enc": row.get("enc", ""),
                         "width": int(row["width"]), "height": int(row["height"])})
        except (KeyError, ValueError):
            continue
    out.mkdir(parents=True, exist_ok=True)
    extracted = []
    with tempfile.TemporaryDirectory(prefix="cw-imgs-") as tmp:
        result = subprocess.run(
            ["pdfimages", "-all", str(path), f"{tmp}/img"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pdfimages 提取失败：{result.stderr.strip()[:200]}")
        blobs = sorted(Path(tmp).glob("img-*"))
        index = 0
        for row in rows:
            if row["width"] * row["height"] < 400 * 300:
                continue
            if index >= len(blobs):
                break
            blob = blobs[index]
            index += 1
            if blob.stat().st_size < min_bytes:
                continue
            target = out / f"p{row['page']:03d}-{blob.name}"
            shutil.copyfile(blob, target)
            extracted.append({
                "page": row["page"], "file": str(target),
                "width": row["width"], "height": row["height"],
                "bytes": target.stat().st_size,
            })
    if not extracted:
        return _emit({"status": "empty", "reason": "未找到尺寸/体积达标的嵌入图（≥400×300 且 ≥48KB）"})
    return _emit({"status": "ok", "count": len(extracted), "images": extracted})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_text = sub.add_parser("text", help="逐页提取文本")
    p_text.add_argument("file", type=Path)
    p_text.add_argument("--pages", help="页码区间，如 58-72；缺省全册")
    p_img = sub.add_parser("images", help="清点并提取教材嵌入图")
    p_img.add_argument("file", type=Path)
    p_img.add_argument("--out", type=Path, default=Path("material-images"))
    p_img.add_argument("--min-bytes", type=int, default=MIN_IMAGE_BYTES)
    p_read = sub.add_parser("read", help="按扩展名自动分派（等价 text）")
    p_read.add_argument("file", type=Path)
    p_read.add_argument("--pages")
    args = parser.parse_args(argv)
    try:
        if args.command in ("text", "read"):
            return cmd_text(args.file, getattr(args, "pages", None))
        return cmd_images(args.file, args.out, args.min_bytes)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        return _emit({"status": "error", "message": str(error)})


if __name__ == "__main__":
    raise SystemExit(main())
