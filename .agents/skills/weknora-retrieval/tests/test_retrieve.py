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

    def test_bases_without_allowlist(self):
        with patch.dict(os.environ, {"WEKNORA_KB_IDS": ""}):
            self.open.return_value = self.response([{"id": "kb2", "name": "Example"}])
            code, result = self.cli("bases")
        self.assertEqual((code, result["items"][0]["id"]), (0, "kb2"))

    def test_config_loading_and_environment_override(self):
        with patch.object(retrieve, "local_config", return_value={"WEKNORA_API_KEY": "local"}), patch.dict(os.environ, {"WEKNORA_KB_IDS": ""}):
            self.assertEqual(retrieve.WeKnora().key, "test-value")
            with patch.dict(os.environ):
                del os.environ["WEKNORA_API_KEY"]
                self.assertEqual(retrieve.WeKnora().key, "local")

    def test_tags_nested_pagination(self):
        self.open.return_value = self.response({"data": [{"id": "tag1", "knowledge_base_id": "kb1", "name": "Course", "knowledge_count": 1}], "total": 21, "page": 1, "page_size": 20})
        code, result = self.cli("tags", "--kb", "kb1")
        self.assertEqual((code, result["next_page"]), (0, 2))
        self.assertEqual(result["items"][0]["name"], "Course")

    def test_tagged_documents_have_urls_and_validate_tag(self):
        self.open.side_effect = [
            self.response({"data": [{"id": "tag1", "knowledge_base_id": "kb1", "name": "Course"}], "total": 1, "page": 1, "page_size": 20}),
            self.response([{"id": "doc", "knowledge_base_id": "kb1", "tag_id": "tag1", "title": "Book"}], total=1, page=1, page_size=20),
        ]
        code, result = self.cli("documents", "--kb", "kb1", "--tag", "tag1")
        self.assertEqual(code, 0)
        self.assertIn("tag_id=tag1", self.open.call_args.args[0].full_url)
        self.assertTrue(result["items"][0]["preview_api_url"].endswith("/knowledge/doc/preview"))

    def test_wrong_tag_results_are_rejected(self):
        self.open.side_effect = [
            self.response({"data": [{"id": "tag1", "knowledge_base_id": "kb1"}], "total": 1, "page": 1, "page_size": 20}),
            self.response([{"id": "doc", "knowledge_base_id": "kb1", "tag_id": "other"}], total=1, page=1, page_size=20),
        ]
        code, result = self.cli("documents", "--kb", "kb1", "--tag", "tag1")
        self.assertEqual((code, result["status"]), (1, "forbidden"))

    def test_search_question_match_keeps_answer_content(self):
        self.open.return_value = self.response([{"id": "chunk", "knowledge_id": "doc", "knowledge_base_id": "kb1", "content": "The answer is router", "matched_content": "What is the router?"}])
        code, result = self.cli("search", "--kb", "kb1", "--query", "router")
        self.assertEqual(code, 0)
        self.assertEqual(result["items"][0]["content_preview"], "The answer is router")

    def test_runtime_library_without_allowlist(self):
        with patch.dict(os.environ, {"WEKNORA_KB_IDS": ""}):
            self.open.return_value = self.response([])
            code, result = self.cli("search", "--kb", "kb2", "--query", "topic")
        self.assertEqual((code, result["status"]), (0, "empty"))
        self.assertEqual(json.loads(self.open.call_args.args[0].data)["knowledge_base_id"], "kb2")

    def test_invalid_library_rejected_before_request(self):
        code, result = self.cli("search", "--kb", "../bad", "--query", "topic")
        self.assertEqual((code, result["status"]), (1, "invalid_request"))
        self.open.assert_not_called()

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
