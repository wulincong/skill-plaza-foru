/* ============================================================
   运行记录 · 演示数据（前端先行版）
   ------------------------------------------------------------
   结构与后端 traces/index.jsonl（列表）和 <runId>.json（详情）
   完全一致；详情取材自两次真实运行（产教报告成功交付 / 取证
   超时）。后端 /api/runs 就绪后删除本文件切换数据源即可。
   ============================================================ */

export type RunOutcome = 'success' | 'timeout' | 'aborted' | 'error' | 'historical'

export type ReportChart = {
  id: string
  type: 'bar' | 'stackedBar' | 'histogram' | 'line' | 'map'
  title: string
  data: Array<Record<string, unknown>>
  sourceIds: string[]
  unit?: string
  snapshotDate?: string
  region?: string
  caveat?: string
  altText?: string
  insight?: string
  xAxis?: { name?: string; unit?: string }
  yAxis?: { name?: string; unit?: string }
}

export interface RunListItem {
  requestId?: string
  userMessage?: string
  resumeSourceId?: string
  tokenUsage?: { provider?: string | null; model?: string | null }
  webLinks?: Array<{ name: string; url: string }>
  downloads?: Array<{ name: string; url: string }>
  runId: string
  ts: string
  skill: string
  /** 浏览器会话 id：同一会话的多条运行组成一个对话（旧记录缺省退化为单运行一组） */
  clientSessionId?: string
  taskTitle?: string
  promptDigest: string
  outcome: RunOutcome
  /** 执行引擎（历史记录缺省视为 zcode） */
  engine?: 'zcode' | 'pi'
  durationMs: number
  usage?: {
    inputTokens?: number
    outputTokens?: number
    cacheReadTokens?: number
    totalTokens?: number
    /** 本次运行花费（美元，pi 专属） */
    costUsd?: number
  }
  toolCallCount?: number
  /** Agent 与环境快照（历史记录缺省 → 详情页整块隐藏） */
  agentEnv?: {
    agentVersion?: string
    model?: string
    thinking?: string
    node?: string
    os?: string
  }
  /** MVP 直出模式的报告解析摘要（pi 运行才有） */
  report?: {
    structurePass?: boolean
    missingSections?: string[]
    stats?: {
      sections: number
      facts: number
      inferences: number
      recommendations: number
      gaps: number
      sources: number
      chars: number
    }
    /** report-meta 侧车校验摘要（来源/指标/结论分级） */
    meta?: {
      pass: boolean
      errors: string[]
      counts: {
        sources: number
        metrics: number
        facts: number
        inferences: number
        recommendations: number
        charts: number
      }
      gaps?: Array<Record<string, unknown>>
      risks?: Array<Record<string, unknown>>
      marketAnalysis?: { status?: string; queryId?: string; sampleSize?: number }
      resumeReview?: { strengths?: string[]; missingEvidence?: string[]; rewriteItems?: string[] }
      charts?: ReportChart[]
    }
  }
  /** 原始文件路径（真实数据才有；演示数据无） */
  files?: { events?: string; trace?: string; report?: string; html?: string; pdf?: string }
}

export interface RunToolPart {
  type: 'tool'
  tool: string
  callID: string
  state: { status: string; input?: unknown; output?: unknown }
}

export interface RunTextPart { type: 'text'; text: string }
export interface RunReasoningPart { type: 'reasoning'; text: string }

export type RunPart = RunToolPart | RunTextPart | RunReasoningPart

export interface RunDetail {
  session: {
    id: string
    title: string
    workspace: string
    created: string
    updated: string
  }
  outcome: RunOutcome
  usage?: RunListItem['usage']
  messages: Array<{ seq: number | null; time: string; role?: string; parts: RunPart[] }>
}

/* ---------- 列表（对应 index.jsonl） ---------- */

export const RUNS_MOCK: RunListItem[] = [
  {
    runId: 'backfill-sess_26d85b12',
    ts: '2026-09-17T02:41:12.000Z',
    skill: 'industry-education-report',
    promptDigest: '佛山新能源汽车专业建设产教报告（默认示例任务）',
    outcome: 'success',
    durationMs: 712_000,
    usage: { inputTokens: 486_210, outputTokens: 12_450, cacheReadTokens: 452_180, totalTokens: 498_660 },
    toolCallCount: 14,
    engine: 'zcode',
    agentEnv: { agentVersion: '0.16.9', model: 'glm-5.3 (GLM Coding Plan)', node: 'v24.20.0', os: 'darwin arm64' },
  },
  {
    runId: 'backfill-sess_c7c6bbb5',
    ts: '2026-09-17T02:21:05.000Z',
    skill: 'industry-education-report',
    promptDigest: '佛山新能源汽车专业建设产业教育报告（取证超时）',
    outcome: 'timeout',
    durationMs: 720_000,
    usage: { inputTokens: 389_420, outputTokens: 9_870, cacheReadTokens: 351_260, totalTokens: 399_290 },
    toolCallCount: 29,
  },
  {
    runId: '20260917-031739-fnyv',
    ts: '2026-09-17T07:17:39.696Z',
    skill: 'ai-interview',
    promptDigest: '只回复两个字：记录成功',
    outcome: 'success',
    durationMs: 5_764,
    usage: { inputTokens: 16_375, outputTokens: 13, cacheReadTokens: 0, totalTokens: 16_388, costUsd: 0.0011 },
    toolCallCount: 0,
    engine: 'pi',
    agentEnv: { agentVersion: '0.85.1', model: 'deepseek/deepseek-flash', thinking: 'low', node: 'v24.20.0', os: 'darwin arm64' },
  },
  {
    runId: '20260917-032109-yw0m',
    ts: '2026-09-17T07:21:09.000Z',
    skill: 'ai-interview',
    promptDigest: '写一段三百字的面试开场白，慢慢写',
    outcome: 'aborted',
    durationMs: 5_001,
    toolCallCount: 0,
  },
  {
    runId: '20260917-031759-3eo3',
    ts: '2026-09-17T07:17:59.000Z',
    skill: 'ai-interview',
    promptDigest: '写一段两百字的面试开场白',
    outcome: 'success',
    durationMs: 9_171,
    usage: { inputTokens: 32_876, outputTokens: 452, cacheReadTokens: 27_968, totalTokens: 33_328 },
    toolCallCount: 0,
  },
  {
    runId: 'backfill-sess_50470e92',
    ts: '2026-09-17T02:20:39.000Z',
    skill: 'industry-education-report',
    promptDigest: '检查 industry-education-report 技能是否存在',
    outcome: 'historical',
    durationMs: 7_000,
    toolCallCount: 0,
  },
  {
    runId: 'backfill-sess_725c13e9',
    ts: '2026-09-17T00:13:28.000Z',
    skill: 'training-data-qa',
    promptDigest: 'training-data-qa 数据构造与划分规划',
    outcome: 'historical',
    durationMs: 5_000,
    toolCallCount: 0,
  },
]

/* ---------- 详情 A：完整成功的产教报告（sess_26d85b12 取材，14 步节选） ---------- */

export const RUN_DETAIL_SUCCESS: RunDetail = {
  session: {
    id: 'sess_26d85b12-403d-4384-bd9b-582c4dd87961',
    title: '佛山新能源汽车专业建设产教报告',
    workspace: 'web/server/workspace/11c0f2aa/',
    created: '2026-09-17T02:41:12.000Z',
    updated: '2026-09-17T02:53:04.000Z',
  },
  outcome: 'success',
  usage: { inputTokens: 486_210, outputTokens: 12_450, cacheReadTokens: 452_180, totalTokens: 498_660 },
  messages: [
    {
      seq: 0,
      time: '2026-09-17T02:41:12.000Z',
      role: 'user',
      parts: [
        {
          type: 'text',
          text: '请先用 Skill 工具加载 industry-education-report 技能，然后严格按该技能的方法与输出契约执行以下任务：\n\n使用 $industry-education-report 完成以下任务：\n- 服务对象：院校管理者\n- 目标地区：广东省佛山市\n- 报告基期：2024 年\n- 报告用途：专业建设与调整\n- 重点专题：区域产业链、岗位人才需求、专业与课程、就业去向\n- 已有材料或特别要求：为某高职院校论证新能源汽车专业建设方向，结论需要区分事实、推断和建议。\n\n请先复述任务边界与缺失信息，再按该 SKILL 的方法推进。',
        },
      ],
    },
    {
      seq: 1,
      time: '2026-09-17T02:41:16.000Z',
      role: 'assistant',
      parts: [
        {
          type: 'tool',
          tool: 'Skill',
          callID: 'call_skill_01',
          state: {
            status: 'completed',
            input: { skill: 'industry-education-report', args: '服务对象：院校管理者；地区：广东省佛山市；基期：2024；用途：专业建设与调整；…' },
            output: '<skill_content name="industry-education-report"># 产教决策报告\n\n输出可审查的决策材料：报告 Markdown、结构化 report.json、证据与口径附录、验收结果…',
          },
        },
        {
          type: 'text',
          text: '技能已加载。先复述任务边界与缺失信息，然后读取技能的参考资料与脚本再推进。\n\n**任务边界复述**\n- 受众：院校管理者（college 院校版模板，9 章 C01–C09）\n- 区域：广东省佛山市；基期：2024 年（历史基期）\n- 决策事项：为某高职院校论证新能源汽车专业建设方向\n- 结论须区分：事实 / 推断 / 建议 / 缺数\n\n**缺失信息（按技能规则登记为缺口，不编造）**\n- 佛山市级新能源汽车产量（公报未发布该口径）\n- 佛山本地去重岗位需求台账、目标院校招生就业微观台账\n- 佛山现行专项扶持政策（原 2023 年办法已于 2025 年 10 月废止）',
        },
      ],
    },
    {
      seq: 2,
      time: '2026-09-17T02:41:22.000Z',
      role: 'assistant',
      parts: [
        { type: 'tool', tool: 'Read', callID: 'call_read_01', state: { status: 'completed', input: { file_path: '.zcode/skills/industry-education-report/references/data-contract.md' }, output: '# 数据、引用与文件契约\n\nreport.json 顶层字段：title、audience（college/government）、region、chain、period…sources：id、title、publisher、url、locator…' } },
        { type: 'tool', tool: 'Read', callID: 'call_read_02', state: { status: 'completed', input: { file_path: '.zcode/skills/industry-education-report/references/foshan-evidence.md' }, output: '# 佛山预核验证据包\n\nFS-01 佛山市 2024 年国民经济和社会发展统计公报（GDP 13361.90 亿元，+1.3%）…' } },
        { type: 'tool', tool: 'Read', callID: 'call_read_03', state: { status: 'completed', input: { file_path: '.zcode/skills/industry-education-report/assets/templates.json' }, output: '{ "college": { "chapters": ["C01 摘要", "C02 区域产业与新能源汽车链", "C03 岗位人才需求", "C04 重点企业", "C05 专业与课程对照", "C06 就业去向", "C07 培养方案建议", "C08 风险与缺口", "C09 决策建议"] } }' } },
        { type: 'reasoning', text: '佛山/广东证据包已预核验（FS-xx/GD-xx），按技能规定：默认场景不发起联网检索，直接使用证据包并保留缺口登记。先建 report.json，再跑校验脚本，最后渲染并逐条语义审核。' },
      ],
    },
    {
      seq: 3,
      time: '2026-09-17T02:47:35.000Z',
      role: 'assistant',
      parts: [
        {
          type: 'tool',
          tool: 'Write',
          callID: 'call_write_01',
          state: {
            status: 'completed',
            input: { file_path: 'foshan-nev-college/report.json', content: '{\n  "title": "佛山市新能源汽车产业链产教决策报告（院校版·专业建设论证）",\n  "audience": "college",\n  "region": "广东省佛山市",\n  "chain": "新能源汽车",\n  "period": "2024年产业基期",\n  "sources": [9 项], "metrics": [9 项], "claims": [10 条], "gaps": [4 项]\n}' },
            output: '已写入 foshan-nev-college/report.json（9122 字符）',
          },
        },
        {
          type: 'tool',
          tool: 'Bash',
          callID: 'call_bash_01',
          state: {
            status: 'completed',
            input: { command: 'python3 .zcode/skills/industry-education-report/scripts/report.py validate foshan-nev-college/report.json', description: '校验报告结构' },
            output: 'validation: PASS\n  chapters: 9/9 (C01–C09)\n  claims: 10（事实 5 / 推断 2 / 建议 3），均有 source 关联\n  gaps: 4，全部含缺失原因与补齐路径\n  指标口径检查：派生指标输入一致，无混算',
          },
        },
        {
          type: 'tool',
          tool: 'Bash',
          callID: 'call_bash_02',
          state: {
            status: 'completed',
            input: { command: 'python3 .zcode/skills/industry-education-report/scripts/report.py render foshan-nev-college/report.json -o foshan-nev-college/report.md', description: '渲染报告正文' },
            output: 'rendered: foshan-nev-college/report.md（42 KB，含 2 张口径对照表）',
          },
        },
      ],
    },
    {
      seq: 4,
      time: '2026-09-17T02:52:40.000Z',
      role: 'assistant',
      parts: [
        {
          type: 'tool',
          tool: 'Write',
          callID: 'call_write_02',
          state: {
            status: 'completed',
            input: { file_path: 'foshan-nev-college/review.md', content: '# 语义审核（逐条）\n\n- 事实 5 条：数值均来自 FS/GD 证据包，口径一致 ✔\n- 推断 2 条：推断链已标注依据与不确定性 ✔\n- 建议 3 条：含拟议目标与前提条件 ✔…' },
            output: '已写入 foshan-nev-college/review.md',
          },
        },
        {
          type: 'text',
          text: '报告已生成并通过技能全部自动检查与语义审核。\n\n## 交付文件（位于当前工作目录）\n- `report.json` — 结构化报告：9 来源、9 指标、10 条结论（事实 5 / 推断 2 / 建议 3）、4 项缺口、2 张口径对照表\n- `report.md` — 渲染正文；`validation.json` — 结构校验通过；`review.md` — 逐条语义审核（全部 pass）\n\n## 核心结论（按事实/推断/建议分层）\n- **事实**：佛山 2024 年 GDP 13361.90 亿元（+1.3%，可比价），规上工业增加值 -1.9%，但工业技改投资 +6.1%；广东 2024 新能源汽车产量 361.78 万辆（+43%）\n- **推断**：佛山新能源汽车检测与维修类岗位需求随省内产量扩张上升，但市级岗位台账缺失，规模待核验\n- **建议**：分两步建设——先以「智能网联汽车检测与维修」方向改造现有汽车专业课程（缺口：车载总线诊断、电池管理系统），一年后依据招生与就业数据再决定是否单设专业',
        },
      ],
    },
  ],
}

/* ---------- 详情 B：取证超时的运行（sess_c7c6bbb5 取材，29 步节选为 10 步） ---------- */

export const RUN_DETAIL_TIMEOUT: RunDetail = {
  session: {
    id: 'sess_c7c6bbb5-0208-4ccf-aee7-b145e2f256d9',
    title: '佛山新能源汽车专业建设产业教育报告',
    workspace: 'web/server/workspace/77063e46/',
    created: '2026-09-17T02:21:05.000Z',
    updated: '2026-09-17T02:32:57.000Z',
  },
  outcome: 'timeout',
  usage: { inputTokens: 389_420, outputTokens: 9_870, cacheReadTokens: 351_260, totalTokens: 399_290 },
  messages: [
    {
      seq: 0,
      time: '2026-09-17T02:21:05.000Z',
      role: 'user',
      parts: [
        {
          type: 'text',
          text: '请先用 Skill 工具加载 industry-education-report 技能，然后严格按该技能的方法与输出契约执行以下任务：\n\n使用 $industry-education-report 完成以下任务：\n- 服务对象：院校管理者；目标地区：广东省佛山市；报告基期：2024 年\n- 重点专题：区域产业链、岗位人才需求、专业与课程、就业去向\n\n请先复述任务边界与缺失信息，再按该 SKILL 的方法推进。',
        },
      ],
    },
    {
      seq: 1,
      time: '2026-09-17T02:21:08.000Z',
      role: 'assistant',
      parts: [
        {
          type: 'tool',
          tool: 'Skill',
          callID: 'call_skill_01',
          state: {
            status: 'completed',
            input: { skill: 'industry-education-report', args: '服务对象：院校管理者；地区：广东省佛山市；基期：2024…' },
            output: '<skill_content name="industry-education-report"># 产教决策报告\n\n输出可审查的决策材料：报告 Markdown、结构化 report.json…',
          },
        },
        {
          type: 'tool',
          tool: 'Read',
          callID: 'call_read_01',
          state: { status: 'completed', input: { file_path: '.zcode/skills/industry-education-report/references/data-contract.md' }, output: '# 数据、引用与文件契约\n\nsources：id、title、publisher、url、locator…搜索摘要不能作为已核验证据…' } },
        {
          type: 'tool',
          tool: 'Read',
          callID: 'call_read_02',
          state: { status: 'completed', input: { file_path: '.zcode/skills/industry-education-report/references/guangdong-evidence.md' }, output: '# 广东预核验证据包\n\nGD-01 广东省 2024 年统计公报：新能源汽车产量 361.78 万辆，同比 +43%…' } },
        {
          type: 'text',
          text: '技能已加载。模板与契约已明确：院校版 C01–C09 九章。现在按取数规则检索佛山市 2024 年可核验的官方数据（统计公报、产业政策、专业标准）。',
        },
      ],
    },
    {
      seq: 2,
      time: '2026-09-17T02:21:29.000Z',
      role: 'assistant',
      parts: [
        { type: 'reasoning', text: 'Search summaries cannot be used as verified evidence — must open original sources. Fetch the Foshan statistical公报 page to verify NEV output figures.' },
        {
          type: 'tool',
          tool: 'WebSearch',
          callID: 'call_ws_01',
          state: {
            status: 'completed',
            input: { query: '2024年佛山市国民经济和社会发展统计公报 汽车 新能源 产量' },
            output: '主要结果：红黑统计公报库（tjgb.hongheiku.com/djs/63215.html）、佛山市人民政府门户网站…',
          },
        },
        {
          type: 'tool',
          tool: 'WebFetch',
          callID: 'call_wf_01',
          state: {
            status: 'error',
            input: { url: 'https://tjgb.hongheiku.com/djs/63215.html', prompt: '请找出汽车产量、新能源汽车产量数值及同比增速…' },
            output: 'Permission request failed（环境拦截）',
          },
        },
        {
          type: 'tool',
          tool: 'WebSearch',
          callID: 'call_ws_02',
          state: {
            status: 'completed',
            input: { query: 'site:foshan.gov.cn 2024年佛山市国民经济和社会发展统计公报' },
            output: '在 foshan.gov.cn 站内未直接找到 2024 版直达页；找到佛山统计局公报目录（2022–2025 列表）…',
          },
        },
        {
          type: 'tool',
          tool: 'WebSearch',
          callID: 'call_ws_03',
          state: {
            status: 'completed',
            input: { query: '佛山 新能源汽车 产业 政策 2024 行动计划 通知' },
            output: '重要发现：佛山市人民政府办公室关于废止促进佛山新能源汽车产业园发展扶持办法的通知（foshan.gov.cn，官方全文）…',
          },
        },
        {
          type: 'text',
          text: '搜索摘要不能作为已核验证据，我来打开原始公报核对新能源汽车产量数据。第三方库只嵌了阅读器没有正文；WebFetch 与 curl 均被环境拦截，只能走 webReader。红黑库是懒加载阅读器，换镜像站找 2024 佛山公报全文。',
        },
      ],
    },
    {
      seq: 3,
      time: '2026-09-17T02:28:14.000Z',
      role: 'assistant',
      parts: [
        {
          type: 'tool',
          tool: 'WebSearch',
          callID: 'call_ws_04',
          state: {
            status: 'completed',
            input: { query: '佛山 2024年统计公报 规模以上工业 "汽车" 产量 同比' },
            output: '佛山 2025 公报（foshanplus 全文）：GDP 13157.35 亿元，+0.2%…2024 版全文仍未获取。',
          },
        },
        { type: 'reasoning', text: 'I cannot extract the Foshan 2024公报 car output values from any accessible mirror. Per the skill contract, search summaries cannot serve as verified evidence for specific numbers. Register市级量化数据 as gaps — do not fabricate. Use verified sources: 废止通知原文、广东公报（技能证据包）、佛山 2025 公报（口径参考）。\n\n→ 政策事实已核验：佛府办〔2025〕11号废止〔2023〕15号产业园扶持办法，2025-10-15 生效。' },
        {
          type: 'text',
          text: '佛山市级公报的镜像均为内嵌 PDF 无法抽取。按技能规则将市级量化数据登记为缺口，不编造；已核验来源：佛山产业园扶持办法废止通知（官方全文）、广东 2024 统计公报（技能证据包）、佛山 2025 公报（fsonline 全文，仅作口径参考）。现在生成结构化报告并跑验收。',
        },
      ],
    },
    {
      seq: 4,
      time: '2026-09-17T02:31:35.000Z',
      role: 'assistant',
      parts: [
        {
          type: 'tool',
          tool: 'Write',
          callID: 'call_write_01',
          state: {
            status: 'error',
            input: { file_path: 'foshan-nev-college/report.json', content: '{\n  "title": "佛山市新能源汽车产业链产教决策报告（院校版·专业建设论证）",\n  "audience": "college",\n  "period": "2024年产业基期",\n  …9122 字符…\n}' },
            output: 'Permission request failed（build 模式下无头会话无人批准写操作）',
          },
        },
        { type: 'reasoning', text: 'Write denied? Maybe sandbox permission. Try Bash mkdir+write? pwd 能过说明只读命令可以。再试 Write 到当前目录直接 report.json。' },
        {
          type: 'tool',
          tool: 'Bash',
          callID: 'call_bash_01',
          state: { status: 'error', input: { command: 'mkdir -p foshan-nev-college && echo ok', description: 'Create output directory' }, output: 'Permission request failed' } },
        {
          type: 'text',
          text: '（运行至 10 分钟超时上限，被服务端守卫停止。本次运行的完整复盘见：权限修复记录——后续会话已改用 yolo 模式并在 14 次工具调用内完整交付报告。）',
        },
      ],
    },
  ],
}

export const RUN_DETAILS_MOCK: Record<string, RunDetail> = {
  'backfill-sess_26d85b12': RUN_DETAIL_SUCCESS,
  'backfill-sess_c7c6bbb5': RUN_DETAIL_TIMEOUT,
}

export const OUTCOME_LABEL: Record<RunOutcome, string> = {
  success: '成功',
  timeout: '超时',
  aborted: '中断',
  error: '错误',
  historical: '历史',
}
