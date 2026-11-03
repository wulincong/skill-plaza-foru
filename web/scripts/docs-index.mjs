import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { collectDocs, publicCatalog, repositoryIndex, repoRoot } from './skill-docs.mjs'

const skills = collectDocs()
const published = publicCatalog(skills)
const file = join(repoRoot, 'docs/skill-index.md')
const index = repositoryIndex(skills)
if (process.argv.includes('--check')) {
  if (readFileSync(file, 'utf8') !== index) throw Error('文档索引有变化，请运行 npm run docs:index')
} else {
  writeFileSync(file, index)
}
console.log(`已汇总 ${skills.length} 个技能的 ${skills.reduce((n, s) => n + s.pages.length, 0)} 页文档，${published.length} 个技能公开展示。`)
