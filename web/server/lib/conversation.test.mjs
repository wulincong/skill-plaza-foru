import assert from 'node:assert/strict'
import { test } from 'node:test'
import { deriveConversation, stripUserPrompt } from './conversation.ts'

const wrappers = [{ prefix: '/skill:doc-translate ', suffix: '' }, { prefix: '', suffix: '' }]
const message = (role, ...parts) => ({ role, parts })
const text = value => ({ type: 'text', text: value })
const tool = name => ({ type: 'tool', tool: name, startedAt: 100, endedAt: 200, state: { status: 'completed', input: 'PRIVATE COMMAND', output: 'PRIVATE OUTPUT' } })

test('expanded skill is stripped before the empty continuation wrapper can match', () => {
  const input = '<skill name="doc-translate" location="/private/SKILL.md">\nSYSTEM RULES\n</skill>\n\n请翻译一下这个文档\n\n用户已上传附件 uploads/endtoend.pdf（endtoend.pdf），文件在当前工作目录内，请先读取该文件再继续任务。'
  assert.equal(stripUserPrompt(input, wrappers), '请翻译一下这个文档')
  assert.equal(stripUserPrompt('/skill:doc-translate 翻译为中文', wrappers), '翻译为中文')
})

test('backend suffixes and inline attachment content are absent from the user bubble', () => {
  assert.equal(stripUserPrompt('请检查\n\n[附件 简历（uploads/resume.md）内容]\nPRIVATE RESUME\nCONTRACT', [{ prefix: '', suffix: '\nCONTRACT' }]), '请检查')
  assert.equal(stripUserPrompt('PREFIX 用户原话 SUFFIX', [{ prefix: 'PREFIX ', suffix: ' SUFFIX' }]), '用户原话')
})

test('one user turn contains one final answer and all tools/narration in process', () => {
  const trace = { messages: [
    message('system', text('SYSTEM SECRET')),
    message('user', text('开始')),
    message('assistant', text('先读取文档。'), tool('read')),
    message('toolResult', text('PRIVATE OUTPUT')),
    message('assistant', { type: 'reasoning', text: 'HIDDEN REASONING' }, tool('bash')),
    message('assistant', text('已确认结构，开始生成。'), tool('write')),
    message('assistant', text('译文已完成。')),
  ] }
  const turns = deriveConversation(trace, [])
  assert.equal(turns.length, 2)
  assert.equal(turns[1].text, '译文已完成。')
  assert.deepEqual(turns[1].process, ['先读取文档。', '已确认结构，开始生成。'])
  assert.equal(turns[1].tools.length, 3)
  assert.equal(turns[1].tools[0].startedAt, 100)
  assert.doesNotMatch(JSON.stringify(turns), /SYSTEM SECRET|HIDDEN REASONING|PRIVATE COMMAND|PRIVATE OUTPUT/)
})

test('multiple user turns keep their own final answer, tools and process', () => {
  const turns = deriveConversation({ messages: [
    message('user', text('第一问')), message('assistant', text('第一答')),
    message('user', text('第二问')), message('assistant', text('查一下。'), tool('read')), message('assistant', text('第二答')),
  ] }, [])
  assert.deepEqual(turns.map(turn => turn.text), ['第一问', '第一答', '第二问', '第二答'])
  assert.equal(turns[1].tools, undefined)
  assert.equal(turns[3].tools.length, 1)
})

test('interrupted tool chain does not promote narration into a final answer', () => {
  const turns = deriveConversation({ messages: [message('user', text('运行')), message('assistant', text('准备读取。'), tool('read')), message('assistant', tool('bash'))] }, [])
  assert.equal(turns[1].text, '')
  assert.deepEqual(turns[1].process, ['准备读取。'])
  assert.equal(turns[1].tools.length, 2)
})

test('saved original input wins over prompt parsing and preserves literal skill markup', () => {
  const original = '<skill name="demo" location="example">用户自己写的标签</skill>'
  const turns = deriveConversation({ messages: [message('user', text('BACKEND WRAPPER')), message('assistant', text('完成'))] }, wrappers, [{ text: original, attachments: ['原文.pdf'] }])
  assert.equal(turns[0].text, original + '\n[附件] 原文.pdf')
})

test('mismatched original input count falls back rather than assigning another user turn', () => {
  const turns = deriveConversation({ messages: [message('user', text('/skill:doc-translate 原文'))] }, wrappers, [{ text: '另一问' }, { text: '尚未发送' }])
  assert.equal(turns[0].text, '原文')
})

