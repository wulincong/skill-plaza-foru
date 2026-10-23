/* ============================================================
   「在线运行」工作台 · 任务配置
   ------------------------------------------------------------
   每个 SKILL 一份结构化任务表单：分节 + 字段（单选/多选/下拉/输入/文本域）
   + 填表示例 + 可选知识库（当前为 Mock，仅演示前端状态）。
   字段只描述"要让 SKILL 知道什么"，不在前端推断模型行为。
   ============================================================ */

export type FieldType = 'choice' | 'multi' | 'select' | 'text' | 'textarea'

export interface TaskField {
  id: string
  label: string
  type: FieldType
  required?: boolean
  span?: 'full'
  placeholder?: string
  help?: string
  options?: string[]
}

export interface TaskSection {
  number: string
  title: string
  description: string
  fields: TaskField[]
}

export interface KnowledgeItem {
  id: string
  title: string
  meta: string
  tag: string
  default?: boolean
}

/** 附件上传位：声明后工作台/对话输入栏出现上传入口（后端 /api/upload） */
export interface UploadField {
  id: string
  label: string
  accept: string
  help?: string
  /** 内置演示附件（demoFiles.ts 的 key）：后端就绪后自动上传，可移除 */
  demoFile?: string
}

export interface UseTaskConfig {
  slug: string
  eyebrow: string
  lead: string
  output: string
  sections: TaskSection[]
  example: Record<string, string | string[]>
  /** 进入页面时自动带入 example 作为默认值（方便直接运行测试） */
  autoFillExample?: boolean
  knowledge: KnowledgeItem[]
  /** 附件上传位；requiredUpload 声明运行前必须上传的文件类型。 */
  uploads?: UploadField[]
  requiredUpload?: { accept: string; label: string }
}

export const USE_TASK_CONFIGS: UseTaskConfig[] = [
  {
    slug: 'doc-translate',
    eyebrow: '文档翻译工作台',
    lead: '上传 PDF 并指定目标语言，翻译后可查看和下载译文 PDF。',
    output: '保留原文纸张、分栏和标题层级的译文 PDF',
    sections: [
      {
        number: '01',
        title: '设置翻译要求',
        description: '支持带文本层的 PDF；扫描件与加密文档暂不支持。',
        fields: [
          { id: 'targetLanguage', label: '目标语言', type: 'text', required: true, placeholder: '例如：简体中文、英语、日语' },
          { id: 'scope', label: '翻译范围', type: 'text', placeholder: '留空翻译全文；也可填写第 2–5 页' },
          { id: 'terms', label: '术语与补充要求', type: 'textarea', span: 'full', placeholder: '例如：保留产品名称和代码；指定专业术语译法' },
        ],
      },
    ],
    example: { targetLanguage: '简体中文', scope: '全文', terms: '' },
    uploads: [{ id: 'sourcePdf', label: '上传原文 PDF（必填）', accept: '.pdf', help: '单个文件 ≤6MB；保留原图并翻译图注，图内文字保持原样。' }],
    requiredUpload: { accept: '.pdf', label: '原文 PDF' },
    knowledge: [],
  },
  {
    slug: 'industry-education-report',
    eyebrow: '产业研究工作台',
    lead: '填写报告对象与研究边界，组合所需专题，再从右侧选择可参考的知识库。',
    output: '产业与专业建设决策报告',
    sections: [
      {
        number: '01',
        title: '确定报告边界',
        description: '先明确服务对象、研究地区与时间口径。',
        fields: [
          { id: 'audience', label: '服务对象', type: 'choice', required: true, options: ['院校管理者', '政府部门', '产业园区'] },
          { id: 'region', label: '目标地区', type: 'text', required: true, placeholder: '例如：广东省（当前数据快照为省级切片）' },
          { id: 'baseline', label: '报告基期', type: 'select', required: true, options: ['2026 年', '2025 年', '2024 年', '2023 年'] },
          { id: 'purpose', label: '报告用途', type: 'select', required: true, options: ['专业建设与调整', '区域产教融合规划', '产业招商与人才研判', '项目申报与评审'] },
        ],
      },
      {
        number: '02',
        title: '选择研究专题',
        description: '可多选；SKILL 会按选择组织报告章节与证据清单。',
        fields: [
          { id: 'topics', label: '重点专题', type: 'multi', required: true, span: 'full', options: ['区域产业链', '岗位人才需求', '重点企业', '专业与课程', '就业去向', '招商建议'] },
          { id: 'context', label: '已有材料或特别要求', type: 'textarea', span: 'full', placeholder: '例如：希望聚焦人工智能产业的岗位结构与薪酬分化，并对应本地产业布局……', help: '可以先写资料名称，后续再补充附件。' },
        ],
      },
    ],
    example: {
      audience: '政府部门',
      region: '广东省',
      baseline: '2026 年',
      purpose: '产业招商与人才研判',
      topics: ['区域产业链', '岗位人才需求'],
      context:
        '基于技能内置的广东在招岗位数据快照（2026-06~07 导入批次，人工智能 AI 切片 v1）生成《广东省人工智能产业人才需求观察报告》；快照未覆盖的统计逐项登记缺口，不得外推或编造；结论区分事实、推断和建议。',
    },
    autoFillExample: true,
    knowledge: [
      { id: 'industry-policy', title: '区域产业政策资料库', meta: '政策与规划 · 38 份', tag: '政策', default: true },
      { id: 'job-market', title: '重点产业岗位需求库', meta: '招聘与岗位画像 · 12,680 条', tag: '岗位', default: true },
      { id: 'major-course', title: '院校专业与课程库', meta: '专业目录与课程样本 · 216 份', tag: '院校' },
      { id: 'employment-flow', title: '毕业生就业去向库', meta: '匿名统计样例 · 8 个数据集', tag: '就业' },
    ],
  },
  {
    slug: 'tech-forecast',
    eyebrow: '技术预判工作台',
    lead: '说明地区、技术方向与预判窗口，SKILL 会结合岗位库佐证与内置证据快照，生成证据分级的前瞻报告。',
    output: '新兴技术成熟度与培训方向 HTML 报告',
    sections: [
      {
        number: '01',
        title: '确定预判范围',
        description: '地区用于岗位库查询口径；技术方向决定报告的快照与图表范围。',
        fields: [
          { id: 'region', label: '目标地区', type: 'text', required: true, placeholder: '例如：广东省（用于岗位库查询与报告口径）' },
          { id: 'domains', label: '技术领域方向', type: 'multi', required: true, span: 'full', options: ['人工智能与大模型应用', '具身智能与机器人', '低空经济（无人机）', '新能源汽车与储能', '集成电路', '数据要素与数据治理'] },
          { id: 'horizon', label: '预判窗口', type: 'select', required: true, options: ['未来 1–3 年', '未来 3–5 年'] },
          { id: 'institution', label: '院校类型', type: 'choice', required: true, options: ['高职院校', '应用型本科', '中职学校', '社会培训机构'] },
        ],
      },
      {
        number: '02',
        title: '聚焦专业与输出重点',
        description: '专业群用于匹配建议；约束越具体，培训方向越可落地。',
        fields: [
          { id: 'majors', label: '关注专业群', type: 'text', placeholder: '例如：软件技术、工业机器人技术（可留空）' },
          { id: 'context', label: '已有材料或特别要求', type: 'textarea', span: 'full', placeholder: '例如：用于新专业申报与培训立项，希望聚焦智能制造方向，并区分库内实测与推断结论……' },
        ],
      },
    ],
    example: {
      region: '广东省',
      domains: ['人工智能与大模型应用', '具身智能与机器人'],
      horizon: '未来 1–3 年',
      institution: '高职院校',
      majors: '软件技术、工业机器人技术',
      context: '用于新专业申报与培训项目立项，需要雷达图与桑基图，并区分库内实测与推断结论。',
    },
    autoFillExample: true,
    uploads: [
      {
        id: 'materials',
        label: '上传行业资料（可选）',
        accept: '.pdf,.docx,.doc,.md,.txt',
        help: '可作为内置文档层证据，报告引用时保留来源与日期。',
      },
    ],
    knowledge: [
      { id: 'tech-snapshots', title: '新兴技术与专业对照快照', meta: '技术清单 · 演进对照 · 专业映射 · 内置', tag: '快照', default: true },
      { id: 'job-market', title: '岗位库白名单查询', meta: '岗位名排序与薪资区间 · 实时', tag: '岗位', default: true },
      { id: 'chart-specs', title: '共享图表规范', meta: '雷达图 · 桑基图 · 内联 SVG', tag: '图表' },
    ],
  },
  {
    slug: 'classroom-assistant',
    eyebrow: '课程教学工作台',
    lead: '用结构化选项说明课程、对象和教学任务，再限定本次允许引用的知识范围。',
    output: '课堂材料与带引用教学内容',
    sections: [
      {
        number: '01',
        title: '设置教学任务',
        description: '选择课程场景与本次希望完成的工作。',
        fields: [
          { id: 'course', label: '课程名称', type: 'text', required: true, placeholder: '例如：人工智能导论' },
          { id: 'learners', label: '授课对象', type: 'select', required: true, options: ['高职一年级', '高职二年级', '本科低年级', '本科高年级', '职业培训学员'] },
          { id: 'task', label: '任务类型', type: 'choice', required: true, span: 'full', options: ['课程答疑', '要点总结', '生成练习', '整理答疑记录'] },
        ],
      },
      {
        number: '02',
        title: '定义输出要求',
        description: '设置内容规模与教学侧重点。',
        fields: [
          { id: 'amount', label: '内容数量', type: 'select', required: true, options: ['3 项', '5 项', '8 项', '10 项'] },
          { id: 'difficulty', label: '难度', type: 'choice', required: true, options: ['基础', '进阶', '综合'] },
          { id: 'focus', label: '教学侧重点', type: 'multi', span: 'full', options: ['概念理解', '案例分析', '操作实践', '课堂互动', '考核复习'] },
          { id: 'context', label: '补充说明', type: 'textarea', span: 'full', placeholder: '例如：需要附参考答案，并标出引用所在章节……' },
        ],
      },
    ],
    example: {
      course: '人工智能导论',
      learners: '高职一年级',
      task: '生成练习',
      amount: '3 项',
      difficulty: '基础',
      focus: ['概念理解', '案例分析'],
      context: '基于第 1 章生成课堂练习，附参考答案和资料定位引用。',
    },
    knowledge: [
      { id: 'course-textbook', title: '《人工智能导论》课程资料', meta: '讲义、课件与章节索引 · 24 份', tag: '课程', default: true },
      { id: 'teaching-plan', title: '课程标准与授课计划', meta: '教学目标与周次安排 · 6 份', tag: '标准', default: true },
      { id: 'exercise-bank', title: '课堂练习样例库', meta: '已审核练习 · 186 题', tag: '题库' },
      { id: 'faq-records', title: '历史课堂答疑记录', meta: '匿名问答 · 92 条', tag: '答疑' },
    ],
  },
  {
    slug: 'ai-interview',
    eyebrow: '模拟面试工作台',
    lead: '补充目标岗位与练习方式，让每轮提问都围绕岗位要求和真实经历展开。',
    output: '交互式模拟面试与证据化复盘',
    sections: [
      {
        number: '01',
        title: '设置目标岗位',
        description: '岗位信息越具体，问题和追问越贴近真实场景。',
        fields: [
          { id: 'role', label: '目标岗位', type: 'text', required: true, placeholder: '例如：Java 后端实习生' },
          { id: 'stage', label: '求职阶段', type: 'select', required: true, options: ['实习', '校招', '社招转岗', '升职竞聘'] },
          { id: 'mode', label: '练习模式', type: 'choice', required: true, span: 'full', options: ['完整模拟', '专项突破', '压力追问'] },
        ],
      },
      {
        number: '02',
        title: '配置面试节奏',
        description: '选择题量和希望重点观察的能力。',
        fields: [
          { id: 'questions', label: '基础题量', type: 'choice', required: true, options: ['3 题', '5 题', '8 题'] },
          { id: 'language', label: '面试语言', type: 'select', required: true, options: ['中文', '中英混合', '英文'] },
          { id: 'focus', label: '重点能力', type: 'multi', span: 'full', options: ['专业基础', '项目经历', '问题解决', '沟通表达', '职业动机', '压力应对'] },
          { id: 'resume', label: '匿名经历摘要', type: 'textarea', required: true, span: 'full', placeholder: '简述教育背景、项目和实习经历；请删除姓名、电话等敏感信息。' },
        ],
      },
    ],
    example: {
      role: 'Java 后端实习生',
      stage: '实习',
      mode: '完整模拟',
      questions: '3 题',
      language: '中文',
      focus: ['专业基础', '项目经历', '问题解决'],
      resume: '计算机相关专业，完成过 Spring Boot 校园二手交易平台项目，负责接口设计与 MySQL 数据建模。',
    },
    knowledge: [
      { id: 'role-competency', title: '数字技术岗位能力库', meta: '岗位能力模型 · 42 类', tag: '岗位', default: true },
      { id: 'interview-rubric', title: '结构化面试评价标准', meta: '评分维度与行为锚点 · 18 份', tag: '评价', default: true },
      { id: 'question-bank', title: '企业面试题样例库', meta: '匿名真题与追问 · 326 题', tag: '题库' },
      { id: 'resume-evidence', title: '简历证据识别规则', meta: '项目与经历核验规则 · 12 份', tag: '规则' },
    ],
  },
  {
    slug: 'career-guidance',
    eyebrow: '就业指导工作台',
    lead: '说明求职目标、自身条件和现实约束，SKILL 会先建立证据表，再给出有优先级的求职动作。',
    output: '岗位匹配证据表、简历改进建议与求职行动计划',
    sections: [
      {
        number: '01',
        title: '设定求职目标',
        description: '目标越具体，方向判断和证据表越贴近真实投递。',
        fields: [
          { id: 'goal', label: '目标岗位或方向', type: 'text', required: true, placeholder: '例如：Java 后端实习' },
          { id: 'stage', label: '当前阶段', type: 'select', required: true, options: ['在校找实习', '应届校招', '社招转岗', '在职转型'] },
          { id: 'task', label: '本次任务', type: 'choice', required: true, span: 'full', options: ['职业定位', '岗位匹配', '简历改进', '求职行动计划', 'Offer 评估'] },
        ],
      },
      {
        number: '02',
        title: '补充条件与约束',
        description: '约束决定建议的可行性，缺项会标注为假设。',
        fields: [
          { id: 'region', label: '目标地区', type: 'text', placeholder: '例如：广州（留空表示不限）' },
          { id: 'time', label: '每周可投入时间', type: 'select', options: ['5 小时以内', '5–10 小时', '10–20 小时', '20 小时以上'] },
          { id: 'context', label: '匿名经历摘要', type: 'textarea', required: true, span: 'full', placeholder: '简述教育背景、项目、实习与技能；请删除姓名、电话等敏感信息。' },
        ],
      },
    ],
    example: {
      goal: 'Java 后端实习',
      stage: '在校找实习',
      task: '岗位匹配',
      region: '广州',
      time: '5–10 小时',
      context: '计算机相关专业，完成过 Spring Boot 校园二手交易平台项目，负责接口设计与 MySQL 建模；暂无实习经历。',
    },
    autoFillExample: true,
    uploads: [
      {
        id: 'resume',
        label: '上传简历',
        accept: '.pdf,.docx,.doc,.md,.txt',
        help: 'PDF / Word / Markdown / 纯文本，单个 ≤6MB；请先删除身份证号、住址等敏感信息。已为你附带测试简历，可移除后换自己的。',
        demoFile: 'resume',
      },
    ],
    knowledge: [
      { id: 'industry-data', title: '产业与就业数据文档', meta: '就业大盘、薪酬行情、职教政策 · 内置快照', tag: '产业', default: true },
      { id: 'job-snapshot', title: '高职岗位库切片文档', meta: '岗位量级与分布口径 · 内置快照', tag: '岗位', default: true },
      { id: 'output-schemas', title: '匹配表与行动计划模板', meta: '输出结构模板 · 3 份', tag: '模板' },
      { id: 'evidence-writing', title: '经历成果化改写指南', meta: '证据表达规则 · 1 份', tag: '写作' },
    ],
  },
  {
    slug: 'training-data-qa',
    eyebrow: '数据治理工作台',
    lead: '描述数据任务、规模与验收重点，再选择标注规范和业务规则知识库。',
    output: '训练样本、质检报告与抽检任务',
    sections: [
      {
        number: '01',
        title: '定义数据任务',
        description: '说明数据用途和预期处理规模。',
        fields: [
          { id: 'task', label: '任务类型', type: 'select', required: true, options: ['文本分类', '信息抽取', '问答生成', '对话指令', '多轮对话'] },
          { id: 'amount', label: '目标样本量', type: 'text', required: true, placeholder: '例如：200 条' },
          { id: 'stage', label: '当前阶段', type: 'choice', required: true, span: 'full', options: ['黄金种子', '批量扩增', '标注验收', '版本封存'] },
        ],
      },
      {
        number: '02',
        title: '配置质量检查',
        description: '选择数据划分和本轮必须通过的质量门禁。',
        fields: [
          { id: 'split', label: '数据集划分', type: 'select', required: true, options: ['80 / 10 / 10', '70 / 15 / 15', '自定义划分', '仅独立评测集'] },
          { id: 'format', label: '交付格式', type: 'choice', required: true, options: ['JSONL', 'JSON', 'CSV'] },
          { id: 'checks', label: '质检项目', type: 'multi', required: true, span: 'full', options: ['Schema', '事实证据', '业务规则', '重复样本', '数据泄漏', '分布偏差'] },
          { id: 'schema', label: '字段与标注说明', type: 'textarea', required: true, span: 'full', placeholder: '例如：input 为用户问题，output 为标准答复，category 为一级意图标签……' },
        ],
      },
    ],
    example: {
      task: '问答生成',
      amount: '200 条',
      stage: '黄金种子',
      split: '80 / 10 / 10',
      format: 'JSONL',
      checks: ['Schema', '事实证据', '重复样本', '数据泄漏', '分布偏差'],
      schema: '基于客服问答数据构造候选黄金种子；input 为问题，output 为答复，category 为业务意图。',
    },
    knowledge: [
      { id: 'annotation-schema', title: '标注 Schema 与字段字典', meta: '字段定义与示例 · 16 份', tag: 'Schema', default: true },
      { id: 'business-rules', title: '业务规则与禁答边界', meta: '规则条目 · 286 条', tag: '规则', default: true },
      { id: 'golden-examples', title: '已验收黄金样本库', meta: '专家确认样本 · 1,240 条', tag: '样本' },
      { id: 'qa-rubric', title: '数据质检验收标准', meta: '门禁与抽检规范 · 9 份', tag: '质检' },
    ],
  },
]

export const configOf = (slug: string): UseTaskConfig | undefined =>
  USE_TASK_CONFIGS.find(item => item.slug === slug)
