# -*- coding: utf-8 -*-
"""
edit_server.py — Skill 人工编辑台（本地网页编辑器，写回真实文件）
用法:
    python scripts/edit_server.py            # http://127.0.0.1:8870/
仅监听本机；只允许编辑白名单内的指导文件（不含任何密码/令牌文件）。
"""
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8870

# 可编辑文件白名单：路径 → (分组, 改完跑什么)
EDITABLE = {
    'SKILL.md': ('总纲', '影响下次 agent 执行流程'),
    'references/copywriting.md': ('规范文档', '影响下次生成大纲的文案'),
    'references/data-aggregation.md': ('规范文档', '影响数据口径说明'),
    'references/image-spec.md': ('规范文档', '影响版式说明'),
    'references/chart-gallery.md': ('规范文档', '影响图表选型说明'),
    'references/article-styles.md': ('规范文档', '影响导语风格'),
    'references/research-benchmarks.md': ('规范文档', '研究基准对照'),
    'references/reference-report-robotics.md': ('规范文档', '机器人参考报告解剖'),
    'references/wechat-publishing.md': ('规范文档', '公众号推送/卡片封面/踩坑手册'),
    'assets/brand.json': ('配置资产', '改完跑 gen_outline.py 再渲染'),
    'assets/curriculum_map.json': ('配置资产', '改完跑 gen_outline.py 再渲染'),
    'assets/mp_config.example.json': ('配置资产', '推草稿前复制为 mp_config.json'),
    'assets/mp_config.json': ('配置资产', '填好AppSecret保存后，回来跑 publish_draft.py'),
    'assets/themes.json': ('配置资产', '改色后重跑 render_report.py --theme 对应名'),
    'output/outline/report_outline.json': ('当次产出', '改完跑 render_report.py'),
    'output/article/article.md': ('当次产出', '直接可用的公众号文案'),
}

PAGE = u"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Skill 人工编辑台</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { display:flex; height:100vh; font-family:'Microsoft YaHei',sans-serif;
  background:#F3F5F9; color:#1F2937; }
aside { width:300px; background:#0F2167; color:#fff; overflow-y:auto;
  padding:18px 0 40px; flex:none; }
aside h1 { font-size:17px; padding:10px 20px 6px; letter-spacing:1px; }
aside .sub { font-size:12px; opacity:.65; padding:0 20px 14px;
  border-bottom:1px solid rgba(255,255,255,.15); }
aside .grp { font-size:12px; opacity:.6; padding:14px 20px 6px;
  letter-spacing:2px; }
aside a { display:block; padding:8px 20px; font-size:13.5px; color:#DBEAFE;
  text-decoration:none; cursor:pointer; word-break:break-all; }
aside a:hover { background:rgba(255,255,255,.08); }
aside a.on { background:#1E3A8A; color:#fff; border-left:4px solid #F97316; }
main { flex:1; display:flex; flex-direction:column; min-width:0; }
.bar { display:flex; align-items:center; gap:14px; padding:12px 20px;
  background:#fff; border-bottom:1px solid #E5E7EB; }
.bar .path { font-family:Consolas,monospace; font-size:13.5px; color:#374151;
  flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }
.bar .hint { font-size:12px; color:#9CA3AF; }
button { background:#1E3A8A; color:#fff; border:none; border-radius:8px;
  padding:9px 22px; font-size:14px; cursor:pointer; font-family:inherit; }
button:hover { background:#1D4ED8; }
button:disabled { background:#9CA3AF; cursor:default; }
#status { font-size:12.5px; color:#059669; min-width:110px; text-align:right; }
#status.dirty { color:#D97706; }
textarea { flex:1; border:none; outline:none; resize:none; padding:18px 22px;
  font-family:Consolas,'Microsoft YaHei',monospace; font-size:13.5px;
  line-height:1.7; white-space:pre; overflow:auto; background:#fff; }
</style></head><body>
<aside>
  <h1>公众号报告 Skill · 编辑台</h1>
  <div class="sub">改动直接写回文件（Ctrl+S 保存）</div>
  <div id="nav"></div>
</aside>
<main>
  <div class="bar">
    <div class="path" id="path">—</div>
    <div class="hint" id="hint"></div>
    <div id="status"></div>
    <button id="save" onclick="save()">保存</button>
  </div>
  <textarea id="ta" spellcheck="false" placeholder="从左侧选择一个文件开始编辑"></textarea>
</main>
<script>
const FILES = __FILES__;
const nav = document.getElementById('nav');
const ta = document.getElementById('ta');
const pathEl = document.getElementById('path');
const hintEl = document.getElementById('hint');
const statusEl = document.getElementById('status');
let cur = null, dirty = false;

const groups = {};
for (const [p, [g, h]] of Object.entries(FILES))
  (groups[g] = groups[g] || []).push([p, h]);

for (const g of Object.keys(groups)) {
  const d = document.createElement('div');
  d.className = 'grp'; d.textContent = g; nav.appendChild(d);
  for (const [p, h] of groups[g]) {
    const a = document.createElement('a');
    a.textContent = p.split('/').pop() + '　' + (p.includes('/') ? p.split('/').slice(0,-1).join('/') : '');
    a.title = p + '｜' + h;
    a.onclick = () => open(p, a);
    a.dataset.p = p;
    nav.appendChild(a);
  }

}

async function open(p, el) {
  if (dirty && !confirm('当前文件未保存，切换将丢失改动。继续？')) return;
  document.querySelectorAll('aside a').forEach(x => x.classList.remove('on'));
  el.classList.add('on');
  cur = p;
  pathEl.textContent = p;
  hintEl.textContent = '改完：' + FILES[p][1];
  const r = await fetch('/api/file?path=' + encodeURIComponent(p));
  ta.value = await r.text();
  setDirty(false);
}

function setDirty(d) {
  dirty = d;
  statusEl.className = d ? 'dirty' : '';
  statusEl.textContent = d ? '● 未保存' : '已保存';
}

ta.addEventListener('input', () => setDirty(true));

const qf = new URLSearchParams(location.search).get('file');
if (qf && FILES[qf]) {
  const el = document.querySelector('aside a[data-p="' + qf + '"]');
  if (el) el.click();
}

async function save() {
  if (!cur) return;
  const r = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: cur, content: ta.value })
  });
  const j = await r.json();
  setDirty(false);
  statusEl.textContent = j.ok ? ('✓ ' + new Date().toLocaleTimeString()) : '保存失败';
}

document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save(); }
});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默访问日志，避免控制台编码问题

    def _send(self, code, body, ctype='text/html; charset=utf-8'):
        data = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _safe_path(self, rel):
        if rel not in EDITABLE:
            return None
        return os.path.join(BASE, rel.replace('/', os.sep))

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/api/file':
            qs = urllib.parse.parse_qs(u.query)
            rel = (qs.get('path') or [''])[0]
            p = self._safe_path(rel)
            if not p or not os.path.exists(p):
                return self._send(404, 'not found', 'text/plain; charset=utf-8')
            with open(p, 'r', encoding='utf-8') as f:
                return self._send(200, f.read(), 'text/plain; charset=utf-8')
        page = PAGE.replace('__FILES__', json.dumps(
            {k: list(v) for k, v in EDITABLE.items()}, ensure_ascii=False))
        return self._send(200, page)

    def do_POST(self):
        if self.path != '/api/save':
            return self._send(404, 'bad endpoint', 'text/plain; charset=utf-8')
        length = int(self.headers.get('Content-Length') or 0)
        try:
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except ValueError:
            return self._send(400, '{"ok":false,"msg":"bad json"}',
                              'application/json')
        p = self._safe_path(payload.get('path', ''))
        if not p:
            return self._send(403, '{"ok":false,"msg":"forbidden"}',
                              'application/json')
        with open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(payload.get('content', ''))
        return self._send(200, '{"ok":true}',
                          'application/json')


def main():
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print('edit server on http://127.0.0.1:%d/ (Ctrl+C to stop)' % PORT)
    srv.serve_forever()


if __name__ == '__main__':
    main()
