# 数据聚合规范（fetch_data.py）

## 数据源

| 项 | 值 |
|---|---|
| 数据库 | MySQL 5.7，`192.168.8.1:3908`，库 `ai_crowd_souring_extend`（配置在 `db_config.json`） |
| 岗位主表 | `c_company_position`（约 1500 万行，在招约 960 万） |
| 企业地址表 | `c_company_address`（城市来源：`province`/`city` 字段，经 `company_address_id` 关联） |
| 类别字典表 | `c_position_type`（快照存于 `position_type_dict.json`，行业根节点如 人工智能=1242、智能网联汽车=1243） |

## 基础过滤条件（所有角度共用）

```sql
p.publish_state = 'PUBLISHING'      -- 在招
AND p.deleted = b'0'                -- 未删除
AND p.update_time >= 近 N 天        -- 时间窗（--days，默认365）
AND p.position_type LIKE '%,<行业子树ID>,%'  -- 行业归属（串匹配类别ID）
AND (地址在目标地区)                 -- --scope gd_ai 或 --region
```

## 聚合角度一览（报告每屏的数据来源）

| 角度 | 输出字段 | 聚合方法 | 进入报告的条件 |
|---|---|---|---|
| 总量 | `total` | COUNT + COUNT(DISTINCT 企业/城市) | 必有（01 核心发现） |
| 城市分布 | `city` | JOIN 地址表 GROUP BY city，取 TOP21 | 城市数 ≥3（02 城市分布） |
| 技术赛道 | `subtrack` | **互斥主归属**：每个岗位的 position_type ID 串按 PRIORITY 列表（大模型算法>NLP>图像>机器学习>…>数据标注）取第一个命中的细分名，只计一次 | 分组 ≥3（03 技术赛道） |
| 城市×赛道矩阵 | `city_track` | 同一查询内 城市+互斥赛道归属 交叉计数；城市TOP6×分组TOP6，单元格=城市内占比% | 矩阵存在（04 城市×赛道热力图） |
| 岗位性质 | `jobtype` | GROUP BY type（社招/实习/兼职枚举映射） | 有数据（05 岗位结构左图） |
| 学历 | `edu` | GROUP BY education，枚举映射，按学历高低排序；应届/在校合并为一档 | 有数据（06 学历） |
| 经验 | `exp` | GROUP BY experience，枚举映射，按资历排序 | 有数据（07 经验） |
| 学历×经验交叉 | `edu_exp` | GROUP BY education, experience（矩阵） | 必有（与职教池互相对账） |
| **职教可进入岗位池** | `voc_pool` | **行级交叉筛选**：学历∈{大专,高职,中专/中技,高中,初中及以下,不限} 且 经验∈{应届/在校,1年以内,不限}；池内单独聚合 count/pct/城市TOP6/互斥赛道TOP7/薪酬分位数/关键词TOP10 | 池量>0（11 职教机会专题；文章职教段的唯一数据来源） |
| 薪酬 | `salary` | (min+max)/2 逐岗位取中值 → 排序求 P25/P50/P75/P90；`salary_hist` 按 7 档分箱 | 有效率>50%（08 薪酬水平） |
| 分赛道薪酬 | `salary_by_track` | 同薪酬口径 × **互斥主归属**（与赛道占比同一套归属逻辑，杜绝两套口径混拼） | 同上（08 第二张图 + 09 速览表） |
| 能力关键词 | `keywords` | 岗位 description × 36 个固定技能词表做包含计数，取 TOP18（未做同义归并） | 有数据（10 能力关键词） |
| ~~月度更新量~~ | `trend` | GROUP BY 月（**update_time 含批量同步伪影，仅留档，禁止进报告/下趋势结论**） | 不进报告 |
| 数据溯源 | `provenance` | 每条 SQL 行数/耗时留档 + 各维度与总量对账 + sha256 指纹；快照另存 `output/snapshots/` | 必有（verify_data.py Gate1 消费） |

## 关键口径（改代码前必读）

1. **赛道互斥**：岗位的 position_type 是多标签（如"算法工程师,大模型算法"），直接按标签加总占比会超过 100%（实测出现"合计132%"）。因此按 PRIORITY 从具体到通用取唯一主归属，占比之和 ≤100%。呈现层分组（大模型/生成式AI、计算机视觉…）在 `report_common.TRACK_GROUPS` 定义。
2. **薪酬单位是 K**：min_salary/max_salary 是 varchar 的"千元"数字，过滤 0<lo≤hi≤500 的异常后取区间中值。
3. **城市是"企业办公地址"**不是岗位发布地；广东省口径用 21 个地级市名单 + province LIKE 广东双保险。
4. **时间窗按 update_time**（有索引，快），不是 create_time。

## 输出 schema（report_data.json）

```json
{
  "meta":   {"region": "广东省", "industry": "人工智能", "days": 365, "generated_at": "..."},
  "total":  {"positions": 14303, "companies": 5089, "cities": 21},
  "city":   [["深圳市", 7496], ...],
  "subtrack": [{"name": "算法研究员", "count": 3504, "pct": 24.5}, ...],
  "city_track": {"rows": [{"name": "深圳", "count": 7496}], "cols": ["大模型/生成式AI", ...],
                 "cells": [[0, 0, 31.2], ...]},
  "jobtype": [{"name": "社招", "count": 13956, "pct": 97.6}, ...],
  "edu":    [{"name": "本科", "count": ..., "pct": 56.6}, ...],
  "exp":    [{"name": "3-5年", "count": ..., "pct": 35.9}, ...],
  "salary": {"valid": 14278, "valid_pct": 99.8, "p25": 12.5, "median": 22.5, "p75": 35.0, "p90": 47.5},
  "salary_hist": [{"name": "20-30K", "count": ..., "pct": 21.7}, ...],
  "salary_by_track": [{"name": "推荐算法", "count": ..., "median": 37.5}, ...],
  "keywords": [{"name": "Python", "count": 6222}, ...],
  "trend":   [{"ym": "2025-10", "count": 823}, ...],
  "provenance": {"generated_at": "...", "db": {...}, "params": {...}, "queries": [...],
                 "checks": [{"name": "赛道互斥归属合计 = 总量", "pass": true}, ...],
                 "all_checks_pass": true, "data_sha256": "..."}
}
```

## 数据真实性保障（五层 Gate，防"数据对、结论错、图错"）

1. **聚合即留档**：fetch_data.py 逐条记录 SQL 行数/耗时，各维度与总量对账（含职教池与学历×经验交叉矩阵的双向核算），快照存 `output/snapshots/`。
2. **五层 Gate**（verify_data.py）：数值一致性（数字溯源）→ 指标语义（禁用"可投递/增长最快/溢价"等表述）→ 图文一致（正文技能词必须实际上榜）→ 推断证据（无序列不谈动态、趋势页禁用）→ 渲染与安全（render_check 像素核验 + 敏感信息扫描）。
3. **渲染层复检**（render_check.py）：热力图从 PNG 提取单元格色深矩阵，与数值矩阵做秩相关（≥0.85 通过）——专抓"数据正确但图转置/画错"；并核验每页图表真实渲染。
4. **脱敏交付**（pack_delivery.py）：对外包剔除 provenance.queries（SQL）等内部信息，打包前后双次敏感扫描（IP/本机路径/SQL/凭据）。
5. **渲染只吃大纲**：render_report.py 不连数据库；管住大纲+复检渲染，即管住全链路。

## 新增角度的方法

在 fetch_data.py 里加一段聚合 → 写入 out['新角度']（同时加进 provenance 的 checks）→ 在 gen_outline.py 的 build_outline() 里加对应的屏生成逻辑（含进入条件）→ 渲染器无需改动（图表数据由大纲带入）。候选新角度：企业规模/行业交叉（JOIN c_company_archive）、地图可视化（城市×经纬度，见 chart-gallery.md 的 map_choropleth）。
