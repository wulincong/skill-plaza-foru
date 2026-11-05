# 主题系统

基础组件在 assets/report.css，主题在 assets/themes/。交付复制所选主题为 theme.css，页面使用同一语义结构。

| 主题 | 视觉 | 场景 |
| --- | --- | --- |
| paper 纸感简报 | 暖白 #f7f4ee、纸白 #fffdf9、深绿 #0d6e63、琥珀 #b4530a；窄圆角、左侧重点线、1000px 宽 | 管理决策、区域分析；默认 |
| minimal 极简白 | 白底、灰阶、蓝色 #0064d9；16px 圆角、轻边框、1040px 宽 | 工作复盘、研究摘要、项目说明 |

`--theme minimal` 切换主题，同一页面模型复用内容。品牌定制在工作区复制主题，用 `--theme-css 品牌.css` 替换。先调整背景、文字与强调色，再调整字体、宽度、圆角和间距。主题可覆盖组件布局，保持语义标签和完整图块。

核心变量为 `--report-bg, --report-surface, --report-ink, --report-muted, --report-line, --report-accent, --report-accent-soft, --report-attention, --report-font, --report-width, --report-radius, --report-section-gap, --report-title-size, --report-columns`。改主题后用长文、长数字、缺测、宽表和图稿检查。图内颜色按数据含义设计，需要调整时改图稿规格并重绘。

两个组件陈列使用同样内容。新增主题先在工作副本验证，再按需求纳入共享库。
