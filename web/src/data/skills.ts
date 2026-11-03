/* ============================================================
   智能体广场 · 数据
   ------------------------------------------------------------
   只放事实字段。不填推测的日期、版本、评分或下载量。
   outputs / dependencies / limitations 均按条目列出，
   便于在界面里逐条核对，而不是藏在句子里。
   ============================================================ */

export interface Category {
  id: string
  name: string
}

export interface Audience {
  id: string
  name: string
}

export interface Skill {
  slug: string
  name: string
  identifier: string
  categoryId: string
  audiences: string[]
  summary: string
  introduction?: string
  tags: string[]
  preconditions: string
  outputs: string[]
  dependencies: string[]
  limitations: string[]
  minimalInput: string
}

export interface Feature {
  id: string
  catId: string
  title: string
  description: string
  tags: string[]
  slug: string
}

/* 业务分类：id 同时用作语义色名（见 tokens.css 的 --cat-*） */
export const CATEGORIES: Category[] = [
  { id: 'industry', name: '产业与专业建设' },
  { id: 'teaching', name: '课程与教学开发' },
  { id: 'career', name: '实训与就业' },
  { id: 'data', name: '数据治理与模型底座' },
]

/* 适用角色 */
export const AUDIENCES: Audience[] = [
  { id: 'manager', name: '院校管理者' },
  { id: 'teacher', name: '教师' },
  { id: 'student', name: '学生' },
  { id: 'data', name: '数据团队' },
]

export const SKILLS: Skill[] = [
  {
    slug: 'industry-education-report',
    name: '产教决策报告',
    identifier: 'industry-education-report',
    categoryId: 'industry',
    audiences: ['manager', 'data'],
    summary: '面向院校、政府和园区生成有证据、可审查的产业与专业建设决策报告。',
    tags: ['产教融合', '专业建设', '决策报告'],
    preconditions: '产业 / 岗位 / 专业或就业资料',
    outputs: [
      '报告 Markdown',
      '结构化 report.json',
      '证据与口径附录',
      '结构与语义验收结果',
    ],
    dependencies: [
      '目标地区、产业范围与报告用途',
    ],
    limitations: [
      '最新报告需要重新核验来源、年份、范围和统计口径。',
      '缺少院校微观数据时会保留缺口，不编造就业率、岗位缺口或招生规模。',
    ],
    minimalInput:
      '使用 $industry-education-report，为广东省某高职院校制作新能源汽车专业建设报告，受众为院校管理者，基期为 2024 年。',
  },
  {
    slug: 'tech-forecast',
    name: '新岗位·新技术预判',
    identifier: 'tech-forecast',
    categoryId: 'industry',
    audiences: ['manager', 'teacher', 'data'],
    summary: '面向院校与培训机构的新兴技术成熟度、技能演进与新兴岗位预判，输出证据分级的 HTML 决策报告。',
    tags: ['技术预判', '新兴岗位', '培训方向'],
    preconditions: '目标地区 + 技术领域方向',
    outputs: [
      '技术成熟度雷达图报告（HTML）',
      '技能演进桑基图',
      '新兴岗位与新兴技能预测表',
      '培训方向建议表',
    ],
    dependencies: [
      '目标地区、技术领域与预判时间范围',
    ],
    limitations: [
      '预测字段区分证据等级（库内实测 / 内置文档 / 分析推断），分析推断不作为事实呈现。',
      '无真实月度趋势数据时，需求与增长趋势标注为推断或未评估。',
    ],
    minimalInput:
      '使用 $tech-forecast，面向广东省高职院校，预判未来 1–3 年人工智能与机器人方向的新兴岗位与培训建议。',
  },
  {
    slug: 'doc-translate',
    name: '文档翻译',
    identifier: 'doc-translate',
    categoryId: 'teaching',
    audiences: ['teacher', 'manager', 'student'],
    summary: '把 PDF 全文翻译为目标语言，保留原图并翻译图注，重排为对齐原文纸张、分栏和章节层级的译文 PDF。',
    tags: ['文档翻译', 'PDF 重排', 'XeLaTeX'],
    preconditions: 'PDF 文档（文本层可提取）+ 目标语言',
    outputs: [
      '与原文章节结构对齐的译文 PDF',
      '全文术语一致的章节级翻译',
      '保留原图、翻译图注并插回对应章节',
      '简短完成说明（页数与结构对齐情况）',
    ],
    dependencies: [
      '含可提取文本的 PDF 原件',
      '译文的目标语言',
    ],
    limitations: [
      '只对齐宏观结构（纸张、单双栏、标题层级），不逐像素复刻原版式。',
      '扫描件（无文本层）与加密 PDF 不支持，运行时如实告知。',
      '图内文字保持原样；图片位置随译文重排，上传单文件上限 6MB。',
    ],
    minimalInput:
      '使用 $doc-translate，上传一份 PDF 文档并翻译为中文（示例：上传英文课件 PDF，要求全文翻译成中文）。',
  },
  {
    slug: 'classroom-assistant',
    name: '课堂助教',
    identifier: 'classroom-assistant',
    categoryId: 'teaching',
    audiences: ['teacher', 'student'],
    summary: '在授权课程资料范围内完成带引用答疑、要点总结、练习生成和答疑记录整理。',
    tags: ['课程资料', '课堂练习', '引用答疑'],
    preconditions: '本次明确授权的课程材料',
    outputs: [
      '带定位引用的答疑记录',
      '课堂要点总结',
      '练习题与参考答案',
      '答疑过程清单',
    ],
    dependencies: [
      '教师明确授权并提供的课程资料',
      '需要引用时给出资料中的出处位置',
    ],
    limitations: [
      '只回答授权资料覆盖范围内的问题，范围外会明确说明。',
      '练习题在教师确认前只作为草稿，不直接计分。',
    ],
    minimalInput:
      '使用 $classroom-assistant，基于我上传的《新能源汽车概论》第 3 章资料，生成 5 道课堂练习并附答案要点。',
  },
  {
    slug: 'ai-interview',
    name: 'AI 面试练习',
    identifier: 'ai-interview',
    categoryId: 'career',
    audiences: ['teacher', 'student'],
    summary: '结合目标岗位、岗位要求和简历开展逐题模拟面试、智能追问与证据化复盘。',
    tags: ['模拟面试', '就业辅导', '回答复盘'],
    preconditions: '目标岗位 + 简历或经历摘要',
    outputs: [
      '逐题问答记录（含追问链）',
      '能力维度复盘报告',
      '原话引用与待验证项清单',
      '下一轮练习建议',
    ],
    dependencies: [
      '目标岗位的职责与要求描述',
      '本人简历或经历摘要',
    ],
    limitations: [
      '复盘只基于本人提供的信息，不联网核查任职资格。',
      '不承诺面试结果，只给出证据化的改进建议。',
    ],
    minimalInput:
      '使用 $ai-interview，目标岗位为某新能源汽车企业售后技术支持，按我上传的简历逐题模拟并复盘。',
  },
  {
    slug: 'career-guidance',
    name: '就业指导',
    identifier: 'career-guidance',
    categoryId: 'career',
    audiences: ['student'],
    summary: '基于目标、经历、岗位要求和现实约束，制定可执行的职业定位与求职行动方案。',
    introduction: '就业指导是面向学生求职决策的结构化职业规划 SKILL。它综合目标岗位、个人经历、简历、岗位描述以及地区和求职阶段等现实约束，帮助梳理职业定位、岗位匹配证据、能力缺口与求职优先级，并形成简历优化建议和分阶段行动计划。它不承诺录用结果，结论应以用户提供的事实和可核验的岗位信息为依据。',
    tags: ['职业定位', '岗位匹配', '求职计划'],
    preconditions: '目标岗位或方向 + 简历、经历摘要',
    outputs: [
      '职业定位或岗位匹配证据表',
      '简历与求职材料改进建议',
      '按周拆分的求职行动计划',
      'offer 比较矩阵与核实问题',
    ],
    dependencies: [
      '目标岗位或职业方向',
      '简历、经历摘要或其他可核验材料',
    ],
    limitations: [
      '建议基于用户提供的事实和岗位信息，不承诺录用结果。',
      '最新招聘状态、薪资行情和劳动法规需要按时间、地区和来源重新核实。',
    ],
    minimalInput:
      '使用 $career-guidance，目标是 Java 后端实习，请根据我的匿名简历和岗位描述列出匹配证据、关键缺口和 30 天行动计划。',
  },
  {
    slug: 'training-data-qa',
    name: '训练样本构造与标注质检',
    identifier: 'training-data-qa',
    categoryId: 'data',
    audiences: ['data'],
    summary: '从治理数据构造可追溯训练样本，检查重复、泄漏、分布和业务规则并编排专家抽检。',
    tags: ['数据治理', '标注质检', '训练数据'],
    preconditions: '治理数据、任务模板和标注规则',
    outputs: [
      '训练样本数据集（带来源标注）',
      '质检报告（重复、泄漏、分布、规则）',
      '专家抽检任务包',
      '数据集版本说明',
    ],
    dependencies: [
      '已完成治理的数据表或数据文件',
      '明确的任务模板和标注规则',
    ],
    limitations: [
      '数据授权范围由使用方确认，页面与 SKILL 不代替授权判断。',
      '统计结论基于所给数据计算，不外推到未提供的数据源。',
    ],
    minimalInput:
      '使用 $training-data-qa，对我提供的就业意向调查数据构造训练样本，标注字段以附带规则文件为准。',
  },
  {
    slug: 'wechat-report',
    name: '微信公众号报告',
    identifier: 'wechat-report',
    categoryId: 'industry',
    audiences: ['manager', 'teacher', 'data'],
    summary: '把地区与行业的岗位数据整理为已质检的公众号报告图片和纯图片分享页。',
    tags: ['公众号图文', '人才需求', '产业报告'],
    preconditions: '地区、行业、目标读者与可用数据',
    outputs: ['报告分屏图片', '纯图片分享网页与图片下载包'],
    dependencies: ['目标地区与行业', '报告读者及希望回答的问题'],
    limitations: ['未配置数据库时仅可使用明确标注的离线示例。', '直接生成图片成品供审核；存草稿需要明确要求，不自动群发或发布。'],
    minimalInput: '使用 $wechat-report，为广东省人工智能产业生成一份人才需求报告，读者是院校管理者；直接交付报告图片。',
  },
]

/* 智能体矩阵（T01–T24 规划清单）已移除：广场卡片改为跟随后端可运行技能清单
   动态渲染（SkillsPage 拉 /api/skills，本数组做文案 enriched 与后端不可达时的回落），
   未上线的规划项不再展示。历史数据见 git（9ab876f 之前版本）。 */

/* 效果预览：左侧业务列表 + 右侧产物示意 */
export const FEATURES: Feature[] = [  {
    id: 'industry',
    catId: 'industry',
    title: '规划产业与专业',
    description: '让产业、岗位和专业建议回到证据与口径。',
    tags: ['产业分析', '专业建设', '证据报告'],
    slug: 'industry-education-report',
  },
  {
    id: 'teaching',
    catId: 'teaching',
    title: '开发课程与教学',
    description: '在授权课程资料内生成答疑、要点和练习。',
    tags: ['授权资料', '定位引用', '课堂练习'],
    slug: 'classroom-assistant',
  },
  {
    id: 'interview',
    catId: 'career',
    title: '组织实训与就业',
    description: '围绕目标岗位和简历完成面试练习闭环。',
    tags: ['能力地图', '逐题追问', '回答复盘'],
    slug: 'ai-interview',
  },
  {
    id: 'data',
    catId: 'data',
    title: '治理训练数据',
    description: '把样本构造、机器质检和专家抽检连成流程。',
    tags: ['数据集划分', '泄漏检查', '专家抽检'],
    slug: 'training-data-qa',
  },
]

export const bySlug = new Map(SKILLS.map(s => [s.slug, s] as const))

/** 在线对话默认通用智能体：后端 skill 字段值与运行记录显示名（不进 SKILLS 卡片清单） */
export const GENERAL_SKILL_ID = 'general'
export const GENERAL_SKILL_NAME = '通用智能体'

export function catOf(id: string): Category {
  return CATEGORIES.find(c => c.id === id) ?? { id: 'industry', name: id }
}

export function audOf(id: string): Audience {
  return AUDIENCES.find(a => a.id === id) ?? { id, name: id }
}
