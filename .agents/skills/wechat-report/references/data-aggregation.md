# 报告数据契约

真实统计调用 talent-data-query 的公开CLI；本技能只构造统计需求、转换展示字段和绑定来源，不接触表结构或连接凭据。

## 报告计划

基础取数示例（只演示请求格式，不等于完整研究计划；分析流程见 [research-analysis.md](research-analysis.md)）：

~~~json
{
  "schema": "wechat-report-plan/1",
  "filters": {
    "region": {"level": "province", "name": "广东省"},
    "industries": [{"id": "15", "includeDescendants": true}]
  },
  "sections": ["overview", "geography", "requirements", "salary", "vocational"],
  "audience": "院校管理者",
  "execution": {"freshness": "live", "deadlineMs": 360000}
}
~~~

filters 与 execution 使用共享查询契约；先读 talent-data-query/references/request-contract.md。industryLabel 可补充准确的选题名，不能用于改变实际过滤。未设置更新时间即全时间范围在招记录。

| 章节 | 共享指标 |
|---|---|
| overview | positions.count、companies.count、data_quality.summary |
| geography | city_education.cross（完整频数用于城市数和分布） |
| requirements | 学历、经验、招聘类型分布与 education_experience.cross |
| salary | salary.summary、salary.distribution |
| vocational | 同一范围叠加明确学历×经验交集，统计独立子样本 |
| tracks | track.distribution |
| city_tracks / lq | city_track.cross；LQ 从完整频数派生 |
| track_salary | track.distribution、track_salary.summary |
| skills | skills.distribution |
| track_skills | track.distribution、skills.distribution、track_skills.cross |

方向/技能章节需在计划中显式增加 analysis。下例为“名称规则”，不能称为官方产业赛道；规则按顺序取第一个命中，未命中保留未分类。可先用共享 resolve 获得岗位类型ID，再用 roleIds（完整ID，非产业ID）设置规则。

~~~json
{
  "tracks": [
    {"key": "algorithm", "label": "算法研发", "titleAny": ["算法", "SLAM"]},
    {"key": "control", "label": "控制与调试", "titleAny": ["控制", "调试"]},
    {"key": "other_engineering", "label": "工程实施", "titleAny": ["工程师"]}
  ],
  "skills": ["Python", "C++", "ROS", "SLAM", "PLC"]
}
~~~

将该对象放在计划 analysis 字段中，并选择所需章节。具体计数、方向归属、文本命中、薪酬清洗由共享工具执行。技能是忽略大小写的子串匹配；每岗位每词最多一次，ROS会命中ROS2，词间可重叠。需要同义归并/词界时先扩展共享策略，不能在报告中私改口径。

## 结果与展示

- collect_data 通过共享 capabilities/query/inspect 接口工作，生成 report_data.json 与 report_binding.json；不导入共享工具内部模块。后续load_data核验来源manifest、文件指纹，并用纯适配器重建展示数据。
- 岗位/企业数、城市、学历经验、薪酬、方向、技能均由明确 metricId 追溯。大纲 bindings 指定目标字段、输入字段、固定投影与引用；数值正文/图表需通过 verify_data。
- 薪酬采用共享 salary-policy/1，100K/月上限、保留小数、线性分位数与六档分布。图例和文字同步，不能延用旧整数化、500K上限或七档算法。
- 城市分布由完整 city_education.cross 频数归并，城市数不等于TOP N行数；省市组合防止全国同名市混合。地址缺失独立记录。
- 职教子样本在用户原有筛选上取学历、经验交集。与原筛选交集为空时由完整学历×经验频数确认空池，不扩大样本。满足条件不等于会被录用。
- coverage 保留每节 complete/empty/unavailable/unsupported 等状态；缺失模块不填假零。salary无有效样本、技能无描述时明确缺口。
- 正文和图表只读已保存结果，不重新查询。条件或数据刷新后生成新修订，不混合不同读取时间的统计。
- 内部evidence保留实际执行SQL与聚合值，核查表直接消费；逐语句耗时尚不可靠，展示为未可靠测量，批次耗时另列。不重建SQL冒充实际执行。
- 平台更新时间不是职位发布时间，当前数据不能支撑招聘增速、同比或就业率结论。
