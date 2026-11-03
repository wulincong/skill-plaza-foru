import assert from 'node:assert/strict'
import { test } from 'node:test'
import { projectQuestion } from './chatQuestion.ts'
import { deriveSessionConversation } from './conversation.ts'

const fenced = value => '已核对。\n\n```plaza-question\n' + JSON.stringify(value) + '\n```'
const legacy = '学历分布：\n\n|学历|岗位数|\n|---|---|\n|大专|54|\n\n请问按哪个口径继续分析？\n\n1. **大专+经验不限（54 条）**——样本较小；\n2. 入门池——宽口径；\n3. 严格高职——样本为空。\n\n如无特别说明，我建议按 **方案 1** 继续。'

for (const kind of ['confirm', 'single', 'multiple', 'input']) {
  test('projects a validated ' + kind + ' question without exposing the fence', () => {
    const options = kind === 'input' ? [] : [{ label: '同意', description: '继续此任务' }, { label: '暂缓' }]
    const request = { kind, question: '怎样继续？', options }
    assert.deepEqual(projectQuestion(fenced(request)), { text: '已核对。', question: request })
  })
}

test('a complete question survives a missing closing fence; a repeated question appears once', () => {
  const raw = fenced({ kind: 'confirm', question: '开始收集标题？', options: ['同意', '拒绝'] })
    .replace('已核对。', '已核对。\n\n首先，请问开始收集标题？').replace(/\n```$/, '')
  assert.equal(projectQuestion(raw).question.kind, 'confirm')
  assert.equal(projectQuestion(raw).text, '已核对。')
})

test('a legacy choice preserves the source table, all labels, explanations and recommendation', () => {
  const projected = projectQuestion(legacy)
  assert.match(projected.text, /\|大专\|54\|$/)
  assert.deepEqual(projected.question.options.map(o => o.label), ['大专+经验不限（54 条）', '入门池', '严格高职'])
  assert.equal(projected.question.options[0].description, '样本较小')
  assert.equal(projected.question.note, '如无特别说明，我建议按 方案 1 继续。')
  assert.equal(projectQuestion(legacy.replace(/\d\. /g, '')).question.options.length, 3)
})

test('invalid schemas, instructional lists and quoted code stay ordinary text', () => {
  for (const raw of [
    fenced({ kind: 'single', question: '选什么？', options: ['重复', '重复'] }),
    fenced({ kind: 'confirm', question: '', options: ['是', '否'] }),
    fenced({ kind: 'confirm', question: '继续？', options: ['是', '否', '其他'] }),
    '请问哪个更好？\n\n1. 方案一\n2. 方案二\n\n综上所述，已经采用方案一。',
    '```text\n' + legacy + '\n```',
    '实施步骤\n1. 打开菜单\n2. 关闭页面',
  ]) assert.deepEqual(projectQuestion(raw), { text: raw })
})

test('old answers keep their original wording and question association across history snapshots', () => {
  const runs = ['a','b'].map((runId, i) => ({ runId, ts: runId, clientSessionId: 's', engineSessionId: 'e', engine: 'pi', skill: 'general', outcome: 'success', userMessage: i ? '方案2' : '请分析' }))
  const messages = [runs[0].userMessage, legacy, runs[1].userMessage, '已继续'].map((text, i) => ({ role: i % 2 ? 'assistant' : 'user', parts: [{ type: 'text', text }] }))
  const turns = deriveSessionConversation(runs[1], runs, run => ({ messages: messages.slice(0, run === runs[0] ? 2 : 4) }), () => [])
  assert.equal(turns[1].question.kind, 'single')
  assert.equal(turns[2].answerTo, 'a')
  assert.equal(turns[2].text, '方案2')
})
