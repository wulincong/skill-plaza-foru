import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { collectDocs, hasSkillDocs, publicCatalog, publicGuide, repositoryIndex } from './skill-docs.mjs'

function docsFixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'plaza-skill-docs-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  function write(path, body) {
    mkdirSync(dirname(join(root, path)), { recursive: true })
    writeFileSync(join(root, path), body)
  }
  return { root, write }
}

test('缺文档的技能可以独立接入，增删首页后同步收录或撤下所有专题', t => {
  const { root, write } = docsFixture(t)
  const parent = '.agents/skills/'
  const home = parent + 'draft/docs/index.md'
  const registered = ['ready', 'draft', 'prompt-only']
  const collect = () => collectDocs(root, registered)
  write(parent + 'ready/docs/index.md', '# 已发布\n\n说明')
  write(parent + 'private/SKILL.md', 'internal')
  write(parent + 'draft/SKILL.md', 'draft')
  write('docs/guide.md', '# 通用指南\n\n说明')
  function checkUnpublished() {
    assert.equal(hasSkillDocs(root, 'draft'), false)
    const skills = collect()
    assert.deepEqual(skills.map(s => s.id), ['ready'])
    assert.deepEqual(publicCatalog(skills).map(s => s.id), ['ready'])
    const index = repositoryIndex(skills, publicGuide(root))
    assert.match(index, /通用指南/)
    assert.doesNotMatch(index, /draft|private|prompt-only/)
  }
  checkUnpublished()
  mkdirSync(dirname(join(root, home)))
  checkUnpublished()
  write(parent + 'draft/docs/topic.md', '# 专题\n\n正文')
  checkUnpublished()
  write(home, '# 新指南\n\n[专题](topic.md)')
  assert.equal(hasSkillDocs(root, 'draft'), true)
  assert.deepEqual(publicCatalog(collect())[0].pages.map(p => p.key), ['index', 'topic'])
  rmSync(join(root, home))
  checkUnpublished()
})

test('仓库收录内部技能，公开目录只渲染注册技能的 docs 页面', t => {
  const { root, write } = docsFixture(t)
  const native = '.agents/skills/demo/docs/'
  const collect = () => collectDocs(root, ['demo'])
  write('.agents/skills/private/SKILL.md', 'internal instructions')
  write('.agents/skills/private/docs/index.md', '# 内部文档\n\nprivate text')
  write('.agents/skills/private/templates/nested/SKILL.md', 'not a top-level skill')
  write(native + 'examples.md', '# 示例\n\n正文')
  write(native + 'index.md', '# 使用指南\n\n阅读[示例](./examples.md)。\n\n<script>alert(1)</script>')
  write('docs/guide.md', '# 在线运行与 API 指南\n\n## 在线运行\n\n[打开在线对话](#/experience)\n\n```bash\ncurl https://example.org\n```')
  const guide = publicGuide(root)
  const index = repositoryIndex(collect(), guide)
  assert.match(index, /内部文档/)
  assert.match(index, /\[在线运行与 API 指南\]\(guide.md\)/)
  assert.deepEqual(guide.outline.map(section => section.title), ['在线运行'])
  assert.match(guide.blocks[0].html, /href="#\/experience"/)
  assert.deepEqual(guide.blocks[1], { kind: 'command', text: 'curl https://example.org' })
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
  assert.deepEqual(blocks.map(b => b.kind), ['markdown', 'prompt', 'markdown', 'command', 'prompt'])
  assert.equal(blocks[1].text, example)
  assert.equal(blocks[4].text, '下一条')
  assert.match(blocks[0].html, /<blockquote>/)
  assert.deepEqual(blocks[3], { kind: 'command', text: 'echo demo' })
  assert.match(blocks[2].html, /href="https:\/\/example.org\/guide"/)
  assert.deepEqual(outline.map(s => s.title), ['输入', '输入'])
  assert.notEqual(outline[0].id, outline[1].id)
  assert.ok(blocks[0].html.includes('id="' + outline[0].id + '"'))
  assert.ok(blocks[2].html.includes('id="' + outline[1].id + '"'))
})
