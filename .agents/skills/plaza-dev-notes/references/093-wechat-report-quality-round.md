# 093 · wechat-report 质量轮：实测页高、结论先行、图表自动选型与纯图预览

**状态**：已实现（2026-11-03）。以山东智能制造既有真实工件（40,507 条，未重新查库）离线重跑全链通过：大纲/渲染/两阶段验收/文章/核查表/交付包；wechat-integration 15 项与 talent-data 全套测试通过；关键页（核心发现、大数字卡、原截字页、附录）目检无裁切。在线新会话的端到端行为未验证。

## 动机

用户审阅 091 生成的山东报告后提出四点：①网页预览在每张分页图下重复大纲文字（图内已有同样内容）；②个别行文字被拦腰截断（估算高度+overflow:hidden 裁切，即 083 缺陷5 的残留）；③"核心发现"页只有数据罗列、综合判断垫底，没有结论先行；④图表几乎全是横向条形（chart_recommender 的 FT 选型规则在 270fa72 重构时被移出主链路，只剩文档约束）。目标：在不动共享查询与交付协议的前提下，把呈现质量修到位。

## 约定细节

- **实测页高（render_report.py）**：内容页模板尾部注入 `PAGE_MEASURE_H` 脚本（`render_report.py:822`），`measure_page()`（`:849`）用无头浏览器 `--dump-dom` 读取 `.page` 真实 `scrollHeight`（overflow:hidden 下仍包含被裁内容）；主循环先按估算写页、实测超出即以"实测+12px"经 `render_screen(height=...)` 重排再截图（`:929` 附近两遍法）。封面/封底维持固定高度；`est_screen_height` 降级为初值与兜底，manifest 记录最终实测高。这是 091 后续路线 3 的落地。
- **结论先行（report_analysis.py）**：`analysis_payload()`（`:328`）对 overview 返回 `(事实段落, 结论框, None)`——executive.synthesis 不再拼成段末"综合分析"，而是写入 `screen['conclusion']`（`apply_analysis` `:361`），渲染为页面顶部橙色左边框"核心结论"框（render_report.py `:792`，置于全部正文之前）。`verify_analysis_outline`（`:396`）与 `bound_report.verify_outline:177` 同步校验：结论框文本含数字即失败（数字只允许出现在绑定 finding 的段落里）。大纲结构变为总-分：结论→事实分述。
- **图表自动选型**：`bound_report.project` 新增 `composition` 投影（`:90`）——构成类字段排序取前 N 后交 `chart_recommender.recommend_composition` 选 kind（>85% bignum / ≤4 pie / 5-7 donut / >7 排序 hbar），kind 是绑定数据的纯函数，校验重算必然一致；另加 `name_pct`（`:86`）供 vbar 显示百分比。`gen_outline.py:69` 的 `composition()` 辅助用于招聘类型/学历/经验/岗位方向/职教池方向；薪酬分布改 `vbar`（`gen_outline.py:107`）。城市/关键词保持排序 hbar，交叉保持 table/heatmap。`verify_data.py:40` 数据阶段用 `check_chart_choice` 复核违规组合，作为独立验收项"图表选型（FT 规则）"。
- **纯图预览（pack_delivery.py:26）**：公开 site 只保留 H1 标题+提示行+分页图片，不再重复段落/总结文字；文字版仍随 ZIP 的 article/article.md 交付（公众号推送需要），公开 ZIP 结构不变。

山东复跑效果：图表形态从 5×hbar+table 变为 hbar×3+bignum（社招 98.61%）+vbar+table 共 4 种（gallery"每报告 ≥4 种"达成）；核心发现页结论框在最前；原截字的第 8 页（职教）与附录目检完整；页高序列 1600/1512/2076/1591/2194/2076/2229/2126/1822/1587/1868。

## 成本与取舍

- 每页多一次 Chrome dump-dom（约 +0.5-1s/页，11 页全链约 10s），换取裁切可测量；否决"估算再加安全边距"——不可证明无截字。
- 结论框复用 insight 样式仅换边框色，不新增 CSS 组件；否决新增 summary 屏类型——保持 outline/3 协议不动，conclusion 是普通屏字段。
- composition 的 kind 由数据决定，牺牲单份报告的形态自由换取跨报告一致与可校验；手工指定构成类 kind 的旧路径不再存在（排名/交叉类仍手工）。
- 网页预览信息量下降（无文字版在线阅读）；取舍依据是分页图本身即完整交付物，文字重复反而制造不同步风险。

## 后续路线

1. 学历/经验在山东样本分别 9/8 类 → 规则判 hbar；若希望更常见 donut，可在 composition 内做"次要类合并成'其他'"（分母口径需同步披露），本期未做。
2. scatter（方向量价气泡）、range_dot、sankey 等仍未进自动选型；地图 choropleth 需省级 GeoJSON（内置仅广东/浙江），接入时优先复用 chart-visualization 技能的边界资源。
3. 在线新会话全链（真实模型主动写分析→新管线渲染→平台交付）待用户跑一次后回填；旧会话工作副本需同步 scripts/references 才能享受本轮修复。
