# program.json 结构与证据交接

`program.json` 由本技能编写，是培养方案的可校验结构契约。查询请求、指标名、单位、分母和清洗规则由 [人才数据库查询](../../talent-data-query/SKILL.md) 定义，以查询结果为准。学时学分总数、各类占比和红线结论一律由 `scripts/program.py` 从课程表和进程表计算，契约里不手填总数。

## 顶层字段

```json
{
  "schema": "training-program/1",
  "title": "大数据技术专业人才培养方案（2026 级）",
  "status": "draft",
  "as_of": "2026-11-18",
  "meta": {},
  "sources": [],
  "metrics": [],
  "jobGroups": [],
  "capabilityDomains": [],
  "standards": [],
  "curriculum": {},
  "schedule": {},
  "assurance": {},
  "graduation": {},
  "decisions": [],
  "diff": {},
  "redlineOverrides": {}
}
```

`status` 为 draft/final；仍有待核对标准或未决关键取舍时只能是 draft。`as_of` 为证据截止日（YYYY-MM-DD）。

## meta

```json
{
  "majorName": "大数据技术",
  "majorCode": "510205",
  "level": "高职专科",
  "duration": {"years": 3, "maxYears": 5},
  "entryRequirement": "高中阶段学校毕业或具有同等学力",
  "region": "广东省",
  "industries": ["数字经济"],
  "schoolConstraints": {"note": "订单班约束原文或 user: 引用"},
  "version": "2026-1",
  "basedOnStandard": {"name": "高等职业学校专业教学标准：大数据技术", "sourceId": "S_STD", "status": "verified"}
}
```

`majorCode` 须为 6 位数字。`basedOnStandard.status` 为 verified 时 `sourceId` 必须指向 standards 里 status=verified 的条目所引来源；标准未取得原文时填 pending，并按「标准核对」规则登记决策。

## sources 与 metrics（与产教报告同构）

`sources` 含 id、title、publisher、url、published、accessed、locator、scope、excerpt。url 按来源类型：

- **`corpus:` 本地同类方案语料**（主用）：`corpus:方向/文件名.txt`，指向仓库 `data/人才培养方案/` 的清洗 TXT，脚本按 `索引.csv` 核对条目、sha256 与 excerpt 原句，用法与选样规则见 [本地语料库](local-corpus.md)；用于课程设置理由、培养目标依据、版本差异的对标引用，不作岗位需求证据、不用于实施保障。
- 共享统计：工作区 `data/tq-…/result.json`，构建脚本回填 **contentHash** 与 **dataReadAt**。
- 用户附件 `uploads/` 相对路径；粘贴材料 `user:` 加名称；官方网页 `https://`。excerpt 均逐字摘录原句。

`metrics` 含 id、label、value、unit、period、region、population、definition、source_ids；直接引用查询结果的指标加 `binding`（如 `{"metricId":"all/positions.count","field":"value"}`、薪酬中位数 `value.median`、分布 `rows`），写稿时可省略 value，脚本从已校验工件填入，手填数值与指纹不符会验收失败。规则与产教报告 [数据契约](../../industry-education-report/references/data-contract.md) 一致，本技能不另设口径。

## jobGroups（岗位群与典型工作任务）

```json
{
  "id": "JG1",
  "name": "数据平台运维与开发",
  "summary": "面向……的岗位群判断",
  "positions": [
    {"name": "大数据运维工程师", "stage": "entry", "metricIds": ["M_JG1_CNT"], "sourceIds": []},
    {"name": "数据开发工程师", "stage": "development", "metricIds": ["M_JG1_CNT"], "sourceIds": []}
  ],
  "workTasks": [
    {"id": "WT1", "name": "集群部署与监控", "capabilityIds": ["C-OPS-1", "C-OPS-2"]}
  ]
}
```

岗位名称必须来自查询返回的岗位名、用户材料或国家标准的职业面向原文；stage 区分初始岗（entry）与发展岗（development）。每个岗位群至少引用一个指标或材料来源，`workTasks` 把典型工作任务连接到能力项（DACUM 式分解的中间层，名称用真实工作过程语言，不造岗位）。

## capabilityDomains（能力域与能力项）

```json
{
  "id": "CD-OPS",
  "name": "平台运维能力域",
  "capabilities": [
    {
      "id": "C-OPS-1",
      "name": "能完成 Hadoop 集群部署与基础调优",
      "evidence": {"status": "verified", "metricIds": ["M_JG1_SKILLS"], "sourceIds": []},
      "note": "证据边界或样本量说明"
    }
  ]
}
```

每个能力项 `evidence.status`：

- verified：绑定至少一个 metricId 或 sourceId，脚本核验可解析；
- user-material：仅用户材料支撑（订单班、企业专家意见等），sourceIds 必须指向用户来源；
- insufficient：样本量不足或检索不到，**必须**存在一条用户明确选择「按现有证据继续」的 decisions 记录，否则校验失败。

## cultivation（培养目标与培养规格的校本表述）

```json
{
  "goal": "培养德智体美劳全面发展，掌握……的高素质技术技能人才",
  "goalBasis": {"standardSourceId": "S_STD", "metricIds": ["M_JG1_CNT"], "note": "在标准培养目标基础上，结合区域岗位证据强调……"},
  "spec": [
    {"dimension": "素质", "items": [{"text": "坚定拥护中国共产党领导……", "sourceIds": ["S_STD"]}]},
    {"dimension": "知识", "items": [{"text": "掌握分布式存储基本知识", "capabilityId": "C-OPS-1"}]},
    {"dimension": "能力", "items": [{"text": "能完成集群部署与调优", "capabilityId": "C-OPS-1"}]}
  ]
}
```

`goal` 是校本化表述，`goalBasis` 引用标准来源与区域证据；spec 按素质/知识/能力三维分解，能力维条目应连接 capabilityId（引用能力域），知识/素质条目引用标准或课程材料来源。标准降级路径（原文未取得且用户已决策继续）下 `standardSourceId` 可省略，改为 `metricIds` 引用区域岗位证据并在 note 说明待核对。

## standards（国家教学标准逐要素核对）

```json
{
  "element": "职业面向",
  "content": "面向数据工程技术人员……等职业群",
  "sourceId": "S_STD",
  "status": "verified",
  "note": "原文摘录位置"
}
```

`element` 覆盖专业教学标准要素：概述、专业名称（代码）、入学基本要求、基本修业年限、职业面向、培养目标、培养规格、课程设置及学时安排、师资队伍、教学条件、质量保障和毕业要求中与本方案相关的项。status=verified 时 content 必须是来源原文摘录（excerpt 核对）且 sourceId 可解析；检索不到原文的要素 status=pending，**sourceId 可省略**（降级路径没有标准来源可指，不得用其他来源冒充），note 说明缺口，且待核对项需要决策记录（见 [标准核对](standards-check.md)）。**禁止凭记忆编写标准条文**——校验只认 sources 里可回查的原文。

## curriculum（课程体系）

```json
{
  "courses": [
    {
      "id": "CS1",
      "name": "Hadoop 大数据平台运维",
      "category": "professional-core",
      "theoryHours": 40,
      "practiceHours": 32,
      "credits": 4.5,
      "semesters": [3],
      "assessment": "考试",
      "domains": [{"capabilityId": "C-OPS-1", "level": "H"}, {"capabilityId": "C-OPS-2", "level": "M"}],
      "rationale": {"text": "岗位证据显示……", "metricIds": ["M_JG1_SKILLS"], "sourceIds": ["S_STD"]}
    }
  ]
}
```

category 取值：public-required（公共基础必修）、public-elective（公共选修）、professional-base（专业基础）、professional-core（专业核心，须 6–8 门）、professional-extension（专业拓展）、internship（岗位实习，全实践）、comprehensive-practice（综合实践，全实践）。`semesters` 为 1–6。每门课必有 `description`（课程简介 ≥20 字）与 `typicalContent`（典型教学内容/工作任务 ≥30 字），专业核心课分别加严到 ≥40 字、≥80 字（去空白计字）。每门课 `rationale` 必须给出可解析的 metricIds/sourceIds，说明设置理由回溯到能力域与岗位证据；`domains.level` 用 H/M/L 标支撑强度。七个类别在课程表中均须出现（附录学时结构表完整的前提）。

## pedagogy（教学实施与考核评价，硬下限）

```json
{
  "teachingImplementation": "……教学模式、教学方法与手段、教学组织形式……（≥150 字）",
  "assessment": "……课程考核、实践考核、多元评价与以证代考……（≥150 字）"
}
```

对应正文第九章两节；写法对标精读语料同类章节，不得以一两句原则话凑数。

## 内容深度下限汇总（校验阻断）

| 项 | 下限 |
|---|---|
| 每门课程简介 | ≥20 字（核心课 ≥40 字） |
| 每门课典型内容/工作任务 | ≥30 字（核心课 ≥80 字） |
| 培养规格 | 素质/知识/能力每维 ≥5 条，每条 ≥12 字 |
| 职业面向 | ≥2 个岗位群，每群 ≥2 个岗位，覆盖初始岗与发展岗 |
| 教学实施 / 考核评价 | 各 ≥150 字 |
| 毕业要求 | ≥4 条，总字数 ≥80 字，每条 ≥8 字 |
| 课程类别 | 七类齐全 |
| 对标语料 | corpus: 来源 ≥3 份 |
| 图表规划 | ≥3 种图型家族，条形家族 ≤ 全部图一半（见下） |

## chartPlan（图表规划，先定图再取数）

取数之前先写图表规划：每张图回答什么判断、选什么图型及理由、需要哪些数据、数据来自哪里。规划落进契约后由脚本校验，成品页面再按同一口径二次校验（`scripts/check_page.py`）。

```json
{
  "id": "F_EDU",
  "question": "区域岗位的学历要求如何分布？",
  "kind": "barh",
  "reason": "学历类别为长标签，横向排名便于阅读",
  "section": "四、职业面向",
  "dataOrigin": "query",
  "dataRefs": {"metricIds": ["M_EDU"]}
}
```

- `kind` 取 chart-visualization [figure/1](../../chart-visualization/references/figure-spec.md) 可执行集：bar、barh、line、grouped-line、faceted-line、province-map、scatter、distribution、histogram、ecdf、paired、change-distribution、median-change、interval、matrix。雷达/桑基/堆叠柱等专题图当前不可执行出图，不进规划。
- `section` 是插图落点，必须精确等于正文章节标题（一～十二、附录A–D）。
- `dataOrigin` 与 `dataRefs`：`query` 须绑定可解析 metricIds（按规划一次性把各图岗位数据取齐）；`corpus` 须绑定 corpus: 来源；`user` 须绑定用户材料来源；`program`（方案自带：课程表、进程表、能力课程支撑、学时结构）在 fromProgram 写明取数字段，不需要外部取数。

**图型家族判定口径（构建期与成品期同一口径）**：条形家族——竖柱（bar）、横条（barh）及分组/堆叠/多面板柱条——算**一种**；其余按分析关系各算一种：折线（line/grouped-line/faceted-line）、地图（province-map）、散点、分布（distribution/histogram/ecdf）、配对（paired/change-distribution/median-change）、区间（interval）、矩阵（matrix）。硬门槛：**全页 ≥3 种不同家族，条形家族 ≤ 全部面板的一半**；一张图稿的多面板须同家族，跨家族拆成两张图。report-rendering [图表选型](../../report-rendering/references/chart-selection.md)「各图确实都在做同类比较时统一图型、记录理由即可」的弹性**对本技能不适用**。诚实边界不变：趋势要真实多期数据、分布要原始观测，取不到就换有数据支撑的图型，不造数据凑图型。

## 依据引用（可读名称 + 锚点链接）

正文所有引用证据的位置——职业面向「依据」列、培养目标依据、培养规格「关联能力/来源」列、6.1「支撑能力项」列、6.3「证据」列、实施保障来源、附录交叉引用——由构建脚本统一写成 `[可读名称](#锚点)`：

- 指标：`岗位学历要求为大专的记录数 3,014 条（全国，2026-11-23）`——名称、数值、单位、地域、时期（数值由构建回填）。
- 来源：`2026 级人工智能技术应用专业人才培养方案 · 教学进程安排表合计行`——标题加定位，corpus 标题按索引回填。
- 能力项：写能力项名称。

链接落点是网页附录 A/B 的条目锚点（`program.py page` 生成带 id 的块：A.1 来源、A.2 指标、附录B 能力项定义），完整口径、时期、分母与摘录都在落点；有真实 http(s) 地址的来源同时给外链。**正文（含 Word）不出现「指标 M_」「来源 S_」「能力 C-」写法**；编号只保留在结构化产物（program.json、t05-package.json）与附录条目标识上。sources/metrics/capability 的 id 须满足锚点格式（字母开头，仅字母数字-_）。

## schedule（教学进程）

```json
{
  "semesters": [
    {"no": 1, "weeks": 20, "activities": [{"name": "课堂教学", "weeks": 16}, {"name": "集中实训", "weeks": 2}, {"name": "考试与机动", "weeks": 2}]}
  ],
  "internship": {"seminars": [5, 6], "weeks": 26, "note": "第5学期18周+第6学期8周，集中安排"}
}
```

每学年教学活动合计 40 周（两个学期 weeks 之和）。岗位实习周数折算约 6 个月（默认 20–30 周内，可集中或分阶段）。

## assurance（实施保障）

师资、实训条件、合作企业三节，每节 `{status: supported|pending, text, sourceIds}`。**只能引用用户提供的办学条件材料**；未提供时 status=pending 并列入附录 C 待补清单，不得编造师资数量、实训室清单或合作企业名称。

## graduation（毕业要求）

`requirements` 为条目数组（含思想品德、学分、实习、证书等），`minCredits` 由脚本对照总学分核验。

## decisions（决策记录）

```json
{"id": "D1", "question": "区域样本量不足，是否扩大到全省口径？", "askedAt": "2026-11-18", "userReply": "扩大到全省", "scope": "evidence"}
```

所有关键取舍必须留痕：缺证三选项的选择原话、标准待核对的继续授权、订单班约束的确认。`scope` 为 evidence/standards/curriculum/schedule/general。样本不足继续、标准 pending 出稿，均以 decisions 里用户原话为授权依据。

## diff（版本对比，可选）

用户提供旧版时启用：`{"basis": "旧版方案来源 id", "items": [{"section": "专业核心课程", "old": "……", "new": "……", "reason": "依据 M_XXX……"}]}`。逐项差异写入附录 D。

## redlineOverrides（校本红线，可选）

默认红线见 [红线参数](redlines.md)。校本要求（如总学分上限、顶岗实习时长）由用户提供后在此覆盖，`{"providedBy": "user:教务处要求", "values": {"totalHoursMax": 2700}}`；未提供的项不得自行假设。

## 构建产物

`python3 <技能目录>/scripts/program.py build program.json` 在校验全部通过后，把以下文件写入 `output/program-<短哈希>/`：

| 文件 | 内容 |
|---|---|
| program.md | 方案正文全文（十二章 + 附录 A–D，依据为可读名称链接） |
| program.json | 补齐计算字段与绑定数值后的结构化方案 |
| validation.json | 红线对照表、图表规划审计、证据核验结果、警告与待核对清单 |
| t05-package.json / t05-overview.md | 课程开发任务包（[T05 契约](t05-package.md)） |
| program.docx | 可编辑 Word 版（环境缺少依赖时跳过并在 validation.json 说明） |
| program-files.json | 交付登记清单（name/path/sha256），供 register_delivery.py --files-from 使用 |

`python3 <技能目录>/scripts/program.py page program.json --work work` 在图稿就绪后（按 chartPlan 用 chart-visualization render+verify 出完图）生成 `work/page-body.json`：正文各章块（依据链接内嵌）、附录 A/B 锚点条目、按规划章节插入的 figure 块。组装 page.json 时正文与附录直接用这组块，不要手工改写正文文字或锚点。

校验失败时 build 阻断并列出全部不达标项与原因；修数后重跑。正文、Word 与结构化三份内容同源，修订一律改 program.json 再重建，不手改产物。

**成品校验（登记交付前必过）**：`python3 <技能目录>/scripts/check_page.py <工作区根> --page work/page.json --web output/public/<站点目录>`。校验实际嵌入图型（≥3 家族、条形 ≤ 一半、与 chartPlan 一致）、编号写法为零（「指标/来源/能力 + 编号」全页、裸编号正文）、依据链接无死链且链接文字可读。任一项不达标**不得 register_delivery**，修复后重渲染重校验。
