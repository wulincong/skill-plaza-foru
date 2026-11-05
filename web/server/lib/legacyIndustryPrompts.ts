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
