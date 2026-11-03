// Both the repository index and the public reader resolve each skill to one source.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import MarkdownIt from 'markdown-it'
import { GENERAL_SKILL_ID, SKILL_PROMPTS } from '../server/lib/skills.ts'

export const repoRoot = fileURLToPath(new URL('../../', import.meta.url))
export const skillRoots = ['.agents/skills', 'docs/external-skills']
export const publicIds = Object.keys(SKILL_PROMPTS).filter(id => id !== GENERAL_SKILL_ID)
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

export function collectDocs(root = repoRoot, registered = publicIds) {
  const [native, external] = skillRoots.map(path => join(root, path))
  const ids = new Set(registered)
  for (const parent of [native, external]) {
    if (!existsSync(parent)) continue
    for (const entry of readdirSync(parent, { withFileTypes: true })) {
      if (entry.isDirectory() && (parent === external || existsSync(join(parent, entry.name, 'SKILL.md')))) {
        ids.add(entry.name)
      }
    }
  }

  return [...ids].sort().map(id => {
    if (!slugPattern.test(id)) throw Error(`无效的技能目录名 ${id}`)
    const ownDocs = join(native, id, 'docs')
    const dir = existsSync(ownDocs) ? ownDocs : join(external, id, 'docs')
    if (!existsSync(join(dir, 'index.md'))) throw Error(`${id} 缺少 docs/index.md`)
    const pages = readdirSync(dir, { withFileTypes: true })
      .filter(entry => entry.isFile() && entry.name.endsWith('.md'))
      .map(entry => {
        const key = entry.name.slice(0, -3)
        const file = join(dir, entry.name)
        const source = readFileSync(file, 'utf8').replace(/\r\n/g, '\n').trim()
        const [heading, ...lines] = source.split('\n')
        const title = /^#\s+(.+)$/.exec(heading)?.[1].trim()
        const body = lines.join('\n').trim()
        if (!slugPattern.test(key) || !title || !body) {
          throw Error(`${file} 需要小写英文文件名、首行一级标题和正文`)
        }
        return { key, title, body, file: relative(root, file) }
      })
      .sort((a, b) => Number(b.key === 'index') - Number(a.key === 'index') || a.key.localeCompare(b.key, 'en'))
    if (pages[0]?.key !== 'index') throw Error(`${dir}/index.md 必须是普通文件`)
    return { id, public: registered.includes(id), pages }
  })
}

const markdown = new MarkdownIt({ html: false })
markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const href = token.attrGet('href')
  if (!/^https?:\/\//i.test(href)) {
    const key = href.replace(/^\.\//, '').replace(/\.md$/, '')
    if (!href.endsWith('.md') || !env.skill.pages.some(page => page.key === key)) {
      throw Error(`${env.file} 中的链接 ${href} 需要指向同目录 Markdown 或完整网页地址`)
    }
    token.attrSet('href', `#/docs/${env.skill.id}${key === 'index' ? '' : '/' + key}`)
  }
  return self.renderToken(tokens, idx, options)
}

export function publicCatalog(skills) {
  return skills.filter(skill => skill.public).map(skill => ({
    id: skill.id,
    summary: skill.pages[0].body.split('\n\n', 1)[0],
    pages: skill.pages.map(page => ({
      key: page.key,
      title: page.title,
      html: markdown.render(page.body, { skill, file: page.file }),
    })),
  }))
}

export function repositoryIndex(skills) {
  const lines = ['# 技能文档索引', '', '由各技能的 Markdown 自动汇总。新增或修改页面后，从 web 目录运行 `npm run docs:index` 更新此页。']
  for (const [isPublic, heading] of [[true, '广场技能'], [false, '开发与共享技能']]) {
    lines.push('', `## ${heading}`, '')
    for (const { id, pages } of skills.filter(skill => skill.public === isPublic)) {
      const links = pages.map(page => `[${page.title}](${relative('docs', page.file)})`)
      lines.push(`- ${links.join(' · ')} （\`${id}\`）`)
    }
  }
  return lines.join('\n') + '\n'
}
