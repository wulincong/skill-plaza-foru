"""Read-only WeKnora retrieval for trusted local skill callers."""

import argparse
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://kb.tringai.cn/api/v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PREVIEW_CHARS = 2000
ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


class RetrievalError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def require_api_shape(condition):
    if not condition:
        raise RetrievalError("unavailable", "上游响应不符合预期，未返回未经核对的数据。")


def check_scope(row, kb, document=None):
    if row.get("knowledge_base_id") != kb or (
        document is not None and row.get("knowledge_id") != document
    ):
        raise RetrievalError("forbidden", "返回记录不属于指定范围。")


class WeKnora:
    def __init__(self):
        self.key = os.environ.get("WEKNORA_API_KEY", "").strip()
        ids = [item.strip() for item in os.environ.get("WEKNORA_KB_IDS", "").split(",")]
        if not self.key or not all(ID.fullmatch(item) for item in ids):
            raise RetrievalError("configuration_error", "请配置 WEKNORA_API_KEY 和 WEKNORA_KB_IDS。")
        self.bases = list(dict.fromkeys(ids))
        self.http = urllib.request.build_opener(NoRedirect)

    def request(self, path, *, params=None, body=None):
        url = f"{API_BASE}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, data=json.dumps(body).encode() if body is not None else None,
            headers={"X-API-Key": self.key, "Content-Type": "application/json"},
        )
        try:
            with self.http.open(req, timeout=30) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            require_api_shape(len(raw) <= MAX_RESPONSE_BYTES)
            result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            status = {400: "invalid_request", 401: "unauthorized", 403: "forbidden",
                      404: "not_found"}.get(exc.code, "unavailable")
            raise RetrievalError(status, f"WeKnora 返回 HTTP {exc.code}。") from None
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise RetrievalError("unavailable", f"WeKnora 请求失败（{type(exc).__name__}）。") from None
        require_api_shape(isinstance(result, dict) and result.get("success") is True and "data" in result)
        return result

    def document(self, kb, document):
        row = self.request(f"knowledge/{document}")["data"]
        require_api_shape(isinstance(row, dict) and row.get("id") == document)
        check_scope(row, kb)
        return row


def rows(response):
    data = response["data"]
    if data is None:  # An empty Go slice can be encoded as null.
        return []
    require_api_shape(isinstance(data, list) and all(isinstance(row, dict) for row in data))
    return data


def select(row, *fields):
    return {field: row.get(field) for field in fields}


def search_hits(client, kb, query, document):
    scope = {"knowledge_ids": [document]} if document else {"knowledge_base_id": kb}
    response = client.request("knowledge-search", body={**scope, "query": query})
    items = []
    for row in rows(response):
        check_scope(row, kb, document)
        require_api_shape(row.get("id") and row.get("knowledge_id") and isinstance(row.get("content"), str))
        item = select(row, "knowledge_base_id", "knowledge_id", "knowledge_title", "id", "chunk_index", "score")
        matched = row.get("matched_content")
        field = "matched_content" if isinstance(matched, str) and matched.strip() else "content"
        item["preview_field"] = field
        item["preview"] = row[field][:PREVIEW_CHARS]
        item["truncated"] = len(row[field]) > PREVIEW_CHARS
        items.append(item)
    return {"items": items}


def read_page(client, args, document):
    params = {"page": args.page, "page_size": 20 if args.operation == "documents" else 5}
    if args.operation == "documents":
        if args.keyword:
            params["keyword"] = args.keyword
        path = f"knowledge-bases/{args.kb}/knowledge"
        fields = ("id", "knowledge_base_id", "title", "file_name", "parse_status")
    else:
        path = f"chunks/{document}"
        fields = ("id", "knowledge_base_id", "knowledge_id", "chunk_index", "content")
    response = client.request(path, params=params)
    items = []
    for row in rows(response):
        check_scope(row, args.kb, document)
        require_api_shape(row.get("id") and (document is None or isinstance(row.get("content"), str)))
        items.append(select(row, *fields))
    total = response.get("total")
    size = response.get("page_size")
    require_api_shape(isinstance(total, int) and total >= 0 and isinstance(size, int) and size > 0
                      and response.get("page") == args.page)
    return {"items": items, "total": total, "page": args.page,
            "next_page": args.page + 1 if args.page * size < total else None}


def retrieve(client, args):
    if args.operation == "bases":
        items = []
        for kb in client.bases:
            row = client.request(f"knowledge-bases/{kb}")["data"]
            require_api_shape(isinstance(row, dict) and row.get("id") == kb)
            items.append(select(row, "id", "name", "type", "knowledge_count"))
        return {"items": items}

    if args.kb not in client.bases:
        raise RetrievalError("forbidden", "知识库不在本次调用的授权范围内。")
    document = getattr(args, "document", None)
    doc = None
    if document is not None:
        if not ID.fullmatch(document):
            raise RetrievalError("invalid_request", "文档 ID 无效。")
        doc = client.document(args.kb, document)
    if args.operation == "search":
        return search_hits(client, args.kb, args.query, document)
    result = read_page(client, args, document)
    if doc:
        result["knowledge_title"] = doc.get("title") or doc.get("file_name")
    return result


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RetrievalError("invalid_request", message)


def search_text(value):
    text = value.strip()
    if not text or len(text) > 2000:
        raise argparse.ArgumentTypeError("搜索词需要 1 到 2000 个字符")
    return text


def page_number(value):
    page = int(value)
    if page < 1:
        raise argparse.ArgumentTypeError("页码从 1 开始")
    return page


def main():
    parser = Parser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("bases")
    docs = commands.add_parser("documents")
    search = commands.add_parser("search")
    chunks = commands.add_parser("chunks")
    for command in (docs, search, chunks):
        command.add_argument("--kb", required=True)
    for command in (docs, chunks):
        command.add_argument("--page", type=page_number, default=1)
    docs.add_argument("--keyword", type=search_text)
    search.add_argument("--query", required=True, type=search_text)
    search.add_argument("--document")
    chunks.add_argument("--document", required=True)
    try:
        args = parser.parse_args()
        result = retrieve(WeKnora(), args)
        result["status"] = "ok" if result["items"] else "empty"
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except RetrievalError as exc:
        print(json.dumps({"status": exc.status, "message": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
