// Historical trace decoding only. Never inject these retired instructions into a new turn.
import { skillDir } from './skills.ts'

export const LEGACY_INDUSTRY_CHART_RULE = `产教报告绘制统计图时，读取 ${skillDir('chart-visualization')}/SKILL.md，` +
  '先完成本轮 report.py build，从它打印的 output/report-…/report.json 生成绘图数据。分布使用指标的 breakdown.groups，图注写指标编号、范围和分母。' +
  `实际运行 python3 ${skillDir('chart-visualization')}/scripts/figure.py render。网页在对应段落留 <!-- chart:图稿ID -->，运行 python3 ${skillDir('industry-education-report')}/scripts/embed_chart.py <规格.json> <图稿目录> <网页路径>，由它调用共享 verify 并嵌入完整图块。修订标题、图注或数字也改规格并重绘。仅有定性证据时使用原文或表格。`

export const LEGACY_INDUSTRY_RENDER_RULE = `产教报告先完成本轮 report.py build。统计图从其输出的 report.json 取已核指标与 breakdown.groups，` +
  `读取 ${skillDir('chart-visualization')}/SKILL.md，实际运行共享 figure.py render，保留单位、范围、分母和来源。` +
  `网页版交给 ${skillDir('report-rendering')}/SKILL.md，按内容选择组件、表格和主题。` +
  `由渲染技能把现有正文与 JSON 内部整理，使用 scripts/render.py 生成网页并复验、嵌入完整图稿。默认 paper，遵循用户指定风格。` +
  '保留本轮四份下载，追加网页版声明，核对实际图文与窄屏效果。'

// Kept only to strip wrappers from existing conversations.
export const LEGACY_INDUSTRY_DECISION_SUFFIX = '\n\n（本轮先按读者的决定核对证据。已粘贴的原文即为材料，按 user: 引用原句，不能要求重传或臆造附件、时段、容量。先检验一个必要条件是否已被证据否决：若唯一可用场地排满且无替代，足以判断本期不能开班；其余设备或师资未知不触发提问，直接成稿。核心缺证时说清已知、缺口及影响，必须提供单选的三个选项“补充材料”“扩大范围”“按现有证据继续”。本轮停在提问，不运行 build。补材料或扩围后重新判断；仅凭“请生成”不能代选继续。单项决定用 decision 三节简报，明确要全景观察时用 observation。关键缺口仍在且用户选择继续，记录其原话。可交付时依技能契约运行 report.py build，保留四份下载。）'

export const LEGACY_INDUSTRY_PRESENTATION_HANDOFF = `需要排版成品时，将本轮 build 的正文和 report.json 交给 ${skillDir('report-rendering')}/SKILL.md，按该技能完成呈现与交付。`
