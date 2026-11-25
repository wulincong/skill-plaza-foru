import { JOB_DICTIONARIES } from './jobDictionaries.ts'
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
  optionKeys?: Record<string, string>
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
  promptInstruction?: string
  sections: TaskSection[]
  example: Record<string, string | string[]>
  /** 进入页面时自动带入 example 作为默认值（方便直接运行测试） */
  autoFillExample?: boolean
  knowledge: KnowledgeItem[]
  /** 附件上传位；requiredUpload 声明运行前必须上传的文件类型。 */
  uploads?: UploadField[]
  requiredUpload?: { accept: string; label: string }
}

const jobSelect = (id: string, label: string, dictionary: string): TaskField => ({
  id, label, type: 'select', options: ['不限', ...Object.values(JOB_DICTIONARIES[dictionary]!).filter(x => x !== '不限')],
  optionKeys: { ...Object.fromEntries(Object.entries(JOB_DICTIONARIES[dictionary]!).map(([key, value]) => [value, key])), '不限': '' },
})

export const USE_TASK_CONFIGS: UseTaskConfig[] = [
  {
    slug:'competency-assessment',eyebrow:'岗位胜任力测评',
    lead:'结合真实岗位要求与个人材料，了解已有优势、能力差距和需要补充的证据。',
    output:'能力画像、任职门槛核验、JD与经历对照、提升及验证任务',
    promptInstruction:'请使用真实JD反推能力指标，对照我的材料完成胜任力初评并交付网页报告。按岗位方向选择5–10份同层级代表JD进行分析。明示要求与AI推导分开，资格单列，未知不补零。关键缺证先补问。',
    sections:[{number:'01',title:'确定测评目标',description:'填写目标岗位和工作性质，结合相关岗位JD进行分析。',fields:[
      {id:'role',label:'目标岗位',type:'text',required:true,placeholder:'例如：前端开发实习生'},
      jobSelect('positionType','工作性质','POSITION_TYPE'),
    ]},{number:'02',title:'补充个人材料',description:'至少提供一项技能、经历或简历；未提供的能力记为未知。',fields:[
      {id:'work',label:'工作／实习经历',type:'textarea',span:'full',placeholder:'单位、时间、职责和实际成果；课程项目不算正式工作年限'},
      {id:'projects',label:'项目经历',type:'textarea',span:'full',placeholder:'项目背景、本人负责内容、用到的技能及成果'},
      {id:'skills',label:'已掌握技能',type:'textarea',span:'full',placeholder:'写明能完成什么任务，避免只罗列技术名词'},
      {id:'resume',label:'简历摘要',type:'textarea',span:'full',placeholder:'可粘贴匿名简历，或上传文字版附件'},
      {id:'notes',label:'补充说明',type:'textarea',span:'full',placeholder:'希望重点评估的方向、已有成果链接或其他信息'},
    ]}],
    example:{role:'前端开发',positionType:'实习',projects:'独立完成Vue校园二手交易网站的列表、详情页面与接口联调。',skills:'掌握HTML、CSS、JavaScript、Vue；尚未使用自动化测试。'},
    uploads:[{id:'resumeFile',label:'上传简历',accept:'.pdf,.docx,.txt,.md',help:'支持文字PDF、DOCX、TXT、Markdown；只提取与能力有关的材料。'}],knowledge:[],
  },
  {
    slug: 'job-matching', eyebrow: '岗位智能匹配',
    lead: '填写求职条件，结合简历和岗位要求找到适合优先投递的岗位。',
    output: '最多20个推荐岗位、JD匹配依据、能力差距与求职建议',
    promptInstruction: '按岗位接口筛选JSON原样查询最多100个候选，对照我的真实简历和全部候选JD，按规则推荐最多20个并交付岗位匹配报告。不足时如实说明，不自动放宽条件。',
    sections: [{number:'01',title:'填写求职需求',description:'目标岗位必填，城市留空表示不限城市。',fields:[
      {id:'role',label:'目标岗位',type:'text',required:true,placeholder:'例如：前端开发'},
      {id:'city',label:'期望城市',type:'text',placeholder:'选填，留空不限城市，例如：广州市'},
      jobSelect('salary','期望薪资（K/月）','SALARY'),
      jobSelect('positionType','工作性质','POSITION_TYPE'),
      jobSelect('industry','行业偏好','INDUSTRY'),
      {...jobSelect('education','学历','EDUCATION'),help:'按岗位要求筛选；不选时在JD匹配中结合简历判断。'},
      {id:'graduation',label:'毕业状态',type:'select',options:['不限','在校生','应届毕业生','已毕业'],help:'未选择工作经验时，在校或应届映射对应经验Key。'},
      jobSelect('experience','工作／实习经验','EXPERIENCE'),
      {id:'resume',label:'简历摘要',type:'textarea',span:'full',placeholder:'可粘贴技能、项目和实习经历，或上传简历。请删除电话、邮箱等联系方式。'},
      {id:'notes',label:'补充说明',type:'textarea',span:'full',placeholder:'例如：排除外包、优先某类项目、通勤或其他要求'},
    ]}],
    example:{role:'前端开发',city:'广州市',positionType:'实习',graduation:'在校生',industry:'不限',salary:'不限',education:'不限',experience:'不限',resume:'计算机专业大三，掌握JavaScript、HTML、CSS和Vue，做过校园二手交易网站，负责页面组件和接口联调。',notes:''},
    uploads:[{id:'resumeFile',label:'上传简历',accept:'.pdf,.docx,.txt,.md',help:'支持文字PDF、DOCX、TXT、Markdown；最多6MB。没有简历时仅做条件推荐。'}],
    knowledge:[],
  },
  {
    slug: 'student-learning',
    eyebrow: '个性化学习规划',
    lead: '告诉我们你想从事的岗位，找到适合自己的课程和学习节奏。',
    output: '学习路线、每日任务、阶段成果与对应教材入口',
    promptInstruction: '请优先查询知识库课程包与教材，结合我的基础和时间安排学习顺序，生成带教材入口的个性化学习计划网页。缺少必要信息时先补问。',
    sections: [{
      number: '01', title: '填写学习需求', description: '目标岗位必填，其余信息帮助安排适合你的学习内容和时间。',
      fields: [
        { id: 'role', label: '目标岗位', type: 'text', required: true, span: 'full', placeholder: '例如：人工智能模型训练助理' },
        { id: 'goal', label: '学习目标', type: 'select', options: ['求职', '实习', '课程补基础', '项目实践'] },
        { id: 'foundation', label: '当前基础', type: 'textarea', span: 'full', placeholder: '专业、年级、已掌握的知识或做过的项目' },
        { id: 'availability', label: '可投入时间', type: 'text', span: 'full', placeholder: '例如：每周5天，每天1小时，希望8周完成' },
        { id: 'notes', label: '补充说明', type: 'textarea', span: 'full', placeholder: '例如：希望重点学习的内容、已有设备条件，或其他学习要求' },
      ],
    }],
    example: { role: '人工智能模型训练助理', goal: '实习', foundation: '计算机专业二年级，掌握 Python 基础，尚未训练过模型。', availability: '每周5天，每天1小时，希望8周完成', notes: '' },
    knowledge: [],
  },
  {
    slug: 'doc-translate',
    eyebrow: '文档翻译工作台',
    lead: '上传 PDF 并指定目标语言，翻译后可查看和下载译文 PDF。',
    output: '保留原文纸张、分栏和标题层级的译文 PDF',
    promptInstruction: '请按所选范围翻译上传的 PDF；范围留空时翻译全文。生成译文 PDF 后只简短说明译文语言、页数和未覆盖项。',
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
    lead: '写明谁要做什么决定。可附岗位调研、培养方案或排课表，生成决策简报。',
    output: '决策简报、结构化报告与证据复核',
    promptInstruction: '围绕决策问题生成简报。若核心判断仍缺证据，先说明影响，请我选择如何继续。',
    sections: [
      {
        number: '01',
        title: '确定报告范围',
        description: '查询地区岗位数据时填写地区和产业；仅分析校内材料时可留空。',
        fields: [
          { id: 'region', label: '目标地区', type: 'text', placeholder: '例如：广东省广州市' },
          { id: 'industry', label: '产业或岗位范围', type: 'text', placeholder: '例如：机器人产业' },
          { id: 'baseline', label: '观察时期', type: 'text', placeholder: '留空使用当前在招记录；历史分析请注明时间与材料' },
          { id: 'audience', label: '服务对象', type: 'choice', required: true, options: ['院校管理者', '政府部门', '产业园区'] },
        ],
      },
      {
        number: '02',
        title: '明确决策问题',
        description: '已有调研、课程或毕业去向材料可随任务提供。',
        fields: [
          { id: 'purpose', label: '决策问题', type: 'textarea', required: true, span: 'full', placeholder: '例如：哪些入门岗位适合作为高职实训项目的目标？' },
          { id: 'context', label: '补充材料与要求', type: 'textarea', span: 'full', placeholder: '可粘贴企业访谈或课程材料，并注明来源与日期' },
        ],
      },
    ],
    example: {
      audience: '院校管理者', region: '广东省广州市', industry: '机器人产业', baseline: '当前在招记录',
      purpose: '分析岗位的学历门槛，帮助专业负责人决定实训项目应优先面向哪些岗位。',
    },
    uploads: [{ id: 'materials', label: '补充研究材料', accept: '.md,.txt,.pdf,.docx', help: '可提供培养方案、访谈纪要或统计表。' }],
    knowledge: [],
  },
  {
    slug: 'teaching-diagnosis',
    eyebrow: '教学诊断工作台',
    lead: '上传周期内考勤与成绩数据，补充评教、课堂行为或教学进度，完成三层诊断、证据链归因与改进建议。',
    output: '三层诊断报告网页、授权风险名单文件与改进措施留档',
    promptInstruction: '先核对数据口径并如实报告数据质量问题；口径不明或核心数据缺项先询问。统计结论逐条标注范围与样本量，改进建议成稿后用决策卡让我逐项确认。',
    sections: [
      {
        number: '01',
        title: '确定诊断范围',
        description: '考勤与成绩为必传数据；评教、课堂行为、教学进度至少补充一项用于归因。',
        fields: [
          { id: 'period', label: '诊断周期', type: 'text', required: true, placeholder: '例如：2025-2026学年第一学期（2025-09-01 至 2026-01-15）' },
          { id: 'scope', label: '覆盖班级或专业', type: 'text', required: true, placeholder: '例如：大数据技术专业 2401-2403 班' },
          { id: 'audience', label: '读者角色', type: 'choice', required: true, options: ['教学质量管理者', '专业负责人', '督导'] },
        ],
      },
      {
        number: '02',
        title: '明确诊断关注点',
        description: '预警阈值与上期材料可选，用于风险名单授权与复诊对比。',
        fields: [
          { id: 'focus', label: '关注问题', type: 'textarea', span: 'full', placeholder: '例如：出勤下滑的班级与课程；某几门课不及格率偏高' },
          { id: 'thresholds', label: '预警阈值', type: 'text', span: 'full', placeholder: '留空用默认：缺勤率≥20%或缺勤≥10次；平均分<60或不及格≥2门' },
        ],
      },
    ],
    example: {
      period: '2025-2026学年第一学期（2025-09-01 至 2026-01-15）',
      scope: '大数据技术专业 2401-2403 班',
      audience: '专业负责人',
      focus: '排查出勤下滑的班级与不及格率偏高的课程',
      thresholds: '',
    },
    uploads: [
      { id: 'coreData', label: '考勤与成绩数据（必传）', accept: '.csv,.xlsx', help: '考勤记录与成绩数据各一份，单个文件 ≤6MB。' },
      { id: 'extraData', label: '评教 / 课堂行为 / 教学进度', accept: '.csv,.xlsx,.md,.txt', help: '可选；至少补充一项，归因分析更充分。' },
      { id: 'history', label: '上一周期报告或干预记录', accept: '.csv,.xlsx,.md,.txt,.pdf,.docx', help: '用于复诊对比与成长档案。' },
    ],
    requiredUpload: { accept: '.csv,.xlsx', label: '考勤与成绩数据' },
    knowledge: [],
  },
  {
    slug: 'courseware-studio',
    eyebrow: '课件生成工作台',
    lead: '写明教学单元与课时数，上传允许使用的教材、教案或实训指导书，生成课证对齐、逐页出处可查的课件。',
    output: '可编辑 PPTX 课件、网页预览版与课件档案',
    promptInstruction: '课件内容只用我上传与列示的材料；先交付校订稿，实训安全步骤等我确认后再定稿。',
    sections: [
      {
        number: '01',
        title: '设定教学单元',
        description: '主题与课时决定课件骨架；学生程度影响讲解与测验难度。',
        fields: [
          { id: 'topic', label: '单元主题', type: 'text', required: true, placeholder: '例如：工具坐标标定' },
          { id: 'course', label: '课程名称', type: 'text', required: true, placeholder: '例如：工业机器人现场编程' },
          { id: 'hours', label: '课时数', type: 'choice', required: true, options: ['1 课时', '2 课时', '4 课时', '6 课时'] },
          { id: 'learners', label: '学生程度', type: 'select', options: ['中职一年级', '中职二年级', '高职一年级', '高职二年级', '本科低年级', '本科高年级', '职业培训学员'] },
          { id: 'style', label: '课件风格', type: 'choice', options: ['简约蓝', '暖橙', '墨绿', '黑白打印'] },
        ],
      },
      {
        number: '02',
        title: '材料范围与课标',
        description: '课件事实只来自这里列示的材料；未覆盖的要点会标注待教师补充。',
        fields: [
          { id: 'materialsNote', label: '材料范围说明', type: 'textarea', required: true, span: 'full', placeholder: '例如：教材第 4 章 4.1–4.3（p.58–72）、实训指导书任务三；均已上传' },
          { id: 'standardsNote', label: '课程标准条目', type: 'textarea', span: 'full', placeholder: '粘贴条目编号与原文，如 GQT-3.2 能够完成工具坐标系的建立与标定' },
        ],
      },
    ],
    example: {
      topic: '工具坐标标定',
      course: '工业机器人现场编程',
      hours: '2 课时',
      learners: '高职二年级',
      style: '简约蓝',
      materialsNote: '教材第 4 章 4.1–4.3（p.58–72）与实训指导书任务三，均已上传',
      standardsNote: 'GQT-3.2 能够完成工具坐标系的建立与标定；GQT-3.3 能够按安全操作规程进行设备上电与运行',
    },
    uploads: [
      { id: 'materials', label: '教学材料（必传）', accept: '.pdf,.docx,.doc,.md,.txt', help: '教材章节、教案或实训指导书；课件内容只来自这些材料。单个 ≤6MB。' },
      { id: 'images', label: '图片素材（可选）', accept: '.png,.jpg,.jpeg,.webp', help: '设备照片、企业案例图等自备素材，引用时标注提供方。' },
    ],
    requiredUpload: { accept: '.pdf,.docx,.doc,.md,.txt', label: '教学材料' },
    knowledge: [],
  },
  {
    slug: 'class-placement',
    eyebrow: '智能分班工作台',
    lead: '上传学生名单，选择均衡或分层模式，获得可审计、可复现的分班结果与班级画像对比报告。',
    output: '每班名册、班级画像对比报告网页与审计包',
    promptInstruction: '请先解析名单并告诉我字段完整性，再求解；首次结果出来后用决策卡让我确认或重掷一次。',
    sections: [
      {
        number: '01',
        title: '设置分班参数',
        description: '班级数量与容量决定规模约束；分层模式需要测评列。',
        fields: [
          { id: 'mode', label: '分班模式', type: 'choice', required: true, span: 'full', options: ['均衡分班', '分层分班'], help: '均衡：各班成绩性别等维度接近；分层：按测评画像与方向志愿聚类组班。' },
          { id: 'classCount', label: '班级数量', type: 'text', required: true, placeholder: '例如：6' },
          { id: 'capacity', label: '每班容量上限', type: 'text', required: true, placeholder: '例如：50' },
          { id: 'title', label: '任务名称', type: 'text', placeholder: '例如：2026级智能制造学院新生分班' },
        ],
      },
      {
        number: '02',
        title: '维度权重与特殊约束',
        description: '留空用默认（成绩 0.7、性别 0.3）；约束需注明理由，未申报的信息不使用。',
        fields: [
          { id: 'weights', label: '均衡维度与权重', type: 'text', span: 'full', placeholder: '留空默认成绩 0.7 + 性别 0.3；也可写“成绩 0.6、性别 0.2、生源地区 0.2”' },
          { id: 'directions', label: '方向与班级数（分层模式）', type: 'textarea', span: 'full', placeholder: '例如：智能制造 3 个班、新能源汽车 3 个班；留空按志愿需求自动分配' },
          { id: 'constraints', label: '特殊约束申请', type: 'textarea', span: 'full', placeholder: '例如：2026001 与 2026002 双胞胎同班（家长申请）；2026003 与 2026004 需回避（教务备案）' },
        ],
      },
    ],
    example: {
      mode: '均衡分班',
      classCount: '6',
      capacity: '50',
      title: '2026级新生分班',
      weights: '',
      directions: '',
      constraints: '2026008 与 2026009 双胞胎同班（家长申请）',
    },
    uploads: [
      { id: 'roster', label: '学生名单（必传）', accept: '.csv,.xlsx', help: '含学号、姓名，可含性别、生源地区、成绩、测评列与志愿列；单个 ≤6MB。' },
      { id: 'lastResult', label: '上次分班结果（可选）', accept: '.csv,.xlsx', help: '用于对照说明，不直接决定本次分班。' },
    ],
    requiredUpload: { accept: '.csv,.xlsx', label: '学生名单' },
    knowledge: [],
  },
  {
    slug: 'course-scheduling',
    eyebrow: '排课沙盘工作台',
    lead: '上传教学任务、班级、教室、作息与校历模板，生成零冲突的多套课表方案；选定后导出课表与日历。',
    output: '方案对比网页、课表 Excel、课程日历 ics 与冲突归因',
    promptInstruction: '请先校验模板数据，缺关键字段先问我；求解后给我三套方案对比与推荐，我选定方案后再导出课表和日历。',
    sections: [
      {
        number: '01',
        title: '学期与偏好',
        description: '学期信息在校历模板内；这里补充会影响求解的偏好。',
        fields: [
          { id: 'semester', label: '学期名称', type: 'text', required: true, placeholder: '例如：2026-2027学年第一学期' },
          { id: 'preference', label: '方案侧重', type: 'choice', required: true, options: ['自动生成三套对比', '教师到校天数少', '班级与实训室负载均衡'], help: '默认生成教师集中、负载均衡、折中三套方案供对比。' },
          { id: 'extra', label: '补充说明', type: 'textarea', span: 'full', placeholder: '例如：体育课尽量不排午后；数控实训室周五下午被企业培训占用；双师课按模板教师列填写' },
        ],
      },
      {
        number: '02',
        title: '调停课（可选）',
        description: '学期中增量重排时填写；不填默认整学期排课。',
        fields: [
          { id: 'changes', label: '调停课需求', type: 'textarea', span: 'full', placeholder: '例如：T08 老师下周一外出停课；大数据2402 的平台部署实训停开；新开网络安全进阶 2 节给大数据2401' },
        ],
      },
    ],
    example: {
      semester: '2026-2027学年第一学期',
      preference: '自动生成三套对比',
      extra: '体育课尽量不排午后，实训课错峰',
      changes: '',
    },
    autoFillExample: true,
    uploads: [
      { id: 'info', label: '学校信息（必传）', accept: '.csv,.xlsx', demoFile: 'schedInfo', help: '学校名称、学期、开学周一与总周数；模板首表。' },
      { id: 'tasks', label: '教学任务（必传）', accept: '.csv,.xlsx', demoFile: 'schedTasks', help: '课程、班级、教师、周学时、连排与教室要求；双师/混编用分号分隔多值。' },
      { id: 'classes', label: '班级名单（必传）', accept: '.csv,.xlsx', demoFile: 'schedClasses', help: '班级ID、名称、人数与专业。' },
      { id: 'teachers', label: '教师名单（必传）', accept: '.csv,.xlsx', demoFile: 'schedTeachers', help: '教师ID、姓名与授课偏好（集中/分散）；任务表按 ID 或姓名引用。' },
      { id: 'rooms', label: '教室与实训室（必传）', accept: '.csv,.xlsx', demoFile: 'schedRooms', help: '容量、类型、设备与台套数；台套数是排课硬约束。' },
      { id: 'timetable', label: '作息时间（必传）', accept: '.csv,.xlsx', demoFile: 'schedTimetable', help: '节次、起止时间与时段（上午/下午）；连排不跨时段。' },
      { id: 'calendar', label: '校历（必传）', accept: '.csv,.xlsx', demoFile: 'schedCalendar', help: '每周一行；假期、1+X 考试窗口、企业轮岗用标记列注明。' },
      { id: 'blocks', label: '占用约束与权重（可选）', accept: '.csv,.xlsx', demoFile: 'schedBlocks', help: '每周不可用时段（例会、检修）；软约束权重。' },
    ],
    requiredUpload: { accept: '.csv,.xlsx', label: '教学任务表' },
    knowledge: [],
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
    output: '逐题模拟面试、回答复盘与同题重练',
    promptInstruction: '请从第一道面试题开始，等我回答后再继续。',
    sections: [
      {
        number: '01',
        title: '设置目标岗位',
        description: '岗位信息越具体，问题和追问越贴近真实场景。',
        fields: [
          { id: 'role', label: '目标岗位', type: 'text', required: true, placeholder: '例如：Java 后端实习生' },
          { id: 'stage', label: '求职阶段', type: 'select', options: ['实习', '校招', '社招转岗', '升职竞聘'] },
          { id: 'jd', label: '岗位要求', type: 'textarea', span: 'full', placeholder: '粘贴招聘说明中最想练习的一两条职责，例如“能定位故障并向客户解释处理方案”。' },
          { id: 'mode', label: '练习模式', type: 'choice', span: 'full', options: ['完整模拟', '专项突破', '压力追问'], help: '默认完整模拟，结束后集中复盘。' },
        ],
      },
      {
        number: '02',
        title: '配置面试节奏',
        description: '选择题量和希望重点观察的能力。',
        fields: [
          { id: 'questions', label: '主问题数', type: 'choice', options: ['3 题', '5 题', '8 题'], help: '默认 3 题，追问和同题重答不占题数。' },
          { id: 'language', label: '面试语言', type: 'select', options: ['中文', '中英混合', '英文'] },
          { id: 'focus', label: '重点能力', type: 'multi', span: 'full', options: ['专业基础', '项目经历', '问题解决', '沟通表达', '职业动机', '压力应对'] },
          { id: 'resume', label: '匿名经历摘要', type: 'textarea', span: 'full', placeholder: '可写一段项目、实习或课程经历，说明你本人负责哪一步。' },
        ],
      },
    ],
    example: {
      role: 'Java 后端实习生',
      stage: '实习',
      jd: '根据故障现象定位接口问题，并说明如何验证修复。',
      mode: '完整模拟',
      questions: '3 题',
      language: '中文',
      focus: ['专业基础', '项目经历', '问题解决'],
      resume: '计算机相关专业，完成过 Spring Boot 校园二手交易平台项目，负责接口设计与 MySQL 数据建模。',
    },
    uploads: [{ id: 'materials', label: '匿名简历或岗位说明', accept: '.pdf,.docx,.doc,.md,.txt', help: '请先删除姓名、电话、客户名称等信息。每个文件最多 6 MB。' }],
    knowledge: [],
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

/** Keep the displayed label separate from the API key. Omitted choices impose no filter. */
export function jobFilters(values: Record<string, string | string[]>): Record<string, string> {
  const config = configOf('job-matching')!
  const result: Record<string,string> = {keyword:String(values.role ?? '').trim()}
  const city=String(values.city ?? '').trim()
  if(city)result.city=city
  for (const field of config.sections.flatMap(s=>s.fields)) {
    if (!field.optionKeys) continue
    const choice=String(values[field.id] ?? '')
    const key=field.optionKeys[choice]
    if (choice && key === undefined) throw new Error('无效的岗位筛选选项')
    if(key)result[field.id]=key
  }
  if(!result.experience) {
    if(values.graduation==='在校生')result.experience='ON_CAMPUS'
    if(values.graduation==='应届毕业生')result.experience='GRADUATING'
  }
  return result
}

/** Assessment personal attributes inform evaluation, not vacancy filters. */
export function competencyFilters(values: Record<string, string | string[]>): Record<string,string> {
  const result: Record<string,string>={keyword:String(values.role ?? '').trim()}
  const choice=String(values.positionType ?? '')
  const field=configOf('competency-assessment')!.sections[0]!.fields.find(f=>f.id==='positionType')!
  if(choice && field.optionKeys?.[choice] === undefined)throw new Error('无效的工作性质')
  const key=field.optionKeys?.[choice]
  if(key)result.positionType=key
  return result
}
export function competencyContext(values: Record<string,string | string[]>): string[] {
  return ['【岗位接口筛选】',JSON.stringify(competencyFilters(values)),
    '【测评范围】',JSON.stringify({mode:'direction',positionId:''}),
    '【测评材料】',JSON.stringify(Object.fromEntries(['work','projects','skills','resume','notes'].map(k=>[k,String(values[k] ?? '')])))]
}
