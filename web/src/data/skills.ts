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
    summary: '围绕开课、实训和人才培养决定生成简报，也可提供区域产业全景观察。',
    tags: ['产教融合', '专业建设', '决策报告'],
    preconditions: '读者、决策问题和可核对的调研材料',
    outputs: [
      '报告 Markdown',
      '结构化 report.json',
      '证据与口径附录',
      '结构与语义验收结果',
    ],
    dependencies: [
      '决策问题与读者；查询岗位统计时还需地区和产业范围',
      '岗位统计由人才数据库查询技能提供，可复用同一范围的已核验结果',
    ],
    limitations: [
      '最新报告需要重新核验来源、年份、范围和统计口径。',
      '缺少院校微观数据时会保留缺口，不编造就业率、岗位缺口或招生规模。',
    ],
    minimalInput:
      '使用 $industry-education-report，为广州高职院校分析机器人产业的岗位门槛，并建议哪些实训项目应优先调整。',
  },
  {
    slug: 'training-program-design',
    name: '产教培养方案设计',
    identifier: 'training-program-design',
    categoryId: 'industry',
    audiences: ['manager', 'teacher'],
    summary: '基于区域岗位取证与国家专业教学标准原文核对，生成或修订产教融合专业人才培养方案，学时学分红线硬校验。',
    tags: ['培养方案', '产教融合', '课程体系'],
    preconditions: '专业名称与代码 + 办学层次学制 + 服务区域 + 目标产业范围',
    outputs: [
      '培养方案网页版（十一章 + 证据附录）',
      '可编辑 Word 版',
      '学时学分红线校验记录',
      '课程开发任务包',
      '新旧版差异报告（提供旧版时）',
    ],
    dependencies: [
      '岗位统计由人才数据库查询技能提供，每项岗位判断可回溯查询口径',
      '国家专业教学标准需知识库或用户提供原文；取不到的要素标待核对并请用户决策',
    ],
    limitations: [
      '任一红线（总学时、实践占比、公共基础课、选修、核心课门数等）不达标即阻断出稿。',
      '实施保障只引用用户提供的办学条件材料，未提供则标注待补，不编造师资或合作企业。',
    ],
    minimalInput:
      '使用 $training-program-design，为我校高职三年制大数据技术专业（510205）制订产教融合人才培养方案，服务广东省的数字经济产业。',
  },
  {
    slug: 'course-development',
    name: '产教课程开发',
    identifier: 'course-development',
    categoryId: 'teaching',
    audiences: ['teacher', 'manager'],
    summary: '把培养方案课程卡片开发为完整课程：JD 原文抽样驱动典型工作任务，知识点上挂能力项、下接考核点，课证合规逐条核对，成套交付课程包。',
    tags: ['课程开发', '任务驱动', '课程标准'],
    preconditions: '课程名称与定位 + 目标岗位或岗位族 + 总课时（或培养方案课程开发任务包）',
    outputs: [
      '16–18 周课程大纲（模块·任务·评价三栏对齐）',
      '知识点与技能点清单（挂接能力项与考核点）',
      '单元教学设计样例与实训任务书（前两个模块）',
      '课程评价方案（权重与合格标准）',
      '资源缺口清单（标注生成或人工准备）',
      '标准合规核对表与结构化课程包',
    ],
    dependencies: [
      '岗位事实与 JD 原文抽样由人才数据库查询技能提供，任务表述可回溯样本指纹',
      '课程标准与技能标准原文需知识库或用户提供；取不到的条目标待核对并请用户决策',
    ],
    limitations: [
      '无考核点或无能力项挂接的知识点不得进入大纲，脚本校验不通过即阻断交付。',
      '目标岗位在库内无样本且无用户材料时，课程定位标证据不足并等待用户决策，不静默降级。',
    ],
    minimalInput:
      '使用 $course-development，基于培养方案任务包开发《Hadoop 大数据平台运维》完整课程（72 课时，面向数据平台运维岗位群）。',
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
    slug: 'courseware-studio',
    name: '智能课件生成',
    identifier: 'courseware-studio',
    categoryId: 'teaching',
    audiences: ['teacher'],
    summary: '在允许的教材与实训材料范围内生成课证对齐、逐页出处可查的课件，实训安全内容确认后定稿。',
    tags: ['课件生成', '课证对齐', '证据可查'],
    preconditions: '教学单元主题、课时数与允许使用的材料范围',
    outputs: [
      '可编辑 PPTX 课件',
      '课件网页预览版',
      '逐页出处与课标对齐标注',
      '版权与授权状态清单',
      '教师待确认清单（实训安全步骤）',
      '资源入库清单',
    ],
    dependencies: [
      '教材章节、教案或实训指导书（上传或明确列示）',
      '可选：课程标准条目、学生程度、自备图片素材',
    ],
    limitations: [
      '课件内容只来自允许的材料，未覆盖要点标注待教师补充，不用通用知识顶替。',
      '图片只用教师素材与教材原文图，示意图明确标注，不生成图片冒充设备实图。',
      '涉及实训安全的内容未经教师确认步骤顺序，不定稿导出。',
    ],
    minimalInput:
      '使用 $courseware-studio，为《工业机器人现场编程》单元「工具坐标标定」生成 2 课时课件，材料用我上传的教材第 4 章与实训指导书任务三。',
  },
  {
    slug: 'ai-interview',
    name: 'AI 面试练习',
    identifier: 'ai-interview',
    categoryId: 'career',
    audiences: ['teacher', 'student'],
    summary: '练目标岗位的面试题，根据你的回答追问，结束后对照原话找出最值得重答的一题。',
    tags: ['模拟面试', '就业辅导', '回答复盘'],
    preconditions: '目标岗位，可选岗位说明和匿名经历',
    outputs: [
      '逐题问答记录（含追问链）',
      '按岗位能力整理的对话复盘',
      '原话引用与待验证项清单',
      '同题重答与两次回答的变化',
    ],
    dependencies: [
      '目标岗位名称',
      '可选的岗位职责、匿名简历或项目片段',
    ],
    limitations: [
      '复盘只基于本人提供的信息，不联网核查任职资格。',
      '不承诺面试结果，只给出证据化的改进建议。',
    ],
    minimalInput:
      '使用 $ai-interview，我应聘新能源汽车售后技术支持，实训中负责记录充电故障码。请用中文做两道主问题的完整模拟，先问第一题。',
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
    slug: 'resume-police',
    name: '简历优化警察',
    identifier: 'resume-police',
    categoryId: 'career',
    audiences: ['student', 'teacher'],
    summary: '逐句审查简历，解释面试官看不出哪些贡献，给出可替换的改稿，并可按项目生成面试追问。',
    tags: ['简历审查', '项目改写', '面试出题'],
    preconditions: '匿名简历或一段项目经历',
    outputs: ['原句诊断与修改建议', '可复制的简历改稿', '按需生成的面试问题、追问与评价要点'],
    dependencies: ['本人简历或经历片段', '可选的目标岗位、职级和招聘要求'],
    limitations: ['当前广场共享对话历史，请先移除身份和联系方式。', '缺少证据的成果会标记为待补。'],
    minimalInput: '使用 $resume-police，我投测试实习。原句是“负责接口测试”，实际做了登录接口的过期令牌用例并复现了一个缺陷。请解释原句的问题，给我一句可直接替换的写法。',
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
  {
    slug: 'class-placement',
    name: '智能分班',
    identifier: 'class-placement',
    categoryId: 'teaching',
    audiences: ['manager', 'teacher'],
    summary: '公平可审计的均衡分班与基于能力画像的分层分班：种子与日志全程留痕，公示前一次受控重掷。',
    tags: ['均衡分班', '分层分班', '审计复现'],
    preconditions: '学生名单（CSV/XLSX）+ 班级数量、容量与分班模式',
    outputs: [
      '每班名册 CSV 与全员名册',
      '班级画像对比报告网页（分布图与均值差）',
      '审计包：随机种子、哈希链求解日志、复现命令',
      '分层模式的志愿满足率与未满足原因',
    ],
    dependencies: [
      '学生名单（编号或姓名必需，性别、成绩、测评、志愿可部分缺失）',
      '分班参数：班级数量、每班容量上限、均衡或分层模式',
    ],
    limitations: [
      '分班由固定种子脚本求解，随机性可复现；重掷最多一次且留痕。',
      '特殊约束只采用申报过的条目，未申报的个人背景不采集、不使用。',
      '分层模式需要测评画像字段，缺失时先说明再由用户决定处理方式。',
    ],
    minimalInput: '使用 $class-placement，上传名单后按均衡模式分 6 个班，每班上限 50 人，维度按成绩与性别。',
  },
  {
    slug: 'course-scheduling',
    name: '排课智能体',
    identifier: 'course-scheduling',
    categoryId: 'teaching',
    audiences: ['manager', 'teacher'],
    summary: '教务前置沙盘：硬约束零冲突求解多套课表方案，建模企业轮岗、1+X 窗口、混编班与双师同堂，支持学期中增量调课。',
    tags: ['排课', '产教约束', '零冲突', '增量调课'],
    preconditions: '教学任务、班级、教室与实训室、作息时间、校历五张模板表（CSV/XLSX）',
    outputs: [
      '2-3 套零冲突课表方案与指标对比网页',
      '未排入课程的冲突归因与放松建议',
      '选定方案的课表 Excel（班级/教师/教室三视图）',
      '课程日历 ics（轮岗与考试窗口周次自动剔除）',
      '增量调课变更清单（最小扰动、留档可回退）',
    ],
    dependencies: [
      '必需：教学任务（课程、班级、教师、周学时、连排）与教室资源（容量、类型、台套数）、作息、校历',
      '可选：教师偏好、企业轮岗批次、1+X 考试窗口、双师协同、不可用时段、已有课表',
    ],
    limitations: [
      '班级为最小排课单位，混编班表达整班合并，不支持班内分组。',
      '排不进的课程不进课表而是归因报告，取舍由教务决定后重排。',
      '不替换教务系统，定位是排课前的前置推演与沙盘。',
    ],
    minimalInput: '使用 $course-scheduling，上传教学任务、班级、教室、作息与校历模板，生成三套方案并推荐。',
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
