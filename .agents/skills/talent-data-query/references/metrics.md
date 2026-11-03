# 指标与口径

运行 `capabilities` 获取当前执行器的指标名、枚举与限制；本页解释容易混淆的统计含义。

| 指标 | 口径 |
|---|---|
| positions.count | 样本内去重岗位主键记录数 |
| companies.count | 非空且非 0 的企业 ID 去重数；missingN 表示企业 ID 缺失的岗位记录数 |
| data_quality.summary | 按需计算企业 ID、地址关联、省、市、岗位名与来源缺失数，以及样本内最大平台更新时间；各项可能重叠，不能相加为缺失总人数 |
| education.distribution | 原始学历枚举；保留缺失、未知，不合并学历不限与缺失 |
| experience.distribution | 在校、应届、不限、年限上界桶；LESS_THAN_3 是 3 年以内，不解释为 1–3 年 |
| jobType.distribution | 社招、校招、实习、兼职等原始招聘类型；与经验标签及名称“实习”分开 |
| source.distribution | 数据来源，保留原始值、缺失量和其他；字面字符串 NULL 与 null 区分 |
| city.distribution / province.distribution | 企业关联地址的地域分布；全国城市带省份，缺失独立，非市场就业人数 |
| title.top | 同口径岗位名称排名，使用完整样本分母，含未展示的其他量与缺失量 |
| education_experience.cross | 学历×经验；每格 share 分母是整组岗位数，不是行内占比 |
| city_education.cross | 城市×学历，保留省份上下文与缺失；同样以整组岗位数为分母 |
| salary.summary | 有效薪资区间中点的均值、P25、median、P75、P90，单位 K_CNY/month |
| salary.distribution | 同一有效薪资中点的固定分箱；share 分母是有效薪资数 |

学历“大专/高职”和不限分别保留，不能把满足学历条件直接称为可录用。“职教宽口径”“明确大专”“叠加经验的入门池”是不同筛选，调用方必须明确条件，不使用含糊的可投率。

salary-policy/1 要求两端为严格数值（最多六位小数），0 < min <= max <= 100 K/月；区分 missing、non_numeric、non_positive、reversed、above_cap。原始有效小数保留，不先转整数；超过上限被剔除不代表这些岗位不存在。中点频数用于加权均值和分位数，分位数线性插值 h=(n-1)*p，最后展示舍入到六位小数。薪酬为招聘声明区间中点，不是实际收入。

低基数联合分组必须与基础总量对账；薪资有效量+排除量必须等于总量。计数使用可安全表示的整数，share 范围 0–1。未知/失败值不填 0；全部缺薪资返回 unavailable/null。

默认统计只计算所需字段。`positions.count` 的 missingN=0 表示岗位主键计数本身无缺失，不代表地区等属性完整；未请求质量指标时 `cohorts[].missingAddressN`、`freshness.sourceLatestUpdateAt` 为 null，`quality.dataQualityEvaluated=false`。`quality.allPass` 表示请求指标校验通过，不代表已评估所有源字段质量。地域分布等指标仍计算自身所需的缺失量；需要完整缺失率时增加 `data_quality.summary`，用各项缺失数除以同组 positions/denominator。

每个指标有稳定 name、样本内 metricId、metricVersion、cohortFingerprint、method 和实际 evidenceIds；contentHash 绑定筛选、值、方法与质量，不绑定临时文件路径。两组对比输出第二组减第一组；占比差单位为百分点，薪酬差仍为 K/月。

薪酬采用固定分箱 `<3 / 3–6 / 6–10 / 10–15 / 15–25 / 25K+`，不接受自定义分箱；可通过独立 cohort 实现同口径城市/岗位对比，也可通过显式方向规则请求 track_salary.summary。新分箱、专业与多标签分布需新增能力并验收；LQ可从完整城市×方向频数按有版本的公式派生。

1.2 扩展五项指标：track.distribution、city_track.cross、track_salary.summary、skills.distribution、track_skills.cross，见 [analysis.md](analysis.md)。分方向薪酬已支持，方向来自显式首个命中规则，不能把它当成官方产业细分。每组最多五条基础/交叉/方向/技能/薪酬聚合即可供完整报告使用；不请求来源/标题排名时避免额外扫描。新模块仍按 cohort 独立执行，不声称一次 CLI 等于一次扫描。

1.3扩展city_salary.summary：企业关联地址城市的完整薪酬摘要，返回省、市、count、validN、excludedN及summary；同salary-policy/1，不是实际收入。复用原完整薪酬频数查询按需增加城市维度，无方向规则也可请求；缺失省市保留。与city_education.cross联合使用时，按省市连接并检查同一城市岗位基数，学历要求比例以该城市全部岗位为分母。不得将城市平均/中位数按城市简单平均来替代总体分位。
