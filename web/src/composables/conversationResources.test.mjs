import assert from 'node:assert/strict'
import { test } from 'node:test'
import { collectConversationResources } from './conversationResources.ts'

test('only published links appear, keeping previous resources across follow-ups', () => {
  const links = collectConversationResources([
    { role: 'user', text: '生成报告', downloads: [{ name: 'NOT PUBLISHED', url: '/fake' }] },
    { role: 'ai', text: '本地路径 output/report.zip', webLinks: [{ name: '报告', url: '/p/id/0/' }], downloads: [{ name: '完整交付包', url: '/api/deliveries/id/files/0' }] },
    { role: 'user', text: '继续说明' }, { role: 'ai', text: '解释内容' },
  ])
  assert.equal(links.length, 2)
  assert(links.every(link => link.turn === 1 && link.messageIndex === 1))
  assert.equal(links.find(link => link.kind === 'web').url, '/p/id/0/')
  assert.equal(links.find(link => link.kind === 'file').name, '完整交付包')
})

test('repeated URLs deduplicate while distinct new deliveries and source turns remain', () => {
  const web = { name: '原报告', url: '/p/old/0/' }
  const links = collectConversationResources([
    { role: 'user' }, { role: 'ai', webLinks: [web] },
    { role: 'user' }, { role: 'ai', webLinks: [web, { name: '新报告', url: '/p/new/0/' }] },
  ])
  assert.deepEqual(links.map(link => [link.name, link.turn]), [['新报告', 2], ['原报告', 1]])
})

test('legacy PDF is download-only and legacy HTML retains both access channels', () => {
  const pdf = collectConversationResources([{ role: 'user' }, { role: 'ai', skill: { slug: 'doc-translate' }, reportUrl: '/api/reports/pdf' }])
  assert.deepEqual(pdf.map(link => [link.kind, link.url]), [['file', '/api/reports/pdf/download']])
  const html = collectConversationResources([{ role: 'ai', reportUrl: '/api/reports/html' }])
  assert.deepEqual(html.map(link => [link.kind, link.url]), [['file', '/api/reports/html/download'], ['web', '/api/reports/html']])
  assert.equal(collectConversationResources([{ role: 'ai', reportUrl: '/legacy', downloads: [{ name: '实际文件', url: '/new' }] }]).length, 1)
})

test('new conversations and prose-only answers expose no previous or inferred resources', () => {
  assert.deepEqual(collectConversationResources([]), [])
  assert.deepEqual(collectConversationResources([{ role: 'ai', text: '下载 http://example.com/made-up.zip 或 output/public/report.zip' }]), [])
})
