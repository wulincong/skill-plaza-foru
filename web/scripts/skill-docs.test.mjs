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
  const external = 'docs/external-skills/demo/docs/'
  const collect = () => collectDocs(root, ['demo'])
  write('.agents/skills/private/SKILL.md', 'internal instructions')
  write('.agents/skills/private/docs/index.md', '# 内部文档\n\nprivate text')
  write('.agents/skills/private/templates/nested/SKILL.md', 'not a top-level skill')
  write(external + 'index.md', '# 子模块配套指南\n\n介绍')
  assert.match(repositoryIndex(collect()), /内部文档/)
  assert.deepEqual(publicCatalog(collect()).map(s => s.id), ['demo'])
  assert.doesNotMatch(JSON.stringify(publicCatalog(collect())), /private/)
  assert.equal(publicCatalog(collect())[0].pages[0].title, '子模块配套指南')

  write(native + 'examples.md', '# 示例\n\n正文')
  assert.throws(collect, /缺少 docs\/index.md/)
  write(native + 'index.md', '# 使用指南\n\n阅读[示例](./examples.md)。\n\n<script>alert(1)</script>')
  const pages = publicCatalog(collect())[0].pages
  assert.deepEqual(pages.map(p => p.key), ['index', 'examples'])
  assert.match(pages[0].html, /href="#\/docs\/demo\/examples"/)
  assert.match(pages[0].html, /&lt;script&gt;/)
  assert.doesNotMatch(repositoryIndex(collect()), /子模块配套指南/)
  write(native + 'examples.md', '缺少标题')
  assert.throws(collect, /首行一级标题/)
  rmSync(join(root, native, 'examples.md'))
  assert.throws(() => publicCatalog(collect()), /链接/)
})
