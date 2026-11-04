import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compose_bullets.py"


def compose(data, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=json.dumps(data, ensure_ascii=False),
        capture_output=True,
        text=True,
    )


class ComposeBulletsTest(unittest.TestCase):
    def test_pasted_text_keeps_roles_and_missing_result(self):
        result = compose({
            "source": "我对比了执行计划，索引由同事添加。未记录耗时。",
            "bullets": [["对比了执行计划", "索引由同事添加"], ["未记录耗时"]],
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "- 对比了执行计划，索引由同事添加。\n- 未记录耗时。\n")

    def test_invented_result_rejects_the_entire_batch(self):
        result = compose({
            "source": "提交了复现步骤，未跟踪修复结果。",
            "bullets": [["提交了复现步骤"], ["确认修复成功"]],
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_attachment_takes_precedence_over_pasted_text(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "经历.md"
            source.write_text("我整理了重复工单。", encoding="utf-8-sig")
            data = {"source": "我修改了规则。", "bullets": [["整理了重复工单"]]}
            result = compose(data, "--source", source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "- 整理了重复工单。\n")
            result = compose({**data, "bullets": [["修改了规则"]]}, "--source", source)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
