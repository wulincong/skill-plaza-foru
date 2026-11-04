import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { collectDocs, publicCatalog, repositoryIndex } from './skill-docs.mjs'

test('仓库收录内部技能，公开目录只渲染注册技能的 docs 页面', t => {
  const root = mkdtempSync(join(tmpdir(), 'plaza-skill-docs-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  function write(path, body) {
    mkdirSync(dirname(join(root, path)), { recursive: true })
    writeFileSync(join(root, path), body)
  }
  const native = '.agents/skills/demo/docs/'
  const collect = () => collectDocs(root, ['demo'])
  write('.agents/skills/private/SKILL.md', 'internal instructions')
  write('.agents/skills/private/docs/index.md', '# 内部文档\n\nprivate text')
  write('.agents/skills/private/templates/nested/SKILL.md', 'not a top-level skill')
  write(native + 'examples.md', '# 示例\n\n正文')
  assert.throws(collect, /缺少 docs\/index.md/)
  write(native + 'index.md', '# 使用指南\n\n阅读[示例](./examples.md)。\n\n<script>alert(1)</script>')
  assert.match(repositoryIndex(collect()), /内部文档/)
  assert.deepEqual(publicCatalog(collect()).map(s => s.id), ['demo'])
  assert.doesNotMatch(JSON.stringify(publicCatalog(collect())), /private/)
  const pages = publicCatalog(collect())[0].pages
  assert.deepEqual(pages.map(p => p.key), ['index', 'examples'])
  assert.match(pages[0].blocks[0].html, /href="#\/docs\/demo\/examples"/)
  assert.match(pages[0].blocks[0].html, /&lt;script&gt;/)
  write(native + 'examples.md', '缺少标题')
  assert.throws(collect, /首行一级标题/)
  rmSync(join(root, native, 'examples.md'))
  assert.throws(() => publicCatalog(collect()), /链接/)
})

test('示例逐块保留原文，普通引文和代码保持原位，小节链接各有目标', () => {
  const example = '按以下要求修改 <材料> & "术语"。\n\n  保留这行的缩进。'
  const body = [
    '## 输入', '> 一段引用', '```prompt\n' + example + '\n```',
    '## 输入', '[更多说明][ref]', '```sh\necho demo\n```', '```prompt\n下一条\n```',
    '[ref]: https://example.org/guide',
  ].join('\n\n')
  const page = { key: 'index', title: '示例', file: 'demo.md', body }
  const [skill] = publicCatalog([{ id: 'demo', public: true, pages: [page] }])
  const { blocks, outline } = skill.pages[0]
  assert.deepEqual(blocks.map(b => b.kind), ['markdown', 'prompt', 'markdown', 'prompt'])
  assert.equal(blocks[1].text, example)
  assert.equal(blocks[3].text, '下一条')
  assert.match(blocks[0].html, /<blockquote>/)
  assert.match(blocks[2].html, /class="language-sh"/)
  assert.match(blocks[2].html, /href="https:\/\/example.org\/guide"/)
  assert.deepEqual(outline.map(s => s.title), ['输入', '输入'])
  assert.notEqual(outline[0].id, outline[1].id)
  assert.ok(blocks[0].html.includes('id="' + outline[0].id + '"'))
  assert.ok(blocks[2].html.includes('id="' + outline[1].id + '"'))
})
