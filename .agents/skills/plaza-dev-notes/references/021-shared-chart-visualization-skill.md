# 021 · 共享图表与城市热点图 Skill

- 状态：已实现（2026-09-29 初期以子模块整合；2026-11-03 按用户决定转为主仓库内置目录，21 个文件原样保留，迁移与验证见 092）。以下早期实现细节保留为设计来源，当前分发方式以 092 为准。
- 动机：柱状图、折线图、直方图、堆叠柱状图、地图和城市热点图规则此前散落在 career-guidance 子仓库、主仓库 reports 和提示词中；需要统一维护，并为岗位需求分析增加条件化城市热点图。
- 约定细节：初期新增 `.agents/skills/chart-visualization` 子模块，指向本地共享仓库提交 `1f9e20a`；包含 `SKILL.md`、`references/common-rules.md`、六类图表规则、广东省 21 城和浙江省 11 城编码映射、按省份 registry/manifest 管理的离线 GeoJSON、资源说明/校验脚本和无气泡示例。资源校验入口为 `.agents/skills/chart-visualization/scripts/validate-resources.mjs`，当前覆盖广东和浙江两省，边界许可状态待核实。career-guidance 子模块提交 `4dbcc6c` 固定中国目标地点先解析 registry，成功图表标识为 `data-chart-skill="heatmap-chart" data-chart-id="CH_CITY"` 和 `limit=20`，查询失败可用 `data-chart-status="unassessed"` 状态块并给出原因；`web/server/lib/skills.ts` 与 `piRunner.ts` 提示同步该分支。`web/server/lib/htmlReport.ts:100-180` 校验 figure 标记、CH_CITY、成功 SVG 可访问性和失败原因，`web/server/index.ts:752-758` 将摘要写入 recorder note 与 `RunRecord.report.html`，不阻塞用户报告展示。
- 成本与取舍：多一个共享 Skill 子模块和一个待创建的远端仓库；换取所有图表规则、可访问性、来源口径和地图边界约束集中维护。热点图采用行政区填色而非气泡，避免绝对数量视觉误导；无标准边界或城市范围不明时不生成地图。
- 验证：`node scripts/validate-resources.mjs` 返回广东 21/21/42、浙江 11/11/22 匹配，资源子仓库 `git diff --check` 通过；`cd web && npm run build` 通过；`cd web && node --experimental-strip-types --test server/lib/htmlReport.test.ts`（6 项）通过。Pi 的 Skill 展开和认证探测通过，但外部模型请求最终 `Connection error`，真实报告仍待模型网络恢复。
- 后续扩展路线：原远端推送待办已由 092 的主仓库内置方式替代，后续图表规范随主仓库维护。继续完成边界来源许可复核；按 registry/manifest 校验格式增加其他省份或全国资源；将跨城市查询提供的同口径总量接入后再稳定生成“其他”汇总。
