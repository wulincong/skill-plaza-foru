# 023 · 城市热点图：省内白名单查询、省份资源包与报告校验

**状态**：已实现（2026-09-29；真实数据库广东、浙江报告均已跑通，见验证。原 023（省内白名单查询）与 024（省份资源包泛化）于 2026-10-19 合并，见 076）。

## 动机

城市热点图必须先取得与岗位统计相同筛选口径的跨城市记录，再用有标准编码和离线边界依据的地图展示；查询失败、边界缺失或「其他」总量不可得时都不能静默补图或把缺失误写成 0。单一广东边界文件无法泛化到其他省份，需要按省份注册的资源包。

## 约定细节

- **查询**：`scripts/career-market-query.mjs` 注册 `city-distribution`——只接受 `province`（普通城市 query 仍接受 `city`），默认广东省，`limit` 固定 20；`scripts/career-market-queries/city-distribution.sql` 按 `a.province` 分组 `a.city`，按 count 降序 `LIMIT 20`。关键词、岗位词、实习谓词与现有广州查询共用模板（占位 `{{PROVINCE}}`）。
- **省份资源包**：`chart-visualization/resources/regions/registry.json` 是省份唯一索引；每个 `regions/cn/<provinceCode>/manifest.json` 声明 scope、城市编码映射、GeoJSON、SHA-256、来源与许可状态。当前广东 `440000`（21 城）、浙江 `330000`（11 城；浙江边界为 DataV 离线副本，许可待核实）。`scripts/validate-resources.mjs` 遍历 registry 校验 scope/编码/别名/边界数/SHA-256，支持 `--province` 过滤。**未注册省份不得绘制地图**（chart-visualization 与 career-guidance 的 SKILL.md、`skills.ts`、`piRunner.ts` 同步该前置条件）。
- **热点图契约**：`chart-visualization/references/heatmap-chart.md` 固定 `rows[].code`、`coveredCodes`、`totalCount`、`otherCount`、中性色缺失值与 `CH_CITY`/失败状态块字段。
- **执行链**：中国目标地区先调 `city-distribution(province, limit=20)`，成功输出 `<figure data-chart-skill="heatmap-chart" data-chart-id="CH_CITY">`；失败/超时/边界缺失输出「热点图未评估」及原因；没有同口径总量时不能凭空计算「其他」。
- **服务端校验**：`web/server/lib/htmlReport.ts` 校验 figure 的 `data-chart-skill`、CH_CITY、成功 SVG 的 `title/desc/figcaption`，以及 `data-chart-status="unassessed"` 的可读失败原因；`web/server/index.ts` 在 HTML 落盘时记 `recorder.note({htmlReport})` 与 `RunRecord.report.html`，不改写、不阻塞用户报告。
- **failureHint 措辞检查已移除（2026-10-16，并行会话落地）**：曾以正则从图注措辞猜「查询失败」（「未返回/无结果」等词邻近「热点图/城市分布」即命中），2026-10-15 收紧为动作锚定后仍三度误杀线上成功报告（公网 run j8z9/uaw0/58na，其中 uaw0 命中的恰是本记录约定的「中性色/未返回记录」文案本身）；根因**不该从文本猜状态**，已删除 failureHint 正则与「跨城市查询失败必须显示热点图未评估」检查（结构校验/未评估原因校验/矛盾校验保留，单测反转为移除回归 12/12）。**干净替代（待实现，用户暂缓）**：`career-market-query.mjs` 每次执行向会话沙箱写机器可读结果文件（`query-outcomes.jsonl`：queryId/ok/error/elapsedMs/行数），校验器读该文件权威判定 city-distribution 成败——失败要求 `data-chart-status="unassessed"` 或「热点图未评估」，成功要求 CH_CITY 图；无文件回落宽松行为并告警。落地前「查询失败必须标未评估」仅靠技能提示词，无服务器强制。

## 成本与取舍

- 采用省份资源包而不是全国单一大 GeoJSON：按需加载、独立校验、独立处理来源许可；不让模型在运行时下载或拼接边界。浙江资源增加约 118 KiB 离线边界与 11 城映射。
- 固定 TOP 20 并沿用并发 2 约束，未增加岗位表索引或统计快照；同口径总量未提供前「其他」标未评估，避免重复全量聚合与虚假汇总。
- 真实会话两次出现 Pi 侧非 ASCII 提示词多字节截断（目标省份显示「��」），Agent 靠工作区标识 `-gd`/`-zj` 正确解析；Pi 侧编码问题待排查。

## 后续扩展路线

- 为同口径总量增加受控来源（total query 或统计快照）后再生成数值「其他」；DataV 许可复核后扩展省份或全国资源。

## 验证（2026-09-29 真实数据库端到端）

- 广东（workspace `sess-heatmap-gd`）：`city-distribution` 约 55s 返回广州/深圳，报告约 118 KiB 通过 `validateCompleteHtmlReport`，含 21 条广东边界 path。
- 浙江（workspace `sess-heatmap-zj`）：约 33s 返回杭州/宁波，报告约 77 KiB 校验 `pass:true`、heatmap `status:present`，含 11 条浙江边界 path。
- 两省均小样本（省内仅 2 城返回数据），报告按小样本口径加「代表性有限」说明；未返回城市以中性色标示缺失。
- `node scripts/validate-resources.mjs` 返回 2/2 省份全部通过；htmlReport 单测与前端构建通过。

## 2026-11-03 · 全部省级行政区的下一级边界（已实现）

**动机与口径**。只注册广东和浙江时，其他地区即使已有可靠统计也缺少可绘制的离线边界。当前 34 个省级行政区均在 `chart-visualization/resources/regions/registry.json` 注册，共 498 个单元。内地 333 个地级行政区与 32 个省直管县级单位分别标识。四个直辖市按 85 个区县，港澳台分别使用来源中的 18 个地方行政区、7 个堂区加 1 个填海区、22 个县市。城市级查询若只返回直辖市合计，仍需补取区县数据才能按区县填色。

**接口与维护**。兼容原 manifest、cityNameToCode 与 GeoJSON 入口，region 的 level 与 codeSystem 可覆盖 registry 的默认值。台湾地区保留五位 COUNTYCODE 的前导零，香港使用地区字母，澳门使用 OSM relation ID 字符串。重名短名不入映射。`scripts/import-regional-boundaries.py:83,109,185`（相对图表技能目录）读取带指纹的输入，在全新的输出目录生成资源。内地统一到 CTAmap 2026 层，区划时间为 2025 年末。广东和浙江原 64 个名称映射及文件路径兼容。该两包的新来源及许可替代本记录早期的 DataV 来源待核实状态，历史图稿仍按其原图注署名。港澳台各包记录对应数据源、版本、许可与派生过程。

**取舍**。各地实际统计层级不同，因此不将区县、堂区和省直管单元统一宣称为地级市。共享边界同步简化；若原始覆盖的接边存在微小偏差，保留未共边的外缘。通过预先生成离线文件，在线绘图无需下载边界或安装维护用 GIS 依赖。图鉴附录使用单独的边界数据块，`scripts/update-region-gallery.py:10` 对小岛和孔洞增加坐标精度，避免画布取整消去几何环。

**验证与后续**。`scripts/validate-resources.mjs:60,144` 校验标识、层级、名称、父级、几何环与文件哈希。34 包全通过，重建目录与入库资源逐文件一致。21 项制图、5 项静态资源示例和 12 项 HTML 回归通过。七地独立试画完成。390/1280 px 断网 Chrome 逐一切换 498 个单元，核对 19 个地标点击、34 组来源与许可链接，1,436 个几何环全部保留。将来更换快照需重新锁定来源并复核行政区调整、代码和几何，无数据地区继续按未评估处理。
