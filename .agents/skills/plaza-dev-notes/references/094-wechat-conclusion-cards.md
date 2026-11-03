# 094 · wechat-report：综合判断拆分为结论卡（wechat-analysis/2）

**状态**：已实现（2026-11-03）。山东真实工件离线重跑全链通过（两阶段验收 5 项 PASS），wechat-integration 15 项测试通过（夹具已升 v2）；核心发现页目检确认"总判断框 + 4 张编号结论卡 + 绑定事实段"结构完整无裁切。在线新会话行为未验证。

## 动机

093 后用户仍反馈"核心结论讲得非常不到位"：综合判断是一段限制条件堆砌（并不必然/不能解释成/尚不足以），没有可执行的结论。根因有三：校验器禁止综合判断出现数字（防伪造），导致结论被迫空泛；规范只约束"≥40字、跨3维度"，不约束结论句式；呈现上单段长文。同轮用户要求排查"服务器上的画图项目"——本机、真云主机（root@115.231.218.150，注意 `test.deckmanager.net` 的 ssh config 走 6001 是本机回环，须 `-p 22 root@IP` 直连才是云主机）、frp 6002 的 vision123（密钥不通）全部排查：无可调用的画图服务/项目，matplotlib 仅是 ML 项目依赖；该结论已反馈用户。

## 约定细节

- **协议 wechat-analysis/2**（`report_analysis.py:13`）：executive 新增必填 `conclusions` 数组，2-4 张卡；每卡 title 4-16 字动作短语、text 20-200 字决策要点（均走 `_narrative`：无占位/无未绑定数字/无动态断言）、findingIds 1-3 条且存在；**并集必须等于 executive.findingIds**（每条综合事实都要被某张卡认领，卡不能只讲空话）。旧 /1 稿给明确报错提示补 conclusions 后重写。
- **渲染**（`render_report.py`）：核心发现页结构固定为 总判断框(conclusion) → 结论卡(`screen['cards']`，复用 `.sumcard` 编号卡样式，`render_report.py:800` 附近) → 绑定事实段落。卡片与总判断均为纯叙述；支撑数字只出现在其后的 finding 段落（绑定校验不变）。`est_screen_height` 每卡 +210。
- **校验同步**：`analysis_payload` 返回四元组 (paragraphs, conclusion, cards, summary)；`apply_analysis`/`verify_analysis_outline`（`report_analysis.py:364`/`:396` 附近）逐项比对 cards；`bound_report.verify_outline:175` 对 conclusion 与 cards 做"去实体标签后不得含数字"防护（ROS2 类标签豁免与正文一致）。
- **写作规范**：`references/research-analysis.md` 协议示例升 /2 并新增"结论先行"写法节（总判断一句话定调 + 结论卡=动作短语标题 + 判断/行动要点，边界一句话，禁止限制条件堆砌）；SKILL.md:24 同步。
- 草稿模板 `analysis_draft.json` 的 executive 增 `conclusions: []`，空模板依旧过不了校验。

山东复跑样例：4 张卡分别为"合作城市按学生条件重选 / 学历开放不等于门槛降低 / 入门薪酬按入门池口径沟通 / 入门岗位城市结构另作选择"，各认领 1 条综合事实；synthesis 重写为"三特征并不同向 + 决策含义 + 证据边界"结构。

## 成本与取舍

- 协议 breaking change：已保存的 /1 分析稿（含 benchmark raw/session）需补 conclusions 才能再生成；与 091 处理 /2→/3 大纲的先例一致。
- 结论卡禁数字（标签豁免）保留了防伪造边界；代价是卡片不能自证，必须依赖其后事实段——呈现顺序（结论在前、证据紧随）就是这个设计的补偿。
- 复用 sumcard 样式不新增组件；卡数上限 4 防止核心发现页过长。

## 后续路线

1. 在线新会话验证 youcai 能否按 /2 写出合格结论卡（规范已给句式与示例）；写不好时优先改规范示例再考虑模型侧。
2. 章节页 interpretation/action 仍是纯段落，如需同样卡片化可复用本机制（cards 字段渲染已通用）。
3. 生图服务排查结论（无）已反馈；若用户提供 vision123 访问或外部生图/画图服务，再评估接入。
