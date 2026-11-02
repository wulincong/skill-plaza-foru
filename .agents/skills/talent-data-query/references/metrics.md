# 指标与口径

运行 `capabilities` 获取当前执行器的指标名、枚举与限制；本页解释容易混淆的统计含义。

| 指标 | 口径 |
|---|---|
| positions.count | 样本内去重岗位主键记录数 |
| companies.count | 非空且非 0 的企业 ID 去重数；missingN 表示企业 ID 缺失的岗位记录数 |
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

每个指标有稳定 name、样本内 metricId、metricVersion、cohortFingerprint、method 和实际 evidenceIds；contentHash 绑定筛选、值、方法与质量，不绑定临时文件路径。两组对比输出第二组减第一组；占比差单位为百分点，薪酬差仍为 K/月。

首期薪酬采用固定分箱 `<3 / 3–6 / 6–10 / 10–15 / 15–25 / 25K+`，不接受自定义分箱或按城市/岗位分组的薪酬摘要；可用独立 cohort 实现同口径城市/岗位对比。新分箱、专业、多标签分布与 LQ 后续扩展时须新增能力并验收。
