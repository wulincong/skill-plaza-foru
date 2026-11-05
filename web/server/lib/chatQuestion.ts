import type { ChatQuestion, QuestionOption } from '../../shared/chatQuestion.ts'

export const QUESTION_INSTRUCTION = [
  '【在线对话提问约定】仅当任务必须等待用户决定或补充信息才能继续时，结束本轮，在回复末尾单独输出一个 plaza-question 代码块。等待真实回复后再执行，不代选。其他回复照常，不输出此块。',
  '必要的分析/表格先写在块前。问题、选项、建议只写在块内一次。格式如下，替换为实际内容：',
  '```plaza-question', '{"kind":"single","question":"请问按哪个口径继续分析？","options":[{"label":"选项名称","description":"该选择的依据或影响"},{"label":"另一个选项","description":"该选择的影响"}]}', '```',
  'kind 用 confirm（两个相反操作，如继续/取消）、single（互斥方案）、multiple（可同时选择）或 input（用户自由填写，无需 options）。每次一个问题，选择题给 2 至 12 项，可加 note 简述建议。',
].join('\n')

interface QuestionMessage { text: string; question?: ChatQuestion }

function line(value: unknown, limit: number): string | undefined {
  return typeof value === 'string' && value.trim() && value.length <= limit ? value.trim() : undefined
}

function validated(value: any): ChatQuestion | undefined {
  const title = line(value?.question, 500)
  if (!title || !['confirm', 'single', 'multiple', 'input'].includes(value.kind)) return
  const options: QuestionOption[] = []
  const input = value.options ?? []
  if (!Array.isArray(input) || input.length > 12) return
  if (value.kind === 'input' ? input.length !== 0 : input.length < 2) return
  if (value.kind === 'confirm' && input.length !== 2) return
  for (const item of input) {
    const label = line(typeof item === 'string' ? item : item?.label, 200)
    if (!label || options.some(o => o.label === label)) return
    const description = line(item?.description, 800)
    options.push(description ? { label, description } : { label })
  }
  const note = line(value.note, 1200)
  return { kind: value.kind, question: title, options, ...(note ? { note } : {}) }
}

// Old conversations used a direct choice question followed by numbered options.
// Only lift a self-contained choice list. Leave tutorials, tables and examples intact.
function legacyChoice(text: string): QuestionMessage {
  const plain = (s: string) => s.trim().replace(/\*\*/g, '')
  const lines = text.split(/\r?\n/)
  const at = lines.findLastIndex(s => /^(?:请问|请您选择|请选择|您希望|你希望).{0,160}(?:哪个|哪种|哪一|哪些|哪几|哪项|哪套).*[？?：:]$/.test(plain(s)))
  if (at < 0 || text.includes('```')) return { text }
  const options: QuestionOption[] = []
  let note: string | undefined
  for (const raw of lines.slice(at + 1).filter(s => s.trim())) {
    const row = plain(raw)
    if (/^(?:如无特别说明|我建议|建议选择|您也可以)/.test(row) && options.length >= 2 && !note) { note = row; continue }
    const numbered = /^(\d+)[.、)）]\s*/.exec(row)
    if (note || (numbered ? Number(numbered[1]) !== options.length + 1 : !row.includes('——'))) return { text }
    const [label, ...parts] = row.slice(numbered?.[0].length ?? 0).split('——')
    options.push({ label, description: parts.join('——').replace(/[；;]$/, '') })
  }
  const question = validated({ kind: /可多选|哪些|哪几/.test(lines[at]!) ? 'multiple' : 'single', question: plain(lines[at]!), note, options })
  return question ? { text: lines.slice(0, at).join('\n').trimEnd(), question } : { text }
}

export function projectQuestion(text: string): QuestionMessage {
  const block = /(?:^|\n)```plaza-question[ \t]*\r?\n/.exec(text)
  if (!block) return legacyChoice(text)
  try {
    // Some models stop immediately after the complete JSON object and omit the closing fence.
    const body = text.slice(block.index + block[0].length).trimEnd().replace(/\r?\n```$/, '')
    const question = validated(JSON.parse(body))
    if (question) {
      const before = text.slice(0, block.index).trimEnd()
      const split = before.lastIndexOf('\n')
      const normalize = (s: string) => s.trim().replace(/^(?:首先[，,]\s*)?(?:请问)?/, '')
      const repeated = normalize(before.slice(split + 1)) === normalize(question.question)
      return { text: repeated ? before.slice(0, split < 0 ? 0 : split).trimEnd() : before, question }
    }
  } catch { /* Malformed model output remains an ordinary reply. */ }
  return { text }
}

const evidenceLabels = ['补充材料', '扩大范围', '按现有证据继续']

function evidenceChoice(): ChatQuestion {
  return {kind: 'single', question: '这项决定还缺关键依据。你希望怎样继续？', options: [
    {label: evidenceLabels[0], description: '提供能核实未决事项的材料，再评估结论。'},
    {label: evidenceLabels[1], description: '指定新增的调查对象、来源或时期。'},
    {label: evidenceLabels[2], description: '只回答有依据的部分，保留未决事项。'},
  ]}
}

function hasEvidenceChoices(text: string): boolean {
  return /(?:补充|提供|上传).{0,8}(?:材料|资料|证据|排课表)/s.test(text)
    && /(?:扩大|扩展).{0,8}(?:范围|调查|调研)/s.test(text)
    && /(?:现有|已有|当前).{0,6}(?:证据|材料|依据).{0,8}(?:继续|出稿|生成|作答)/s.test(text)
}

/** A missing source is a reason to pause only when the reply actually asks the
 * user to decide. Reports can describe gaps and recommend collecting data. */
function evidenceWait(text: string, question?: ChatQuestion): boolean {
  if (question) {
    const options = question.options.map(o => o.label).join(' ')
    if (hasEvidenceChoices(options)) return true
    // A genuine scope/other clarification must retain the model's question.
    if (!/材料|证据|(?:补充|上传).{0,15}(?:排课表|纪要|清单)/.test(question.question)) return false
  }
  const material = /(?:核心|关键)(?:缺口|缺证)|缺少.{0,12}(?:材料|证据)|待确认.{0,12}(?:学校|师资|场地|设备)|证据不足/s.test(text)
  const ask = /请(?:问|您|你)?[^。！？\n]{0,20}(?:上传|提供|选择|补充|回复)|选项.{0,6}选择|(?:需要|请)用户.{0,16}选择|(?:你|您)希望.{0,12}(?:继续|处理)/s
  const wording = [text, question?.question].join('\n')
  // A completed report may recommend gathering additional material in the
  // future. That recommendation must not suppress the report it accompanies.
  if (!question && !hasEvidenceChoices(text) &&
      /报告已(?:生成|完成|交付)|已(?:生成|交付).{0,15}(?:报告|简报)|^## (?:行动与适用条件|附录)/m.test(text)) return false
  return (material || hasEvidenceChoices(wording)) && (ask.test(wording) || !!question)
}

// Only a top-level trailing protocol block is a control attempt. Keep quoted
// examples and code with ordinary prose after their closing fence intact.
function trailingControl(text: string): { before: string; body: string } | undefined {
  const marker = /(?:^|\n)```plaza-question[ \t]*\r?\n/.exec(text)
  if (!marker) return
  const before = text.slice(0, marker.index).trimEnd()
  if ((before.match(/^`{3,}/gm)?.length ?? 0) % 2 || /(?:示例|格式如下|例如|example)[:：]?$/i.test(before)) return
  const body = text.slice(marker.index + marker[0].length)
  if (/^```[ \t]*\r?\n[\s\S]*\S/m.test(body)) return
  return { before, body }
}

export function projectIndustryReply(raw: string, interactive: boolean): QuestionMessage & { waiting: boolean } {
  const control = trailingControl(raw)
  const projected = !raw.includes('```plaza-question') || control ? projectQuestion(raw) : { text: raw }
  let text = projected.text
  let modelQuestion = projected.question
  if (control && !modelQuestion) {
    text = control.before
    // Do not copy malformed JSON into a reader-facing response. An explicit
    // evidence menu is sufficient to recover a choice, but never infer a choice from a user's answer.
    if (hasEvidenceChoices(control.body)) modelQuestion = evidenceChoice()
    else {
      const title = /"question"\s*:\s*("(?:[^"\\]|\\.)*")/.exec(control.body)?.[1]
      if (title) {
        try { modelQuestion = validated({ kind:'input', question:JSON.parse(title) }) } catch { /* truncated title */ }
      }
    }
  }
  const waiting = evidenceWait(text, modelQuestion)
  const standardMenu = modelQuestion?.kind === 'single' && modelQuestion.options.length === 3
    && evidenceLabels.every(label => modelQuestion.options.some(o => o.label === label))
  const question = waiting && !standardMenu ? evidenceChoice() : modelQuestion
  if (question && !interactive) {
    const lines = []
    if (!text.includes(question.question)) lines.push(question.question)
    for (const option of question.options) {
      if (!text.includes(option.label)) lines.push(option.description ? option.label + '：' + option.description : option.label)
    }
    if (lines.length) text += (text ? '\n\n' : '') + lines.join('\n')
  }
  return { text, question, waiting: waiting || !!question }
}
