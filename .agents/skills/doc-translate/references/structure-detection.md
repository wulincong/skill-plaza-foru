# 宏结构探测指南（doc-translate）

`scripts/detect-layout.mjs` 把译文重排需要的宏观参数一次测出，避免把整份 PDF 读进上下文。

## 依赖与用法

- 依赖：poppler（`pdfinfo`、`pdftotext`），系统 PATH 上，沙箱用户可达；node（沙箱 PATH 含 /opt/plaza-runtime/bin）。
- 用法：`node "<本技能绝对目录>/scripts/detect-layout.mjs" "uploads/<文件名>.pdf"`（当前 cwd 是会话 workspace，技能路径取加载说明）。
- 输出：单行 JSON；失败时 stderr 给原因、退出码非 0（文件不存在 / poppler 报错——后者常见于加密 PDF）。

## 输出字段

| 字段 | 含义 | 用途 |
|---|---|---|
| `pages` | 总页数 | 翻译范围核对、分批提取 |
| `paper.label` | 标准纸名（A4/letter/legal…）或 `custom WxHpt` | geometry 选项映射 |
| `paper.widthPt/heightPt` | 首页尺寸（pt） | custom 纸映射 |
| `columns` | 1 或 2（多数表决） | documentclass `twocolumn` |
| `twoColumnPages` / `sampledPages` | 判为双栏的页数 / 参与表决的页数 | 置信度：`2/2` 与 `18/20` 可信度不同 |
| `textChars` / `charsPerPage` | 去空白字符数 / 每页均值 | 扫描件线索 |
| `likelyScanned` | 每页均值 < 100 字符 | 为 true 时按扫描件处理 |

## 判别依据（为什么这样判）

- **分栏**：`pdftotext -bbox-layout` 给每个文本行的 xMin/xMax。按**行中心点**相对页宽中线归类：双栏页的行聚在中线两侧、居中行很少（标题/页码除外）；单栏满宽行的中心恰在中线附近。
  - 不用行端点判别的原因：LaTeX 默认 `columnsep` 约 10pt，左栏行的右端点可以越过"中线-14pt"这类阈值，端点法会漏（实测踩过）。
  - 只统计文本行 ≥ 8 的页（跳过封面、插图页），多数表决；阈值：两侧各 ≥ 4 行且居中行 ≤ 20%。
- **扫描件**：图片型 PDF 的文本层为空或极稀疏，每页均字符数是直接证据。

## 局限与校正

- **跨栏大图/宽表格**会让单双栏混排页判错；`sampledPages` 很小（≤ 3）或结果存疑时，人工抽查 `pdftotext -layout -f 1 -l 3 <pdf> -` 的视觉对齐再定。
- **两栏混单栏**（如跨栏摘要 + 双栏正文）会正确判 2。
- 末页内容只占左栏（LaTeX 双栏先填满左栏）不影响判别：判别看的是多数页，且右栏有内容的页才计双栏。
- `likelyScanned` 是启发式：为 true 时先用 `pdftotext -layout -f 1 -l 2` 人工确认确无文本层，再向用户说明不支持。
