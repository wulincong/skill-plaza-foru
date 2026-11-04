"""Regression coverage for document scope and evidence returned by the local CLI."""

import io
import json
import os
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import retrieve


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.enter_patch(patch.dict(os.environ, {"WEKNORA_API_KEY": "test-value", "WEKNORA_KB_IDS": "kb1"}))
        self.open = self.enter_patch(patch("urllib.request.OpenerDirector.open"))

    def enter_patch(self, patcher):
        self.addCleanup(patcher.stop)
        return patcher.start()

    def cli(self, *args):
        out = io.StringIO()
        with patch.object(sys, "argv", ["retrieve.py", *args]), redirect_stdout(out):
            code = retrieve.main()
        return code, json.loads(out.getvalue())

    @staticmethod
    def response(data, **meta):
        return io.BytesIO(json.dumps({"success": True, "data": data, **meta}).encode())

    def test_deny_unknown_library_before_any_request(self):
        code, result = self.cli("search", "--kb", "kb2", "--query", "topic")
        self.assertEqual((code, result["status"]), (1, "forbidden"))
        self.open.assert_not_called()

    def test_document_from_different_library_is_not_searched(self):
        self.open.return_value = self.response({"id": "doc", "knowledge_base_id": "kb2"})
        code, result = self.cli("search", "--kb", "kb1", "--document", "doc", "--query", "topic")
        self.assertEqual((code, result["status"]), (1, "forbidden"))
        self.assertEqual(self.open.call_count, 1)

    def test_document_search_sends_only_document_scope_and_bounds_preview(self):
        self.open.side_effect = [
            self.response({"id": "doc", "knowledge_base_id": "kb1"}),
            self.response([{"id": "chunk", "knowledge_id": "doc", "knowledge_base_id": "kb1",
                            "chunk_index": 0, "content": "文" * 2500}]),
        ]
        code, result = self.cli("search", "--kb", "kb1", "--document", "doc", "--query", "topic")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(self.open.call_args.args[0].data), {"knowledge_ids": ["doc"], "query": "topic"})
        hit, = result["items"]
        self.assertTrue(hit["truncated"])
        self.assertEqual(len(hit["preview"]), retrieve.PREVIEW_CHARS)
        self.assertEqual((hit["knowledge_id"], hit["id"], hit["chunk_index"]), ("doc", "chunk", 0))

    def test_chunks_reject_record_from_another_document(self):
        self.open.side_effect = [
            self.response({"id": "doc", "knowledge_base_id": "kb1"}),
            self.response([{"id": "chunk", "knowledge_id": "other", "knowledge_base_id": "kb1",
                            "content": "outside"}], page=1, page_size=5, total=1),
        ]
        code, result = self.cli("chunks", "--kb", "kb1", "--document", "doc")
        self.assertEqual((code, result["status"]), (1, "forbidden"))
        self.assertNotIn("items", result)

    def test_empty_keeps_success_exit_and_missing_data_fails(self):
        self.open.side_effect = [self.response(None), io.BytesIO(b'{"success":true}')]
        code, result = self.cli("search", "--kb", "kb1", "--query", "topic")
        self.assertEqual((code, result["status"], result["items"]), (0, "empty", []))
        code, result = self.cli("search", "--kb", "kb1", "--query", "topic")
        self.assertEqual((code, result["status"]), (1, "unavailable"))

    def test_errors_hide_upstream_body(self):
        for http_code, status in ((401, "unauthorized"), (403, "forbidden"), (503, "unavailable")):
            with self.subTest(http_code=http_code):
                self.open.side_effect = HTTPError("https://example.invalid", http_code, "test-value",
                                                  {}, io.BytesIO(b"test-value"))
                code, result = self.cli("bases")
                self.assertEqual((code, result["status"]), (1, status))
                self.assertNotIn("test-value", str(result))


if __name__ == "__main__":
    unittest.main()
