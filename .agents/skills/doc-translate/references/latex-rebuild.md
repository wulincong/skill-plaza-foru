# XeLaTeX 重排指南（doc-translate）

**环境事实**（2026-10-20 实测，TeX Live 2023 / Debian）：

- `xelatex`、`xeCJK.sty`、`ctex.sty`、`geometry.sty`、`fontspec.sty`、`longtable.sty`、`booktabs.sty`、`hyperref.sty` 均已安装，在系统 PATH 上（沙箱用户可达）。
- 可用中文字体：`WenQuanYi Zen Hei`（文泉驿正黑，推荐正文）、`AR PL UKai CN`（楷体，适合标题/引文）。用 `fc-list :lang=zh` 可复核。
- 冒烟验证：A4 单栏 + letter 双栏 + xeCJK 中文断行均编译通过。

## 纸张与分栏选项映射（detect-layout.mjs 输出 → LaTeX）

| 探测结果 | documentclass / geometry |
|---|---|
| `paper.label` = A4 | `[a4paper]` |
| `paper.label` = letter | `[letterpaper]` |
| `paper.label` = legal | `[legalpaper]` |
| `custom WxHpt` | `\usepackage[paperwidth=Wpt, paperheight=Hpt]{geometry}`（注意用标准纸名优先；custom 尺寸与标准差 < 5pt 时就近取标准纸） |
| `columns` = 2 | documentclass 加 `twocolumn` 选项 |

⚠️ 不要用 `\usepackage[paperwidth=612pt,paperheight=792pt]{geometry}` 表达 letter——实测会引入约 2pt 偏差；标准纸一律用纸名选项。

## 模板骨架（可直接抄改）

```latex
\documentclass[11pt, a4paper]{article}   % 双栏时加 twocolumn；纸张按映射表
\usepackage{geometry}
\usepackage{graphicx}                     % 保留原图，含原 PDF 区域裁切引用
\usepackage{xeCJK}                        % 目标语言含中文时必需；纯西文目标可省略
\setCJKmainfont{WenQuanYi Zen Hei}
\usepackage{longtable}                    % 有跨页表格时
\usepackage{booktabs}
\usepackage[hidelinks,unicode]{hyperref}  % 有链接/书签时
\begin{document}
\title{<原文标题的译文>}
\author{<原文作者/机构，若已知；否则省略>}
\date{<原文日期或空>}
\maketitle
\section{...}
...
\end{document}
```

- 中→英方向（目标语言无中文）：去掉 `xeCJK` 两行即可，西文用默认 Latin Modern。
- 双栏文档中需要跨栏的标题/摘要：`\twocolumn[\begin{@twocolumnfalse} ... \end{@twocolumnfalse}]` 或直接接受 `\maketitle` 的跨栏行为。
- 原图引用、图注翻译和矢量图裁切见 [figure-preservation.md](figure-preservation.md)；图片按栏宽缩放，只有跨栏图使用 `figure*`。

## 特殊字符转义表（写 .tex 前逐项核对）

| 原文字符 | 写法 |
|---|---|
| `#` `$` `%` `&` `_` `{` `}` | `\#` `\$` `\%` `\&` `\_` `\{` `\}` |
| `~` | `\textasciitilde{}` |
| `^` | `\textasciicircum{}` |
| `\` | `\textbackslash{}` |
| 中文引号「」『』《》 | xeCJK 下直接写原文即可 |

正文中的 URL 用 `\url{...}`（免转义）；数学式里的记号进数学模式，不转义。

## 编译与校验

```bash
cd <会话 workspace 目录>
xelatex -interaction=nonstopmode -halt-on-error translation.tex
xelatex -interaction=nonstopmode -halt-on-error translation.tex   # 第二遍：目录/引用稳定
pdfinfo translation.pdf          # Pages ≥ 1 才算成功
```

`.aux` / `.log` / `.out` 等中间文件留在 workspace 即可，无需清理。

## 排错（按命中频率）

1. **缺字形黑框**：Unicode 上下标（如 ₀₂）、生僻符号在字体里没有字形。改用数学模式 `x_{2}`；中文目标换 `AR PL UKai CN` 试验。
2. **Undefined control sequence / Missing $**：多为转义遗漏或数学式没进 `$...$`。读 `translation.log` 中第一个 `Error` 行，行号对应 `translation.tex`。
3. **表格超栏宽**：双栏下窄表格溢出。改 `tabular*` 加 `\small`，或跨栏浮动 `table*`。
4. **中文不断行或报 fontspec 错**：确认 `\usepackage{xeCJK}` 在 `fontspec` 相关包之后、且字体名与 `fc-list` 输出一致。
5. **hyperref 中文书签乱码**：确保 `unicode` 选项已加。
