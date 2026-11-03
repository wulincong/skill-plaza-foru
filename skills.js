const skills = [
  {
    slug: 'industry-education-report',
    name: '产教决策报告',
    identifier: 'industry-education-report',
    summary: '面向院校、政府和园区生成有证据、可审查的产业与专业建设决策报告。',
    category: '产业与专业建设',
    tags: ['产教融合', '专业建设', '决策报告'],
    dependencies: ['可信的产业、岗位、专业或就业资料', 'Python 3（运行报告校验脚本时）'],
    limitations: ['最新报告需要重新核验来源、年份、范围和统计口径。', '缺少院校微观数据时会保留缺口，不编造就业率、岗位缺口或招生规模。'],
    minimalInput: '使用 $industry-education-report，为广东省某高职院校制作新能源汽车专业建设报告，受众为院校管理者，基期为 2024 年。',
    output: '交付报告 Markdown、结构化 report.json、证据与口径附录，以及结构和语义验收结果。',
    featured: true,
    updatedAt: null,
    kind: 'industry'
  },
  {
    slug: 'classroom-assistant',
    name: '课堂助教',
    identifier: 'classroom-assistant',
    summary: '在授权课程资料范围内完成带引用答疑、要点总结、练习生成和答疑记录整理。',
    category: '课程与教学开发',
    tags: ['课程资料', '课堂练习', '引用答疑'],
    dependencies: ['本次明确授权的课程材料'],
    limitations: ['不会用模型记忆或联网搜索补充课程事实。', '资料不足或越界内容会说明缺口并列入待教师处理清单。'],
    minimalInput: '使用 $classroom-assistant，基于我提供的《人工智能导论》第 1 章生成 3 道课堂练习并附参考答案和定位引用。',
    output: '输出带定位引用的答复、课程资料要点、课堂练习，或待教师处理清单。',
    featured: true,
    updatedAt: null,
    kind: 'teaching'
  },
  {
    slug: 'ai-interview',
    name: 'AI 面试练习',
    identifier: 'ai-interview',
    summary: '结合目标岗位、岗位要求和简历开展逐题模拟面试、智能追问与证据化复盘。',
    category: '实训与就业',
    tags: ['模拟面试', '就业辅导', '回答复盘'],
    dependencies: ['目标岗位', '简历或匿名经历摘要；岗位要求可选'],
    limitations: ['评分只衡量本次回答表现，不代表录用概率或个人总体能力。', '不会代替用户作答，也不会自动上传简历或面试内容。'],
    minimalInput: '使用 $ai-interview，目标岗位是 Java 后端实习生，岗位要求和匿名简历见附件，请开始 3 题模拟面试。',
    output: '输出岗位能力地图、逐题问答与针对性追问，并引用真实回答形成练习报告和改进建议。',
    featured: true,
    updatedAt: null,
    kind: 'interview'
  },
  {
    slug: 'career-guidance',
    name: '就业指导',
    identifier: 'career-guidance',
    summary: '基于目标、经历、岗位要求和现实约束，制定可执行的职业定位与求职行动方案。',
    category: '实训与就业',
    tags: ['职业定位', '岗位匹配', '简历优化', '求职计划'],
    dependencies: ['目标岗位或职业方向', '简历、经历摘要或其他可核验材料'],
    limitations: ['建议基于用户提供的事实和岗位信息，不承诺录用结果。', '最新招聘状态、薪资行情和劳动法规需要按时间、地区和来源重新核实。'],
    minimalInput: '使用 $career-guidance，目标是 Java 后端实习，请根据我的匿名简历和岗位描述列出匹配证据、关键缺口和 30 天行动计划。',
    output: '输出职业方向判断、岗位匹配证据、材料改进建议、求职行动计划或 offer 比较矩阵。',
    featured: true,
    updatedAt: null,
    kind: 'career'
  },
  {
    slug: 'training-data-qa',
    name: '训练样本构造与标注质检',
    identifier: 'training-data-qa',
    summary: '从治理数据构造可追溯训练样本，检查重复、泄漏、分布和业务规则并编排专家抽检。',
    category: '数据治理与模型底座',
    tags: ['数据治理', '标注质检', '训练数据'],
    dependencies: ['治理数据、任务模板和标注规则'],
    limitations: ['未经专家确认的生成结果只能标为候选。', '负责数据构造与验收，不负责执行模型训练。'],
    minimalInput: '使用 $training-data-qa，基于附件中的客服问答数据和标注规则构造 200 条候选黄金种子，并输出泄漏、重复和分布质检报告。',
    output: '交付四类数据集、质检报告、问题样本、专家抽检任务，以及可追溯版本记录。',
    featured: true,
    updatedAt: null,
    kind: 'data'
  }
];

const categories = ['全部', '产业与专业建设', '课程与教学开发', '实训与就业', '数据治理与模型底座'];
