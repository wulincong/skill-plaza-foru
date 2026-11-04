import assert from 'node:assert/strict'
import { test } from 'node:test'
import { projectQuestion, projectIndustryReply } from './chatQuestion.ts'
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

const labels=['补充材料','扩大范围','按现有证据继续']
const shortage='已有企业访谈。待确认：学校工位与师资。请上传排课表。'
const question={kind:'single',question:'接下来如何处理？',options:labels.map(label=>({label}))}

test('industry evidence waits remain actionable with valid, malformed and plain output',()=>{
  const raw=fenced(question).replace('已核对。',shortage)
  const malformed=raw.replace('"}]}','"}}]')
  for(const message of [raw,malformed,shortage]){
    const card=projectIndustryReply(message,true)
    assert.equal(card.waiting,true)
    assert.equal(card.text,shortage)
    assert.deepEqual(card.question.options.map(o=>o.label),labels)
    const plain=projectIndustryReply(message,false)
    assert.equal(plain.waiting,true)
    assert.doesNotMatch(plain.text,/plaza-question|"options"|[={}]/)
    for(const label of labels) assert.equal(plain.text.split(label).length,2)
  }
})

test('industry scope questions, finished reports, protocol examples and ordinary replies are preserved',()=>{
  const scope={kind:'input',question:'研究哪个地区？',options:[]}
  const raw=fenced(scope).replace('已核对。','岗位观察还有关键缺口。')
  assert.deepEqual(projectIndustryReply(raw,true),{text:'岗位观察还有关键缺口。',question:scope,waiting:false})
  assert.equal(projectIndustryReply(raw,false).text,'岗位观察还有关键缺口。\n\n研究哪个地区？')
  const example='这里是协议示例：\n'+fenced(question).split('\n\n')[1]
  for(const ordinary of ['已生成决策报告。关键缺口在附录。以后如需扩展，请补充材料。','请提供目标地区。',example]){
    assert.deepEqual(projectIndustryReply(ordinary,true),{text:ordinary,question:undefined,waiting:false})
  }
})

test('a paraphrased evidence menu still pauses and exposes the same three actions',()=>{
  const menu={kind:'single',question:'怎样继续？',options:[
    {label:'补充校内排课材料'},{label:'扩大调研范围'},{label:'基于已有材料生成简报'},
  ]}
  const projected=projectIndustryReply(fenced(menu),true)
  assert.equal(projected.waiting,true)
  assert.deepEqual(projected.question.options.map(o=>o.label),labels)
})
