---
name: doc-translate
description: 文档翻译（PDF）：把用户上传的 PDF 文档全文翻译为目标语言，用 XeLaTeX 重排为对齐原文宏观结构（纸张尺寸、单双栏、标题层级）的 PDF 译文；不追求逐像素版式复刻，扫描件与加密 PDF 不支持并如实告知；产物固定写入 workspace/translation.pdf。
metadata:
  short-description: PDF 文档翻译与 XeLaTeX 重排
---

# 文档翻译（PDF → PDF）

把用户上传的 PDF 文档全文翻译成目标语言，重新排版生成一份宏观结构与原文对齐的 PDF 译文。

## 边界（先读）

- **只对齐宏观结构**：纸张尺寸、单栏/双栏、标题层级、段落边界、表格与列表的存在性。不追求逐像素复刻原版式（字体、精确边距、页眉页脚样式、图文绕排不强求）。
- **扫描件不支持**：图片型 PDF 无文本层时，如实告知用户当前不支持 OCR 翻译并终止，不猜测原文内容。
- **加密 / 权限受限 PDF**：提取工具报错时如实报告原因，不绕过。
- 上传附件单文件上限 6MB，超出属于渠道限制。

## 工作流程

### 一、输入确认

附件说明会给出 `uploads/` 下的相对路径。目标语言未明确时先询问；用户给了翻译范围（全文或页码区间）时按范围执行，区间信息用 `pdfinfo` 的 `Pages` 核对。

当前工作目录已经是会话 workspace。下文 `workspace/translation.pdf` 指当前目录的 `./translation.pdf`，不要再创建一层 `workspace/` 子目录。技能脚本与 references 的相对路径以本技能目录为基准，调用时使用技能加载说明中的绝对目录。

### 二、宏结构探测

```bash
node "<本技能绝对目录>/scripts/detect-layout.mjs" "uploads/<文件名>.pdf"
```

输出单行 JSON：`pages`（页数）、`paper.label`（A4 / letter / custom 宽x高pt）、`columns`（1 或 2）、`likelyScanned`（扫描件线索）。字段含义、判别依据与校正方法见 `references/structure-detection.md`。

### 三、文本提取

- `pdftotext -layout`（保留视觉对齐）提取正文；长文档按 10–20 页一批（`-f` / `-l` 指定区间），边提取边翻译，不要一次性把全文读进上下文。
- 标题层级判定：孤立短行、前后空行、编号模式（`1.`、`1.1`、`Chapter N`、`第N章`、全大写居中行）。
- 表格：`-layout` 下连续对齐的列 → 译文用 `tabular` 重排；合并单元格无法精确复原时在表注说明。
- 图片：无法重绘，在原位置保留 `【图：<题注译文>】` 占位并翻译题注。

### 四、翻译

- 按章节分块，段落与原文一一对应，不合并、不拆散段落。
- 术语表先行：首次出现的人名、机构、产品、缩写确定译法，全文保持一致；无通行译法的专有名词、型号、代码标识符保留原文并在首次出现时括注原文。
- 不增删内容：图注、脚注、参考文献条目都属于翻译范围；原文的列表、枚举保持条目数一致。
- 代码块原样保留（`verbatim` 环境）；数学式用 `$...$` / `\[...\]` 重写。

### 五、XeLaTeX 重排

模板骨架、纸张/单双栏选项映射、LaTeX 特殊字符转义表、编译排错见 `references/latex-rebuild.md`。要点：

- `\documentclass[11pt, <纸张选项>, <twocolumn 若原文双栏>]{article}` + `xeCJK`（目标语言含中文时）。
- 在当前会话 workspace 目录内编译：`xelatex -interaction=nonstopmode -halt-on-error translation.tex`，跑两遍（目录/交叉引用稳定）。
- 产物必须是 **`workspace/translation.pdf`**（服务端按此固定路径捕获交付，文件名不改）。

### 六、校验与交付

- `pdfinfo translation.pdf` 确认 `Pages ≥ 1`；失败时读 `translation.log` 尾部定位第一个 `Error`（常见坑见 reference），修复后重编译。
- 交付回复只写简短完成说明：目标语言、译文章节/页数、宏观结构对齐情况（纸张、单双栏）、未覆盖项（如图片占位）。不要把译文全文贴进对话回复。
- 编译确实无法修复时如实说明失败原因，明确译文未生成，不得伪造链接或用文本冒充 PDF。
