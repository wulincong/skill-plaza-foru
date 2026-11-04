<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { bySlug, catOf, GENERAL_SKILL_ID, GENERAL_SKILL_NAME, type Skill } from '../data/skills'
import { checkHealth, streamChat, ChatRequestError, type ChatAttachment, type ChatEvent, type ChatModelId, type ChatModelOption } from '../composables/useChatApi'
import { interruptSubmission, newRequestId, readSubmission, saveSubmission, type ChatSubmission } from '../composables/interruptedTask'
import { takePendingFormTask } from '../composables/pendingTask'
import { uploadFile, validateUploadFile, formatSize, type UploadedFile } from '../composables/useUpload'
import { fetchRunDetail, fetchRuns, runReportUrl, setConversationArchived, deleteConversation, type RunDetailResult } from '../api/runsApi'
import { OUTCOME_LABEL, type RunListItem } from '../data/runs'
import type { ReportChart as ReportChartData } from '../data/runs'
import Icon from '../components/Icon.vue'
import ReportOutput from '../components/ReportOutput.vue'
import type { ExecutionStep } from '../../shared/execution'
import type { ChatQuestion } from '../../shared/chatQuestion'
import ChatQuestionCard from '../components/ChatQuestionCard.vue'
import ChatModelPicker from '../components/ChatModelPicker.vue'
import ToolCallGroup from '../components/ToolCallGroup.vue'
import ConversationResources from '../components/ConversationResources.vue'
import { collectConversationResources } from '../composables/conversationResources'
import { publishedSkills, publishedSkill } from '../composables/catalog'
import { toast } from '../composables/toast'

/* 在线对话：广场的唯一对话与运行呈现面。
   后端就绪时真实流式运行（Pi）：默认通用智能体，$ 挂载技能；
   「任务配置」表单页提交的任务也交接到这里运行。
   历史侧栏展示测试人员共享的会话，可继续对话与整理历史。 */

interface Msg {
  question?: ChatQuestion
  runId?: string
  answerTo?: string
  role: 'user' | 'ai'
  text: string
  skill?: Skill
  done: boolean
  real?: boolean
  modelName?: string
  /** done 事件带回的图表与报告链接（表单任务/报告技能） */
  charts?: ReportChartData[]
  reportUrl?: string
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
  execution?: ExecutionStep[]
  durationMs?: number
}

interface Demo { slug: string; question: string; reply: string }
const DEMOS: Demo[] = [
  {
    slug: 'industry-education-report',
    question: '为广州高职院校分析机器人产业的岗位门槛，并提出实训建议',
    reply: `【演示输出 · 产教决策报告】\n\n■ 研究范围\n· 按广州机器人产业的在招岗位观察学历和经验要求，在图注保留样本范围、分母与读取时间。\n\n■ 课程建议\n· 对照岗位任务与现有实训项目，请合作企业核实学生能独立完成的操作。\n\n■ 待补证据\n· 毕业去向和实训容量由学校补充，再判断是否调整培养规模。`,
  },
  {
    slug: 'classroom-assistant',
    question: '把这节课的资料变成课堂练习和答疑助手',
    reply: `【演示输出 · 课堂助教】\n\n■ 已基于授权资料生成\n· 课堂要点 12 条，按教学顺序排列\n· 练习题 8 道（选择 5 / 简答 3），附答案与出处页码\n· 高频疑问 5 条，已整理成答疑口径\n\n■ 说明\n· 每条结论均附资料定位引用，可回原文核对`,
  },
  {
    slug: 'ai-interview',
    question: '模拟一轮产品经理岗位的 AI 面试',
    reply: `【演示输出 · AI 面试练习】\n\n■ 面试报告摘要\n· 覆盖题目 6 道：项目深挖 2 / 情景应对 2 / 岗位认知 2\n· 每道题支持追问与重答，回答均保留原话引用\n\n■ 能力地图\n· 表达结构：良好｜岗位认知：待加强｜项目量化：待补充\n\n■ 待验证项\n· "用户增长 30%" 缺少口径说明，已标记为待核实`,
  },
  {
    slug: 'career-guidance',
    question: '判断这个 Java 后端实习岗位我合不合适，再给一份行动计划',
    reply: `【演示输出 · 就业指导】\n\n■ 岗位匹配证据表\n· 已证明：Spring Boot 接口开发（校园项目可佐证）\n· 部分证明：MySQL 数据建模（有实践、缺规模）\n· 关键缺口：分布式与中间件经验（岗位标注"优先"）\n\n■ 30 天行动建议\n· 第 1 周：补消息队列入门，产出学习笔记\n· 第 2–3 周：项目补并发场景改造，重写简历项目段\n· 第 4 周：按每周 5 家投递并复盘\n\n■ 待核实\n· 岗位"转正后 8–12K"的口径与绩效占比`,
  },
  {
    slug: 'training-data-qa',
    question: '构造一批客服领域的训练样本并做质检',
    reply: `【演示输出 · 训练样本构造与标注质检】\n\n■ 样本构造\n· 四类划分：指令跟随 / 事实问答 / 拒答 / 边界探索\n· 本批生成 200 条候选样本，机器质检通过率 86%\n\n■ 质检说明\n· 候选结果 ≠ 专家确认，全部样本待人工抽检\n· 全程保留来源与谱系，可追溯`,
  },
  {
    slug: 'doc-translate',
    question: '把这份英文 PDF 文档全文翻译成中文',
    reply: '请连接运行服务，上传一份带文本层的 PDF，并说明目标语言。翻译完成后会提供译文 PDF 的查看和下载链接。',
  },
]

const FALLBACK = '当前未连接到运行服务，请稍后重新打开在线对话并提交任务。'

const textarea = ref('')
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const sending = ref(false)
const messages = ref<Msg[]>([])
const mobileHistoryOpen = ref(false)
const pendingQuestion = computed(() => {
  const last = messages.value[messages.value.length - 1]
  return last?.question && last.runId ? last : undefined
})
function replyText(index: number) {
  const reply = messages.value[index + 1]
  const question = messages.value[index]
  return question?.question && question.runId && reply?.answerTo === question.runId ? reply.text : undefined
}
const resources = computed(() => collectConversationResources(messages.value))
const resourcePanel = ref<InstanceType<typeof ConversationResources>>()
function resourceCount(message: Msg) {
  const published = (message.webLinks?.length ?? 0) + (message.downloads?.length ?? 0)
  return published || (message.reportUrl ? (message.skill?.slug === 'doc-translate' ? 1 : 2) : 0)
}
/* 附件（真实运行）：上传到会话沙箱 uploads/，随下一条消息发送；
   已上传文件属于当前技能绑定的沙箱目录，技能切换/新对话即失效（见 pickSkill/newChat） */
const pendingAttachments = ref<UploadedFile[]>([])
const attachUploading = ref(false)
const attachInputEl = ref<HTMLInputElement | null>(null)
/* 当前对话 id（后端会话与技能绑定的 key）；null = 下一条消息开新会话 */
const currentConvId = ref<number | null>(null)
const streamTimer: { value: ReturnType<typeof setInterval> | null } = { value: null }
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)')

/* 每个对话对应一个 Pi 后端会话（多轮上下文保留）；技能与会话绑定。
   reactive Map：session 事件异步写入后，依赖它的 computed（侧栏实时条目/运行徽章）才会重算 */
const convSessions = reactive(new Map<string, string>())
const convSlugs = reactive(new Map<number, string>())

/* 运行阶段实时状态行 + 计时 */
const runStatus = ref('')
const elapsedMs = ref(0)
let elapsedTimer: ReturnType<typeof setInterval> | null = null
function formatElapsed(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}分${String(seconds % 60).padStart(2, '0')}秒`
}
let elapsedStart = 0
function beginRun() {
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedStart = Date.now()
  elapsedMs.value = 0
  elapsedTimer = setInterval(() => { elapsedMs.value = Math.max(0, Date.now() - elapsedStart) }, 250)
}
function endRun() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

/* ---------- 后端就绪探测：就绪则真实流式，否则演示输出 ---------- */
const apiReady = ref(false)
const apiModel = ref('')

const models = ref<ChatModelOption[]>([])
const selectedModel = ref<ChatModelId>()
let defaultChatModel: ChatModelId | undefined

async function probeApi() {
  const result = await checkHealth()
  apiReady.value = result.ok
  apiModel.value = result.model ?? ''
  models.value = result.chatModels ?? []
  defaultChatModel = result.defaultChatModel
  selectedModel.value = defaultChatModel
}

function onDocClick(event: MouseEvent) {
  if (skillMenu.value && !(event.target as HTMLElement | null)?.closest('.exp-input-box')) skillMenu.value = false
}

const EXAMPLES = computed(() => DEMOS.filter(d => publishedSkills.value.some(s => s.slug === d.slug)).map(d => ({ slug: d.slug, question: d.question, skill: bySlug.get(d.slug) })))

/* ---- $ 技能选择：默认通用智能体（不挂技能），输入 $ 或点 $ 钮呼出选择器 ---- */
const activeSkill = ref<Skill | undefined>()
const skillMenu = ref(false)
const skillQuery = ref('')
const skillHighlight = ref(0)
const skillMatches = computed(() => {
  const q = skillQuery.value.trim().toLowerCase()
  const list = publishedSkills.value.filter(s =>
    !q || s.slug.toLowerCase().includes(q) || s.name.toLowerCase().includes(q) || s.tags.some(t => t.toLowerCase().includes(q)))
  return list.slice(0, 8)
})
/* 光标前的未完成 $token（$ 起、空白止）命中时呼出选择器 */
const MENTION_RE = /(?:^|\s)\$([^\s$]*)$/
function syncSkillMenu() {
  const el = textareaEl.value
  if (!el) { skillMenu.value = false; return }
  const m = el.value.slice(0, el.selectionStart ?? el.value.length).match(MENTION_RE)
  if (m) {
    if (!skillMenu.value) skillHighlight.value = 0
    skillQuery.value = m[1]
    skillMenu.value = true
  } else {
    skillMenu.value = false
    skillQuery.value = ''
  }
}
function toggleSkillMenu() {
  if (skillMenu.value) { skillMenu.value = false; return }
  skillQuery.value = ''
  skillHighlight.value = 0
  skillMenu.value = true
  textareaEl.value?.focus()
}
/* ---------- 附件：上传到会话沙箱，随下一条消息发送 ---------- */
function triggerAttach() {
  if (!apiReady.value) {
    toast('演示环境不支持附件，请启动本地后端后使用')
    return
  }
  attachInputEl.value?.click()
}
async function onAttachPicked(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (sending.value || attachUploading.value) return
  if (pendingAttachments.value.length >= 5) { toast('最多同时附 5 个文件'); return }
  for (const file of files.slice(0, 5 - pendingAttachments.value.length)) {
    const invalid = validateUploadFile(file)
    if (invalid) {
      toast(`${file.name}：${invalid}`)
      continue
    }
    attachUploading.value = true
    try {
      /* 上传必须落进运行将使用的沙箱目录：已有会话直接复用；首条上传前先起对话骨架 */
      if (currentConvId.value === null) currentConvId.value = Date.now()
      const key = `pi:${currentConvId.value}`
      /* 在上传前完成技能绑定；否则 send() 换技能时会丢掉刚上传文件的会话。 */
      const requested = activeSkill.value?.slug ?? GENERAL_SKILL_ID
      const bound = convSlugs.get(currentConvId.value)
      if (bound !== undefined && bound !== requested) convSessions.delete(key)
      convSlugs.set(currentConvId.value, requested)
      const uploaded = await uploadFile(file, convSessions.get(key))
      if (key !== `pi:${currentConvId.value}` || requested !== (activeSkill.value?.slug ?? GENERAL_SKILL_ID)) return
      convSessions.set(key, uploaded.sessionId)
      pendingAttachments.value.push(uploaded)
    } catch (exc) {
      toast(exc instanceof Error ? exc.message : '附件上传失败')
    } finally {
      attachUploading.value = false
    }
  }
}
function removeAttachment(index: number) {
  pendingAttachments.value.splice(index, 1)
}

function pickSkill(skill: Skill) {
  activeSkill.value = skill
  /* 附件落在旧技能绑定的沙箱目录，换技能后旧会话可能被弃用，一并清空 */
  pendingAttachments.value = []
  /* 移除触发选择的 $token（经 $ 钮呼出时没有 token，只挂载技能） */
  const el = textareaEl.value
  if (el) {
    const caret = el.selectionStart ?? el.value.length
    const m = el.value.slice(0, caret).match(MENTION_RE)
    if (m && m.index !== undefined) {
      const tokenStart = m.index + m[0].length - m[1].length - 1
      textarea.value = el.value.slice(0, tokenStart) + el.value.slice(caret)
      nextTick(() => { el.focus(); el.setSelectionRange(tokenStart, tokenStart) })
    } else {
      el.focus()
    }
  }
  skillMenu.value = false
  skillQuery.value = ''
}
function clearSkill() {
  activeSkill.value = undefined
  pendingAttachments.value = []
  textareaEl.value?.focus()
}
function onTextareaKeydown(event: KeyboardEvent) {
  if (skillMenu.value && skillMatches.value.length) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const n = skillMatches.value.length
      skillHighlight.value = (skillHighlight.value + (event.key === 'ArrowDown' ? 1 : n - 1)) % n
      return
    }
    if ((event.key === 'Enter' || event.key === 'Tab') && !event.isComposing) {
      event.preventDefault()
      pickSkill(skillMatches.value[Math.min(skillHighlight.value, skillMatches.value.length - 1)])
      return
    }
  }
  if (event.key === 'Escape' && skillMenu.value) { skillMenu.value = false; return }
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

function scrollTop() {
  /* 整页滚动：滚到文档底部（输入框吸底在流下方） */
  nextTick(() => { window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' }) })
}

function stopTyping() {
  if (streamTimer.value) { clearInterval(streamTimer.value); streamTimer.value = null }
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'ai' && !last.done) last.done = true
  sending.value = false
}

function newChat() {
  selectionSeq++
  loadingConversation.value = false
  clearRecovery()
  stopTyping()
  clearHistorySelection()
  mobileHistoryOpen.value = false
  currentConvId.value = null
  messages.value = []
  textarea.value = ''
  pendingAttachments.value = []
}

/* ---------- 演示输出：逐字打字机效果（后端未就绪时） ---------- */
function startAiMsg(skill: Skill | undefined, real: boolean): Msg {
  messages.value.push({ role: 'ai', text: '', skill, done: false, real })
  const msg = messages.value[messages.value.length - 1]
  scrollTop()
  return msg
}
function typeInto(msg: Msg, reply: string) {
  if (reducedMotion.matches) {
    msg.text = reply
    msg.done = true
    sending.value = false
    return
  }
  streamTimer.value = setInterval(() => {
    msg.text = reply.slice(0, msg.text.length + 3)
    scrollTop()
    if (msg.text.length >= reply.length) {
      msg.text = reply
      msg.done = true
      sending.value = false
      if (streamTimer.value) { clearInterval(streamTimer.value); streamTimer.value = null }
    }
  }, 24)
}

/* ---------- 真实运行：走本地 Node 后端 → Pi，SSE 流式回填 ---------- */
interface RunOptions { answerTo?: string; taskTitle?: string; attachments?: ChatAttachment[] }
const resumable = ref<ChatSubmission | null>(null)
const recoveryFailed = ref(false)
let inFlight: ChatSubmission | null = null
let leaving = false

function clearRecovery() {
  resumable.value = null
  recoveryFailed.value = false
  saveSubmission(null)
}

function onPageShow(event: PageTransitionEvent) {
  if (event.persisted && leaving) window.location.reload()
}

function leavePage() {
  leaving = true
  if (inFlight) void interruptSubmission(inFlight, true).catch(() => {})
}

function makeStreamHandler(msg: Msg, sessionKey: string) {
  return (event: ChatEvent) => {
    if (event.type === 'session') {
      /* 服务端发回本轮会话 id（首轮新建、被回收后重建都会发）：记住它，后续轮次带上下文多轮 */
      convSessions.set(sessionKey, event.sessionId)
    } else if (event.type === 'started') {
      msg.runId = event.runId
      elapsedStart = event.startedAt
      elapsedMs.value = Math.max(0, Date.now() - elapsedStart)
      runStatus.value = '正在思考…'
    } else if (event.type === 'execution') {
      msg.execution ??= []
      msg.execution[event.index] = event.step
    } else if (event.type === 'status') {
      if (event.phase === 'tool') runStatus.value = event.state === 'active' ? '正在执行工具…' : '正在继续处理…'
      else if (event.phase === 'text') runStatus.value = '正在生成回复…'
      else runStatus.value = event.phase === 'initializing' ? '正在启动…' : '正在思考…'
    } else if (event.type === 'text') {
      msg.text += event.delta
      scrollTop()
    } else if (event.type === 'done') {
      if (event.question || event.content) msg.text = event.content
      msg.question = event.question
      if (event.question) nextTick(() => document.getElementById('question-' + msg.runId)?.scrollIntoView({ block: 'nearest' }))
      msg.durationMs = event.durationMs
      msg.charts = event.charts ?? []
      msg.reportUrl = event.reportUrl
      msg.webLinks = event.webLinks
      msg.downloads = event.downloads
    } else if (event.type === 'error') {
      msg.durationMs = event.durationMs
      throw new Error(event.message)
    }
  }
}

async function runReal(text: string, slug: string, skill: Skill | undefined, opts: RunOptions = {}, retry?: ChatSubmission) {
  const convId = currentConvId.value
  if (convId === null) return
  const msg = startAiMsg(skill, true)
  convSlugs.set(convId, slug)
  const sessionKey = `pi:${convId}`
  const task: ChatSubmission = retry ?? {
    sessionId: convSessions.get(sessionKey) ?? 'sess-' + newRequestId(),
    requestId: newRequestId(), skill: slug, model: selectedModel.value, text, ...opts,
  }
  convSessions.set(sessionKey, task.sessionId)
  inFlight = task
  resumable.value = null
  saveSubmission(task)
  beginRun()
  let terminal = false
  try {
    const handle = makeStreamHandler(msg, sessionKey)
    await streamChat({
      interactive: true, ...task, messages: [{ role: 'user', content: task.text }],
      onEvent(event) {
        if (event.type === 'done' || event.type === 'error') {
          terminal = true
          if (!leaving) saveSubmission(event.type === 'done' && event.question ? task : null)
        }
        handle(event)
      },
    })
    msg.modelName = models.value.find(m => m.id === task.model)?.name ?? apiModel.value
  } catch (error) {
    if (!leaving && task.answerTo && error instanceof ChatRequestError && error.status === 409) {
      // Another tab may have answered. Reload the server's latest turn instead of offering to replay this reply.
      messages.value.splice(-2)
      clearRecovery()
      toast(error.message)
      const state = await interruptSubmission(task).catch(() => null)
      if (state?.latest) await openRun(state.latest)
    } else if (!leaving) {
      if (!terminal) recoveryFailed.value = true
      const reason = error instanceof Error ? error.message : '请求失败，请稍后重试。'
      msg.text += `${msg.text ? '\n\n' : ''}${reason}`
    }
  } finally {
    inFlight = null
    msg.done = true
    endRun()
    sending.value = false
  }
}

function continueTask() {
  const task = resumable.value
  if (!task || sending.value || loadingConversation.value) return
  if (!apiReady.value) { toast('运行服务未连接，请刷新后重试。'); return }
  sending.value = true
  activeSkill.value = bySlug.get(task.skill)
  selectedModel.value = task.model
  if (task.resumeOf) messages.value.push({ role: 'user', text: '继续任务', done: true })
  runStatus.value = '正在启动…'
  void runReal(task.text, task.skill, activeSkill.value, {}, task)
}

function answerQuestion(question: Msg, text: string) {
  if (pendingQuestion.value !== question || !question.runId || sending.value || loadingConversation.value || attachUploading.value) return
  if (!apiReady.value) { toast('运行服务未连接，请刷新后重试。'); return }
  clearRecovery()
  sending.value = true
  activeSkill.value = question.skill
  messages.value.push({ role: 'user', text, done: true, answerTo: question.runId })
  void runReal(text, question.skill?.slug ?? GENERAL_SKILL_ID, question.skill, { answerTo: question.runId })
}

async function send(raw?: string) {
  const text = (raw ?? textarea.value).trim()
  if (!text || sending.value || loadingConversation.value || attachUploading.value) return

  /* 翻译依赖附件与真实服务：离线时保留输入，重试时重新探测连接。 */
  if (activeSkill.value?.slug === 'doc-translate' && !apiReady.value) {
    sending.value = true
    try { await probeApi() } finally { sending.value = false }
    if (!apiReady.value) { toast('翻译服务未连接，请启动后端后重试。'); return }
  }

  clearRecovery()
  if (currentConvId.value === null) currentConvId.value = Date.now()
  skillMenu.value = false

  /* 附件随本条消息一次性消费；上屏文本附文件名便于回看 */
  const pending = pendingQuestion.value
  const answerTo = pending && pending.skill?.slug === activeSkill.value?.slug ? pending.runId : undefined
  const attachments = pendingAttachments.value.splice(0)
  const shownText = attachments.length ? `${text}\n[附件] ${attachments.map(a => a.name).join('、')}` : text
  messages.value.push({ role: 'user', text: shownText, done: true, answerTo })
  textarea.value = ''
  sending.value = true
  runStatus.value = ''
  elapsedMs.value = 0

  /* 默认通用智能体；$ 挂载的技能只作用于后续消息 */
  const skill = activeSkill.value
  const requested = skill?.slug ?? GENERAL_SKILL_ID

  if (apiReady.value) {
    /* 会话与技能绑定：换技能即弃用旧后端会话（其上下文属于旧技能），下轮新建 */
    const convId = currentConvId.value
    if (convId !== null) {
      const bound = convSlugs.get(convId)
      if (bound !== requested) {
        if (bound !== undefined) convSessions.delete(`pi:${convId}`)
        convSlugs.set(convId, requested)
      }
    }
    void runReal(text, requested, skill, { answerTo, attachments: attachments.length
      ? attachments.map(a => ({ name: a.name, path: a.path })) : undefined })
    return
  }
  const demo = skill ? DEMOS.find(d => d.slug === skill.slug) : undefined
  typeInto(startAiMsg(skill, false), demo ? demo.reply : FALLBACK)
}

/* ---------- 表单任务承接：任务配置页 stash → 这里挂载技能并发起运行 ---------- */
function consumePendingFormTask() {
  const task = takePendingFormTask()
  if (!task) return false
  clearRecovery()
  const skill = publishedSkill(task.slug)
  if (!skill) { toast('该技能当前未上架，请选择其他技能。'); return true }
  activeSkill.value = skill
  stopTyping()
  clearHistorySelection()
  mobileHistoryOpen.value = false
  currentConvId.value = Date.now()
  messages.value = []
  textarea.value = ''

  messages.value.push({ role: 'user', text: task.prompt, done: true })
  sending.value = true
  runStatus.value = ''
  elapsedMs.value = 0
  convSlugs.set(currentConvId.value, task.slug)
  /* 沿用表单上传的沙箱会话：引擎才能读到已上传附件 */
  if (task.sessionId) convSessions.set(`pi:${currentConvId.value}`, task.sessionId)

  if (!apiReady.value) {
    if (task.slug === 'doc-translate') {
      const msg = startAiMsg(skill, true)
      msg.text = '翻译服务未连接，请启动后端后重新提交。'
      msg.done = true
      sending.value = false
      return true
    }
    const demo = skill ? DEMOS.find(d => d.slug === skill.slug) : undefined
    typeInto(startAiMsg(skill, false), demo ? demo.reply : FALLBACK)
    return true
  }
  void runReal(task.prompt, task.slug, skill, { taskTitle: task.taskTitle, attachments: task.attachments })
  return true
}

function fill(slug: string) {
  const demo = DEMOS.find(d => d.slug === slug)
  if (demo) {
    textarea.value = demo.question
    /* 示例即技能问题：挂上对应技能，脱离 $ 的模糊匹配 */
    activeSkill.value = bySlug.get(slug)
    textareaEl.value?.focus()
  }
}
const skillTitle = (slug: string) => bySlug.get(slug)?.name ?? ''
const skillCat = (slug: string) => { const s = bySlug.get(slug); return s ? catOf(s.categoryId).name : '' }

/* ---------- 历史运行记录：侧栏按对话（clientSessionId）分组，点开直接载入对话流 ---------- */
const historyRuns = ref<RunListItem[]>([])
const archivedRuns = ref<RunListItem[]>([])
const historyLive = ref(false)
const archivedLive = ref(false)
const historyLoading = ref(true)
/** 当前选中的对话（key = clientSessionId，旧记录退化为其 runId） */
const selectedSessionKey = ref<string | null>(null)
/** 历史对话载入中（主区显示一行提示，避免空态示例闪现） */
const loadingConversation = ref(false)

/** 一个对话 = 同一 clientSessionId 的全部运行；换技能/新建对话会开新会话，天然分组边界 */
interface HistoryGroup {
  key: string
  title: string
  skill: string
  /** 最新一次运行（trace 是会话累计快照，最新记录包含完整对话） */
  latest: RunListItem
  count: number
  archived: boolean
  /** 当前对话的实时占位条目（运行记录落库前显示；不可点开、不可归档） */
  live?: boolean
  /** 该对话正在运行：结局徽章换成「运行中」 */
  running?: boolean
}

interface HistoryDetail {
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
  conversation: NonNullable<RunDetailResult['conversation']>
  /** 该对话生成的 HTML 报告（内联在最后一条 AI 消息上，与实时对话一致） */
  reportUrl?: string
}
const historyDetails = reactive<Record<string, HistoryDetail>>({})
let selectionSeq = 0

const skillNameOf = (slug: string) => bySlug.get(slug)?.name ?? (slug === GENERAL_SKILL_ID ? GENERAL_SKILL_NAME : slug)

function fmtTime(ts: number | string): string {
  const d = new Date(ts)
  return d.toDateString() === new Date().toDateString()
    ? `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    : `${d.getMonth() + 1}/${d.getDate()}`
}

/* 运行记录 → 对话分组（旧记录无 clientSessionId 时退化为单运行一组）；常规与归档列表共用 */
function groupRuns(runs: RunListItem[], archived: boolean): HistoryGroup[] {
  const bySession = new Map<string, RunListItem[]>()
  for (const run of runs) {
    const key = run.clientSessionId || run.runId
    const bucket = bySession.get(key)
    if (bucket) bucket.push(run)
    else bySession.set(key, [run])
  }
  const groups = [...bySession.values()].map(items => {
    const sorted = [...items].sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts))
    const oldest = sorted[sorted.length - 1]
    return {
      key: oldest.clientSessionId || oldest.runId,
      title: oldest.taskTitle || oldest.promptDigest || '历史对话',
      skill: oldest.skill,
      latest: sorted[0],
      count: sorted.length,
      archived,
    }
  })
  return groups.sort((a, b) => Date.parse(b.latest.ts) - Date.parse(a.latest.ts))
}
const historyGroups = computed(() => groupRuns(historyRuns.value, false))
const archivedGroups = computed(() => groupRuns(archivedRuns.value, true))

/** 当前对话绑定的服务端会话（sess-*；首轮 session 事件到达后可用） */
const liveSessionKey = computed(() => {
  const convId = currentConvId.value
  return convId === null ? undefined : convSessions.get(`pi:${convId}`)
})
/** 落库重试用尽仍无记录时撤掉实时条目，避免幽灵对话常驻侧栏（下次运行自动复位） */
const liveDismissed = ref(false)

/* 当前对话的实时侧栏条目：运行记录要等运行结束才在服务端落库，落库前由它占位
   （ChatGPT 式：发出第一条消息对话即入列）；真实分组出现后无缝接管。 */
const liveConvGroup = computed<HistoryGroup | null>(() => {
  if (!apiReady.value || liveDismissed.value) return null
  const convId = currentConvId.value
  if (convId === null) return null
  const firstUser = messages.value.find(m => m.role === 'user')
  if (!firstUser) return null
  const sessionKey = convSessions.get(`pi:${convId}`)
  if (sessionKey && [...historyGroups.value, ...archivedGroups.value].some(g => g.key === sessionKey)) return null
  /* session 事件未到且不在运行：请求没到服务端，不会有落库记录 */
  if (!sessionKey && !sending.value) return null
  const title = firstUser.text.replace(/\s+/g, ' ').slice(0, 80)
  const slug = convSlugs.get(convId) ?? GENERAL_SKILL_ID
  return {
    key: `live:${convId}`,
    live: true,
    running: sending.value,
    title: title || '新对话',
    skill: slug,
    latest: {
      runId: `live:${convId}`,
      ts: new Date(convId).toISOString(),
      clientSessionId: '',
      promptDigest: title,
      outcome: 'success',
      skill: slug,
      durationMs: 0,
    },
    count: 1,
    archived: false,
  }
})

/** 固定入口切换列表，保留正在阅读的对话。 */
const showArchived = ref(false)
const sidebarSections = computed(() => {
  const now = new Date()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  const sections: { label: string; items: HistoryGroup[] }[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '更早', items: [] },
  ]
  const live = !showArchived.value && liveConvGroup.value
  if (live) sections[0].items.push(live)
  for (const group of showArchived.value ? archivedGroups.value : historyGroups.value) {
    const date = new Date(group.latest.ts).toDateString()
    const section = date === now.toDateString() ? sections[0] : date === yesterday.toDateString() ? sections[1] : sections[2]
    const running = sending.value && group.key === liveSessionKey.value
    section.items.push(running ? { ...group, running: true } : group)
  }
  return sections.filter(s => s.items.length)
})

function clearHistorySelection() {
  selectedSessionKey.value = null
}

function historicalModel(provider?: string | null, modelId?: string | null) {
  return models.value.find(m => m.provider === provider && m.modelId === modelId)
}

/* 点开历史 = 把对话载入正常消息流（与 ChatGPT 一致）：无专门结果卡，
   报告链接内联在最后一条 AI 消息；同时恢复服务端会话，可直接继续对话。 */
async function selectHistory(group: HistoryGroup) {
  /* 实时占位条目就是当前对话，点击不重新载入 */
  if (group.live) return
  if (sending.value) {
    toast('当前运行进行中，完成后才能查看历史对话')
    return
  }
  mobileHistoryOpen.value = false
  if (selectedSessionKey.value === group.key) return
  clearRecovery()
  await openRun(group.latest)
}

async function openRun(run: RunListItem, seq = ++selectionSeq) {
  selectedSessionKey.value = run.clientSessionId || run.runId
  const restore = (detail: HistoryDetail) => {
    const skill = bySlug.get(run.skill)
    stopTyping()
    currentConvId.value = Date.now()
    convSlugs.set(currentConvId.value, run.skill)
    /* 后端优先复用内存会话，重启/回收后从同一工作区恢复持久上下文。 */
    if (run.clientSessionId) convSessions.set(`pi:${currentConvId.value}`, run.clientSessionId)
    activeSkill.value = skill
    selectedModel.value = historicalModel(run.tokenUsage?.provider, run.tokenUsage?.model)?.id ?? defaultChatModel
    let lastAi = -1
    detail.conversation.forEach((turn, i) => { if (turn.role === 'assistant') lastAi = i })
    messages.value = detail.conversation.map((turn, i) => turn.role === 'user'
      ? { role: 'user', text: turn.text, done: true, answerTo: turn.answerTo }
      : { role: 'ai', text: turn.text, question: turn.question, runId: turn.runId, skill, modelName: historicalModel(turn.provider, turn.model)?.name ?? turn.model ?? turn.provider, done: true, real: true, reportUrl: i === lastAi ? detail.reportUrl : undefined, webLinks: turn.webLinks ?? (i === lastAi ? detail.webLinks : undefined), downloads: turn.downloads ?? (i === lastAi ? detail.downloads : undefined), execution: turn.execution, durationMs: turn.durationMs })
    if (pendingQuestion.value && run.requestId && run.clientSessionId) {
      saveSubmission({ requestId: run.requestId, sessionId: run.clientSessionId, text: run.userMessage ?? '', skill: run.skill, model: selectedModel.value })
    }
    if (run.clientSessionId && run.engine === 'pi' && run.outcome === 'aborted' && run.userMessage) {
      resumable.value = {
        requestId: newRequestId(), sessionId: run.clientSessionId, resumeOf: run.runId, text: '继续任务',
        skill: run.skill, model: selectedModel.value, taskTitle: run.taskTitle,
      }
    }
    scrollTop()
  }

  const cached = historyDetails[run.runId]
  if (cached) { restore(cached); loadingConversation.value = false; return true }

  loadingConversation.value = true
  try {
    const result = await fetchRunDetail(run.runId)
    if (seq !== selectionSeq) return
    if (!result.live || !(result.conversation ?? []).length) throw new Error('empty')
    const detail: HistoryDetail = {
      conversation: result.conversation ?? [],
      reportUrl: (result.item?.files?.html || result.item?.files?.pdf) ? runReportUrl(run.runId) : undefined,
      webLinks: result.item?.webLinks,
      downloads: result.item?.downloads,
    }
    historyDetails[run.runId] = detail
    restore(detail)
    return true
  } catch {
    if (seq === selectionSeq) {
      selectedSessionKey.value = null
      toast('历史对话加载失败，请稍候重试')
    }
  } finally {
    if (seq === selectionSeq) loadingConversation.value = false
  }
}

async function recoverSubmission(task: ChatSubmission) {
  const seq = ++selectionSeq
  loadingConversation.value = true
  recoveryFailed.value = false
  resumable.value = null
  try {
    let result = await interruptSubmission(task)
    for (let i = 0; result.state === 'settling' && i < 30; i++) {
      await new Promise(resolve => setTimeout(resolve, 400))
      if (leaving || seq !== selectionSeq) return
      result = await interruptSubmission(task)
    }
    if (leaving || seq !== selectionSeq) return
    if (result.state === 'settling') throw new Error()
    if (result.latest) {
      if (!await openRun(result.latest, seq)) throw new Error()
      if (result.state === 'saved' || ((task.resumeOf || task.answerTo) && result.latest.runId !== (task.resumeOf || task.answerTo))) {
        if (!resumable.value && !pendingQuestion.value) saveSubmission(null)
        return
      }
    }
    // The POST never reached the server (possibly before the first SSE frame).
    // Only the replacement ID returned by the server can submit the saved input.
    if (!result.latest) messages.value = []
    currentConvId.value ??= Date.now()
    convSessions.set(`pi:${currentConvId.value}`, task.sessionId)
    convSlugs.set(currentConvId.value, task.skill)
    activeSkill.value = bySlug.get(task.skill)
    selectedModel.value = task.model
    if (!task.resumeOf) {
      const names = task.attachments?.map(file => file.name)
      messages.value.push({ role: 'user', answerTo: task.answerTo, text: task.text + (names?.length ? '\n[附件] ' + names.join('、') : ''), done: true })
    }
    if (!result.retryId) throw new Error()
    resumable.value = { ...task, requestId: result.retryId }
    saveSubmission(task)
  } catch {
    if (seq === selectionSeq) recoveryFailed.value = true
  } finally {
    if (seq === selectionSeq) loadingConversation.value = false
  }
}

function retryRecovery() {
  const task = readSubmission()
  if (task) void recoverSubmission(task)
}

/* 防重入与显示态分开：初始 loading=true 只为避免空态闪现，不代表有请求在途；
   silent 重拉不切 loading 态（侧栏列表保持可读，重试不打扰） */
let historyReqInFlight = false
async function loadHistory(opts: { silent?: boolean } = {}) {
  if (historyReqInFlight) return
  historyReqInFlight = true
  if (!opts.silent) historyLoading.value = true
  try {
    const [result, archived] = await Promise.all([fetchRuns(), fetchRuns({ archived: true })])
    historyRuns.value = result.live ? result.runs : []
    archivedRuns.value = archived.runs
    archivedLive.value = archived.live
    historyLive.value = result.live
    if (!result.live) {
      clearHistorySelection()
      return
    }
    /* 当前对话（新建/表单交接/历史恢复）在列表刷新后保持或获得高亮 */
    const activeSession = currentConvId.value !== null ? convSessions.get(`pi:${currentConvId.value}`) : undefined
    if (selectedSessionKey.value && ![...historyGroups.value, ...archivedGroups.value].some(g => g.key === selectedSessionKey.value)) {
      clearHistorySelection()
    } else if (!selectedSessionKey.value && activeSession && historyGroups.value.some(g => g.key === activeSession)) {
      selectedSessionKey.value = activeSession
    }
  } finally {
    historyReqInFlight = false
    if (!opts.silent) historyLoading.value = false
  }
}

/* ---------- 会话归档/删除（操作成功后刷新两个列表） ---------- */
const confirmDeleteKey = ref<string | null>(null)
let confirmDeleteTimer: ReturnType<typeof setTimeout> | null = null

async function archiveConversation(group: HistoryGroup, archived: boolean) {
  if (sending.value) {
    toast('当前运行进行中，完成后才能操作')
    return
  }
  const ok = await setConversationArchived(group.key, archived)
  if (!ok) {
    toast('操作失败，请稍候重试')
    return
  }
  toast(archived ? '已归档，可在侧栏「已归档」查看' : '已恢复到对话列表')
  void loadHistory()
}

function onDeleteClick(group: HistoryGroup) {
  if (sending.value) {
    toast('当前运行进行中，完成后才能操作')
    return
  }
  /* 两步确认：第一次点红显确认态，2.5 秒内再点才执行 */
  if (confirmDeleteKey.value !== group.key) {
    confirmDeleteKey.value = group.key
    if (confirmDeleteTimer) clearTimeout(confirmDeleteTimer)
    confirmDeleteTimer = setTimeout(() => { confirmDeleteKey.value = null }, 2500)
    return
  }
  if (confirmDeleteTimer) { clearTimeout(confirmDeleteTimer); confirmDeleteTimer = null }
  confirmDeleteKey.value = null
  void runDelete(group)
}
async function runDelete(group: HistoryGroup) {
  const ok = await deleteConversation(group.key)
  if (!ok) {
    toast('删除失败，请稍候重试')
    return
  }
  toast('对话已删除')
  delete historyDetails[group.latest.runId]
  if (selectedSessionKey.value === group.key) newChat()
  void loadHistory()
}

/* 运行结束后刷新历史列表（新记录入列）；新开运行时复位实时条目 */
watch(sending, (now, was) => {
  if (now) {
    liveDismissed.value = false
    return
  }
  if (was) void refreshHistoryAfterRun()
})

/* 服务端在 done SSE 之后才异步落库（exportTrace → appendIndex），运行一结束就刷新
   经常扑空：首刷未命中当前会话时延迟重拉几次；始终未命中则撤掉实时条目。 */
async function refreshHistoryAfterRun() {
  const sessionKey = liveSessionKey.value
  await loadHistory({ silent: true })
  if (!sessionKey || [...historyGroups.value, ...archivedGroups.value].some(g => g.key === sessionKey)) return
  for (let i = 0; i < 3 && historyLive.value; i++) {
    await new Promise(resolve => setTimeout(resolve, 1200))
    await loadHistory({ silent: true })
    if ([...historyGroups.value, ...archivedGroups.value].some(g => g.key === sessionKey)) return
  }
  liveDismissed.value = true
}

/* 无表单技能的广场入口：只挂载技能，任务仍由用户在对话中输入。 */
const route = useRoute()
watch(() => route.query.skill, (slug) => {
  if (typeof slug !== 'string') return
  const skill = publishedSkill(slug)
  if (skill) pickSkill(skill)
}, { immediate: true })

onMounted(async () => {
  window.addEventListener('pagehide', leavePage)
  window.addEventListener('pageshow', onPageShow)
  document.addEventListener('click', onDocClick)
  const task = readSubmission()
  loadingConversation.value = Boolean(task)
  await probeApi()
  if (leaving) return
  if (consumePendingFormTask()) loadingConversation.value = false
  else if (task) await recoverSubmission(task)
  if (!leaving) void loadHistory()
})
onBeforeUnmount(() => {
  leaving = true
  window.removeEventListener('pagehide', leavePage)
  window.removeEventListener('pageshow', onPageShow)
  document.removeEventListener('click', onDocClick)
  if (streamTimer.value) clearInterval(streamTimer.value)
  endRun()
})
</script>

<template>
  <section class="page page-exp" :class="{ 'has-resources': resources.length && !loadingConversation }">
    <button type="button" class="exp-history-toggle" aria-controls="conversation-history" :aria-expanded="mobileHistoryOpen" @click="mobileHistoryOpen = !mobileHistoryOpen">
      <Icon name="chat" :size="15" />{{ mobileHistoryOpen ? '收起历史对话' : '查看历史对话' }}
    </button>
    <aside id="conversation-history" class="exp-side" :class="{ 'is-open': mobileHistoryOpen }">
      <button type="button" class="exp-new" :disabled="sending" @click="showArchived = false; newChat()">
        <Icon name="plus" :size="15" />
        新建对话
      </button>
      <div :key="showArchived ? 'archived' : 'recent'" class="exp-history">
        <template v-for="section in sidebarSections" :key="section.label">
          <p class="exp-hist-group">{{ section.label }}</p>
          <div
            v-for="group in section.items"
            :key="group.key"
            class="exp-hist-item is-run"
            :class="{ 'is-active': group.live || group.key === selectedSessionKey }"
            role="button"
            tabindex="0"
            :title="group.title"
            @click="selectHistory(group)"
            @keydown.enter.self="selectHistory(group)"
          >
            <span class="exp-hist-ico"><Icon :name="bySlug.get(group.skill)?.categoryId ?? 'brand'" :size="14" /></span>
            <span class="exp-hist-copy">
              <span class="exp-hist-title">{{ group.title }}</span>
              <small>
                {{ skillNameOf(group.skill) }} ·
                {{ group.count > 1 ? `${group.count} 条消息` : fmtTime(group.latest.ts) }}
              </small>
            </span>
            <!-- 右列：徽章在上，操作按钮在右下角（运行中=运行徽章；常规=归档；已归档=恢复+删除；
                 实时占位条目无结局也无操作，落库后由真实分组接管） -->
            <span class="exp-hist-side">
              <span v-if="group.running" class="use-hist-outcome is-running">运行中</span>
              <span v-else-if="group.latest.question" class="use-hist-outcome is-pending">待回复</span>
              <span v-else-if="!group.live" class="use-hist-outcome" :class="`is-${group.latest.outcome}`">{{ OUTCOME_LABEL[group.latest.outcome] ?? group.latest.outcome }}</span>
              <button
                v-if="!group.archived && !group.live"
                type="button"
                class="exp-hist-inline"
                title="归档对话"
                aria-label="归档对话"
                @click.stop="archiveConversation(group, true)"
              ><Icon name="archive" :size="12" /></button>
              <span v-else-if="group.archived" class="exp-hist-side-acts">
                <button
                  type="button"
                  class="exp-hist-inline"
                  title="恢复到对话列表"
                  aria-label="恢复到对话列表"
                  @click.stop="archiveConversation(group, false)"
                ><Icon name="restore" :size="12" /></button>
                <button
                  type="button"
                  class="exp-hist-inline is-danger"
                  :class="{ 'is-confirm': confirmDeleteKey === group.key }"
                  :title="confirmDeleteKey === group.key ? '再次点击确认删除' : '删除对话'"
                  :aria-label="confirmDeleteKey === group.key ? '再次点击确认删除' : '删除对话'"
                  @click.stop="onDeleteClick(group)"
                >{{ confirmDeleteKey === group.key ? '确认' : '' }}<Icon name="trash" :size="12" /></button>
              </span>
            </span>
          </div>
        </template>
        <p v-if="historyLoading" class="exp-side-empty">正在加载对话…</p>
        <p v-else-if="showArchived ? !archivedLive : !historyLive" class="exp-side-empty">暂时无法读取对话，请稍后重试。</p>
        <p v-else-if="!sidebarSections.length" class="exp-side-empty">
          {{ showArchived ? '暂无已归档对话。归档后的对话会出现在这里。' : '暂无最近对话。新建对话后会出现在这里。' }}
        </p>
      </div>
      <div class="exp-history-views" role="group" aria-label="对话列表">
        <button type="button" aria-label="最近对话" title="最近对话" :aria-pressed="!showArchived" @click="showArchived = false">
          <Icon name="chat" :size="15" />
          <span class="exp-view-label">最近对话</span>
        </button>
        <button type="button" :aria-label="archivedLive ? `已归档（${archivedGroups.length} 段对话）` : '已归档'"
          title="已归档" :aria-pressed="showArchived" @click="showArchived = true">
          <Icon name="archive" :size="15" />
          <span class="exp-view-label">已归档 <span v-if="archivedLive" class="exp-view-count">{{ archivedGroups.length }}</span></span>
        </button>
      </div>
    </aside>

    <div class="wrap-exp" :class="{ 'is-empty': messages.length === 0 && !loadingConversation }">
      <div class="exp-shell">
        <div class="exp-top" :class="{ 'is-compact': messages.length > 0 || loadingConversation }">
          <h1 class="exp-title">智能体搭子 · 在线对话</h1>
          <p class="exp-sub">默认由通用智能体直接回答，输入 $ 可挂载专业技能</p>
        </div>

        <div v-if="loadingConversation" class="exp-history-loading">正在读取对话…</div>
        <div v-else-if="messages.length === 0 && !recoveryFailed" class="exp-examples">
          <span class="exp-examples-label">试试这些：</span>
          <button v-for="ex in EXAMPLES" :key="ex.slug" type="button" class="exp-example" @click="fill(ex.slug)">
            {{ ex.question }}
          </button>
        </div>

        <div v-if="!loadingConversation && messages.length > 0" class="exp-stream">
          <template v-for="(msg, mi) in messages" :key="msg.runId ?? mi">
            <div v-if="msg.role === 'user' && !(mi && replyText(mi - 1))" class="exp-msg-user">{{ msg.text }}</div>
            <div v-else-if="msg.role === 'ai'" class="exp-msg-ai">
              <span class="exp-ai-avatar" :style="msg.skill ? { background: `var(--cat-${msg.skill.categoryId}-soft)`, color: `var(--cat-${msg.skill.categoryId})` } : {}">
                <Icon :name="msg.skill ? msg.skill.categoryId : 'brand'" :size="16" />
              </span>
              <div class="exp-ai-main">
                <div class="exp-ai-head">
                  <span class="exp-ai-name">{{ msg.skill ? skillTitle(msg.skill.slug) : '通用智能体' }}</span>
                  <span class="exp-ai-badge" v-if="msg.skill" :style="{ background: `var(--cat-${msg.skill.categoryId}-soft)`, color: `var(--cat-${msg.skill.categoryId})` }">
                    {{ skillCat(msg.skill.slug) }}
                  </span>
                  <span v-if="!msg.done && runStatus" class="exp-run-status">{{ runStatus }} · {{ formatElapsed(elapsedMs) }}</span>
                  <span v-else-if="msg.done" class="exp-demo-tag" :class="{ 'is-real': msg.real }">{{ msg.real ? '真实运行' : '演示输出' }}</span>
                </div>
                <ToolCallGroup v-if="msg.real && (msg.execution?.length || msg.durationMs !== undefined || !msg.done)"
                  :steps="msg.execution ?? []" :duration-ms="msg.done ? msg.durationMs : elapsedMs" :running="!msg.done" />
                <ReportOutput v-if="msg.text || !msg.question" :text="msg.text" :charts="msg.charts" :has-resources="resourceCount(msg) > 0"
                  :html-mode="!msg.question && msg.skill?.slug === 'career-guidance'" :streaming="!msg.done" />
                <ChatQuestionCard v-if="msg.question" :request="msg.question" :run-id="msg.runId"
                  :pending="msg === pendingQuestion" :answer="replyText(mi)" :disabled="sending || loadingConversation || attachUploading"
                  @answer="answerQuestion(msg, $event)" />
                <button v-if="resourceCount(msg)" type="button" class="exp-resource-reference" aria-controls="conversation-resource-list" @click="resourcePanel?.reveal(mi)">
                  <Icon name="file" :size="13" />{{ resourceCount(msg) }} 项生成资源<span>查看资源<Icon name="chev" :size="12" /></span>
                </button>
                <p v-if="msg.done && !msg.real" class="exp-ai-note">当前为演示模式。连接运行服务后，重新提交任务即可获取实际结果。</p>
                <p v-else-if="msg.done && msg.modelName" class="exp-ai-note">由 {{ msg.modelName }} 生成</p>
              </div>
            </div>
          </template>
        </div>

        <div v-if="!loadingConversation && (resumable || recoveryFailed)" class="exp-resume">
          <span role="status">{{ recoveryFailed ? '尚未确认任务状态' : resumable?.resumeOf ? '任务已中断' : '任务尚未开始' }}</span>
          <button type="button" :disabled="sending" @click="recoveryFailed ? retryRecovery() : continueTask()">
            {{ recoveryFailed ? '重新读取' : '继续任务' }}<Icon name="chev" :size="13" />
          </button>
          <button v-if="recoveryFailed" type="button" :disabled="sending" @click="newChat">新建对话</button>
        </div>
        <div class="exp-input">
          <div class="exp-input-box">
            <div v-if="skillMenu" class="exp-skill-menu" role="listbox" aria-label="挂载 SKILL">
              <div
                v-for="(s, i) in skillMatches"
                :key="s.slug"
                class="exp-skill-item"
                :class="{ 'is-hot': i === skillHighlight }"
                role="option"
                :aria-selected="i === skillHighlight"
                @mousedown.prevent
                @click="pickSkill(s)"
              >
                <span class="exp-skill-ico" :style="{ background: `var(--cat-${s.categoryId}-soft)`, color: `var(--cat-${s.categoryId})` }">
                  <Icon :name="s.categoryId" :size="14" />
                </span>
                <span class="exp-skill-meta">
                  <b>{{ s.name }}</b>
                  <small>{{ s.summary }}</small>
                </span>
                <span class="exp-skill-slug">{{ s.slug }}</span>
              </div>
              <p v-if="skillMatches.length === 0" class="exp-skill-empty">没有匹配的 SKILL，试试其他关键词</p>
            </div>
            <div v-if="pendingAttachments.length || attachUploading" class="exp-attach-row">
              <span v-for="(a, i) in pendingAttachments" :key="a.path" class="exp-attach-chip">
                <Icon name="file" :size="13" />
                <span class="exp-attach-name">{{ a.name }}</span>
                <small>{{ formatSize(a.size) }}</small>
                <button type="button" class="exp-attach-x" :aria-label="`移除附件 ${a.name}`" @click="removeAttachment(i)">
                  <Icon name="x" :size="11" />
                </button>
              </span>
              <span v-if="attachUploading" class="exp-attach-chip is-busy">上传中…</span>
            </div>
            <textarea
              ref="textareaEl"
              v-model="textarea"
              class="exp-textarea"
              rows="2"
              placeholder="输入你的问题；输入 $ 挂载专业技能（如 $career-guidance）"
              @input="syncSkillMenu"
              @keydown="onTextareaKeydown"
            ></textarea>
            <div class="exp-input-bar">
              <button
                type="button"
                class="exp-skill-trigger"
                :class="{ 'is-on': skillMenu || activeSkill }"
                :title="activeSkill ? `已挂载 ${activeSkill.name}，点击更换` : '挂载 SKILL'"
                @click.stop="toggleSkillMenu"
              >$</button>
              <span v-if="activeSkill" class="exp-skill-chip" :style="{ background: `var(--cat-${activeSkill.categoryId}-soft)`, color: `var(--cat-${activeSkill.categoryId})` }">
                <Icon :name="activeSkill.categoryId" :size="13" />
                {{ activeSkill.name }}
                <button type="button" class="exp-skill-x" aria-label="取消挂载，回到通用智能体" @click="clearSkill">
                  <Icon name="x" :size="11" />
                </button>
              </span>
              <input
                ref="attachInputEl"
                type="file"
                class="exp-attach-input"
                multiple
                accept=".pdf,.docx,.doc,.md,.txt"
                @change="onAttachPicked"
              />
              <button
                type="button"
                class="exp-attach-btn"
                :title="apiReady ? '上传附件（PDF / DOCX / DOC / MD / TXT，单个 ≤ 6MB）' : '演示环境不支持附件'"
                :disabled="!apiReady || sending || attachUploading"
                @click="triggerAttach"
              >
                <Icon name="paperclip" :size="16" />
              </button>
              <div class="exp-agent">
                <ChatModelPicker v-if="models.length" v-model="selectedModel" :options="models" :disabled="sending || loadingConversation || models.length === 1" />
                <span v-else>{{ apiReady ? (apiModel || '在线 Agent') : '演示模式' }}</span>
                <button type="button" class="exp-send" :disabled="!textarea.trim() || sending || loadingConversation || attachUploading" aria-label="发送" @click="send()">
                  <Icon name="arrow-up" :size="16" />
                </button>
              </div>
            </div>
          </div>
          <p class="exp-input-note">内容由 AI 生成，请仔细核对。</p>
        </div>
      </div>
    </div>
    <ConversationResources v-if="resources.length && !loadingConversation" ref="resourcePanel" :items="resources" :conversation-key="currentConvId" />
  </section>
</template>
