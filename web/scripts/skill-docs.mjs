// Both the repository index and the public reader resolve each skill to one source.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { basename, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import MarkdownIt from 'markdown-it'
import { GENERAL_SKILL_ID, SKILL_PROMPTS } from '../server/lib/skills.ts'

export const repoRoot = fileURLToPath(new URL('../../', import.meta.url))
export const skillRoot = '.agents/skills'
export const guideFile = 'docs/guide.md'
export const publicIds = Object.keys(SKILL_PROMPTS).filter(id => id !== GENERAL_SKILL_ID)
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

function readPage(root, file) {
  const key = basename(file, '.md')
  const source = readFileSync(file, 'utf8').replace(/\r\n/g, '\n').trim()
  const [heading, ...lines] = source.split('\n')
  const title = /^#\s+(.+)$/.exec(heading)?.[1].trim()
  const body = lines.join('\n').trim()
  if (!slugPattern.test(key) || !title || !body) {
    throw Error(`${file} 需要小写英文文件名、首行一级标题和正文`)
  }
  return { key, title, body, file: relative(root, file) }
}

export function hasSkillDocs(root, id) {
  return existsSync(join(root, skillRoot, id, 'docs', 'index.md'))
}

export function collectDocs(root = repoRoot, registered = publicIds) {
  const parent = join(root, skillRoot)
  const ids = new Set(registered)
  for (const entry of readdirSync(parent, { withFileTypes: true })) {
    if (entry.isDirectory() && existsSync(join(parent, entry.name, 'SKILL.md'))) ids.add(entry.name)
  }
  return [...ids].filter(id => hasSkillDocs(root, id)).sort().map(id => {
    if (id === 'guide' && registered.includes(id)) throw Error('guide 是文档中心的通用指南保留地址')
    if (!slugPattern.test(id)) throw Error(`无效的技能目录名 ${id}`)
    const dir = join(parent, id, 'docs')
    const pages = readdirSync(dir, { withFileTypes: true })
      .filter(entry => entry.isFile() && entry.name.endsWith('.md'))
      .map(entry => readPage(root, join(dir, entry.name)))
      .sort((a, b) => Number(b.key === 'index') - Number(a.key === 'index') || a.key.localeCompare(b.key, 'en'))
    if (pages[0]?.key !== 'index') throw Error(`${dir}/index.md 必须是普通文件`)
    return { id, public: registered.includes(id), pages }
  })
}

const markdown = new MarkdownIt({ html: false })
markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const href = token.attrGet('href')
  if (['#/experience', '#/skills', '#/docs'].includes(href)) return self.renderToken(tokens, idx, options)
  if (!/^https?:\/\//i.test(href)) {
    const key = href.replace(/^\.\//, '').replace(/\.md$/, '')
    if (!href.endsWith('.md') || !env.skill?.pages.some(page => page.key === key)) {
      throw Error(`${env.file} 中的链接 ${href} 需要指向同目录 Markdown 或完整网页地址`)
    }
    token.attrSet('href', `#/docs/${env.skill.id}${key === 'index' ? '' : '/' + key}`)
  }
  return self.renderToken(tokens, idx, options)
}

// Parse once so Markdown reference definitions work across prompt examples.
function renderPage(skill, page) {
  const env = { skill, file: page.file }
  const tokens = markdown.parse(page.body, env)
  const blocks = []
  const outline = []
  let start = 0
  function appendMarkdown(end) {
    if (end > start) {
      const html = markdown.renderer.render(tokens.slice(start, end), markdown.options, env)
      blocks.push({ kind: 'markdown', html })
    }
  }
  tokens.forEach((token, i) => {
    if (token.type === 'heading_open' && token.tag === 'h2' && token.level === 0) {
      const title = tokens[i + 1].content
      const id = 'section-' + (outline.length + 1)
      token.attrSet('id', id)
      outline.push({ id, title })
    }
    if (token.type !== 'fence') return
    const language = token.info.trim()
    if (language === 'prompt' || (token.level === 0 && ['bash', 'sh'].includes(language))) {
      if (token.level !== 0 || !token.content.trim()) {
        throw Error(`${page.file} 的 ${language} 示例需要放在独立段落，且正文不能为空`)
      }
      appendMarkdown(i)
      blocks.push({ kind: language === 'prompt' ? 'prompt' : 'command', text: token.content.replace(/\n$/, '') })
      start = i + 1
    }
  })
  appendMarkdown(tokens.length)
  return { key: page.key, title: page.title, blocks, outline }
}

export function publicGuide(root = repoRoot) {
  return renderPage(null, readPage(root, join(root, guideFile)))
}

export function publicCatalog(skills) {
  return skills.filter(skill => skill.public).map(skill => ({
    id: skill.id,
    summary: skill.pages[0].body.split('\n\n', 1)[0],
    pages: skill.pages.map(page => renderPage(skill, page)),
  }))
}

export function repositoryIndex(skills, guide) {
  const lines = ['# 技能文档索引', '', '由各技能的 Markdown 自动汇总。新增或修改页面后，从 web 目录运行 `npm run docs:index` 更新此页。']
  lines.push('', '## 通用指南', '', `- [${guide.title}](${basename(guideFile)})`)
  for (const [isPublic, heading] of [[true, '广场技能'], [false, '开发与共享技能']]) {
    lines.push('', `## ${heading}`, '')
    for (const { id, pages } of skills.filter(skill => skill.public === isPublic)) {
      const links = pages.map(page => `[${page.title}](${relative('docs', page.file)})`)
      lines.push(`- ${links.join(' · ')} （\`${id}\`）`)
    }
  }
  return lines.join('\n') + '\n'
}
