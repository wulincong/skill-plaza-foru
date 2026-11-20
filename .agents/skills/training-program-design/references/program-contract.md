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

category 取值：public-required（公共基础必修）、public-elective（公共选修）、professional-base（专业基础）、professional-core（专业核心，须 6–8 门）、professional-extension（专业拓展）、internship（岗位实习，全实践）、comprehensive-practice（综合实践，全实践）。`semesters` 为 1–6。每门课 `rationale` 必须给出可解析的 metricIds/sourceIds，说明设置理由回溯到能力域与岗位证据；`domains.level` 用 H/M/L 标支撑强度。

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
| program.md | 方案正文全文（十一章 + 附录 A–D） |
| program.json | 补齐计算字段与绑定数值后的结构化方案 |
| validation.json | 红线对照表、证据核验结果、警告与待核对清单 |
| t05-package.json / t05-overview.md | 课程开发任务包（[T05 契约](t05-package.md)） |
| program.docx | 可编辑 Word 版（环境缺少依赖时跳过并在 validation.json 说明） |
| program-files.json | 交付登记清单（name/path/sha256），供 register_delivery.py --files-from 使用 |

校验失败时 build 阻断并列出全部不达标项与原因；修数后重跑。正文、Word 与结构化三份内容同源，修订一律改 program.json 再重建，不手改产物。
