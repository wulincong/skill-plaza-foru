"""courseware-studio 构建链测试（stdlib unittest，可直接 python3 -m unittest）。"""
from __future__ import annotations

import json
import posixpath
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from spec_model import SpecError, appendix_pages, load_spec  # noqa: E402
import build_pptx  # noqa: E402
import build_preview  # noqa: E402

EXAMPLE = SKILL / "tests" / "examples" / "valid-spec.json"


def make_workspace(tmp: Path) -> Path:
    """复制示例 spec 引用的 uploads 文件到临时工作区。"""
    ws = tmp / "ws"
    (ws / "uploads").mkdir(parents=True)
    (ws / "uploads" / "textbook-ch4.pdf").write_bytes(b"%PDF-1.4 placeholder")
    (ws / "uploads" / "training-guide-task3.md").write_text("# 任务三\n安全须知……", encoding="utf-8")
    try:
        from PIL import Image
        Image.new("RGB", (320, 200), (200, 60, 30)).save(ws / "uploads" / "tool-flange.png")
    except ImportError:
        (ws / "uploads" / "tool-flange.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return ws


def load_example(workspace: Path):
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class SpecModelTests(unittest.TestCase):
    def test_valid_spec(self):
        data = load_example(None)
        spec = load_spec(data)
        self.assertEqual(spec["version"], "courseware-spec/1")

    def test_missing_materials(self):
        data = load_example(None)
        del data["materials"]
        with self.assertRaisesRegex(SpecError, "materials"):
            load_spec(data)

    def test_factual_page_requires_sources(self):
        data = load_example(None)
        data["slides"][2]["sources"] = []
        with self.assertRaisesRegex(SpecError, "出处"):
            load_spec(data)

    def test_cover_blocks_forbidden(self):
        data = load_example(None)
        data["slides"][0]["blocks"] = [{"kind": "bullets", "items": ["x"]}]
        with self.assertRaisesRegex(SpecError, "封面"):
            load_spec(data)

    def test_unknown_standard(self):
        data = load_example(None)
        data["slides"][2]["knowledgePoints"][0]["standardId"] = "S9"
        with self.assertRaisesRegex(SpecError, "standardId"):
            load_spec(data)

    def test_safety_requires_confirmations(self):
        data = load_example(None)
        data["pendingConfirmations"] = []
        with self.assertRaisesRegex(SpecError, "pendingConfirmations"):
            load_spec(data)

    def test_final_requires_confirmation_records(self):
        data = load_example(None)
        data["meta"]["final"] = True
        with self.assertRaisesRegex(SpecError, "定稿"):
            load_spec(data)
        data["confirmations"] = [
            {"id": "C1", "decision": "confirmed", "note": "第一轮确认"},
            {"id": "C2", "decision": "confirmed", "note": "第一轮确认"},
        ]
        load_spec(data)  # 补齐确认记录后通过

    def test_file_existence_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = make_workspace(Path(tmp))
            data = load_example(None)
            data["materials"][0]["file"] = "uploads/missing.pdf"
            with self.assertRaisesRegex(SpecError, "不存在"):
                load_spec(data, ws)

    def test_appendix_pages_derived(self):
        spec = load_example(None)
        titles = [title for title, _ in appendix_pages(spec)]
        self.assertTrue(any("出处" in t for t in titles))
        self.assertTrue(any("版权" in t for t in titles))
        self.assertTrue(any("确认" in t for t in titles))


class PptxBuildTests(unittest.TestCase):
    def build(self, tmp: Path):
        ws = make_workspace(tmp)
        spec = load_spec(load_example(None), ws)
        out = tmp / "courseware.pptx"
        count = build_pptx.write_pptx(spec, out, ws)
        return ws, spec, out, count

    def test_structure_and_rels_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws, spec, out, count = self.build(Path(tmp))
            self.assertTrue(out.is_file())
            slides_expected = len(spec["slides"]) + len(appendix_pages(spec))
            self.assertEqual(count, slides_expected)
            with zipfile.ZipFile(out) as zf:
                names = set(zf.namelist())
                # 1) 全部 XML 良构
                for name in names:
                    if name.endswith((".xml", ".rels")):
                        ET.fromstring(zf.read(name))
                # 2) 关系图闭合：每个 rels 的 target 都存在
                for name in [n for n in names if n.endswith(".rels")]:
                    base = Path(name).parent.parent
                    rels = ET.fromstring(zf.read(name))
                    for rel in rels:
                        if rel.get("TargetMode") == "External":
                            continue
                        target = posixpath.normpath((base / rel.get("Target")).as_posix())
                        self.assertIn(target, names, f"{name} -> {target} 缺失")
                # 3) 每张 slide 均引用版式；slide 数与 content-types 一致
                ct = zf.read("[Content_Types].xml").decode("utf-8")
                slides = [n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
                self.assertEqual(len(slides), slides_expected)
                for i in range(1, slides_expected + 1):
                    self.assertIn(f"/ppt/slides/slide{i}.xml", ct)
                # 4) 图片进入 media 且被 slide 引用
                media = [n for n in names if n.startswith("ppt/media/")]
                self.assertTrue(any(m.endswith(".png") for m in media))
                slide4 = zf.read("ppt/slides/slide5.xml").decode("utf-8")
                self.assertIn("r:embed", slide4)

    def test_footer_carries_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws, spec, out, _ = self.build(Path(tmp))
            with zipfile.ZipFile(out) as zf:
                slide4 = zf.read("ppt/slides/slide5.xml").decode("utf-8")
                self.assertIn("来源", slide4)
                draft = zf.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertIn("校订稿", draft)


class PreviewBuildTests(unittest.TestCase):
    def test_preview_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ws = make_workspace(tmp)
            spec = load_spec(load_example(None), ws)
            site = tmp / "site"
            site.mkdir()
            count = build_preview.build_preview(spec, site, ws)
            html = (site / "index.html").read_text(encoding="utf-8")
            expected = len(spec["slides"]) + len(appendix_pages(spec))
            self.assertEqual(count, expected)
            self.assertEqual(html.count('<section class="slide'), expected)
            self.assertIn("来源", html)
            self.assertIn("教师待确认清单", html)
            self.assertIn("资源入库清单", html)
            self.assertIn("版权与授权", html)
            self.assertIn("待教师补充", html)
            self.assertIn("校订稿", html)
            self.assertTrue((site / "assets" / "figure1.png").is_file())


if __name__ == "__main__":
    unittest.main()
