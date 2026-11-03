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
