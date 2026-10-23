# 保留原图并翻译图注

使用系统已有的 `pdftohtml`、`pdfinfo`、`pdftoppm` 和 XeLaTeX `graphicx`，无需新 Python 库。图像文件与中间产物留在会话 workspace；最终 PDF 已嵌入图片，可独立下载。

## 位图提取与清单

```bash
node "<本技能绝对目录>/scripts/preserve-figures.mjs" extract "uploads/source.pdf"
# 可选：--out-dir figures-part-1 --first 1 --last 20
```

输出 `figures/manifest.json` 与安全命名的图片文件。`images` 每项包含：

- `id`、`page`、`file`：原图身份、原文页码与当前工作目录内的图片路径。
- `bboxPt: [x,y,width,height]`：单位 pt，页面左上角为原点。
- `nearbyText`：图片下方原文，用于识别、翻译图注和关联正文。
- `latex`：可直接放进 figure 环境的原图引用，限制栏宽/高度并保持宽高比。

`pages` 给出精确页宽高、旋转角度、位图数与图注候选（含坐标）。`sourcePdf` 是保留在素材目录的原文副本，不要修改。清单中没有位图的页面也可能有矢量图；有多张位图拼成一张逻辑图时，使用下文区域引用保留完整外观。

## 矢量图和组合图

先查看原页，结合图注坐标确定**仅覆盖图形**的矩形；不要框入正文或原文图注：

```bash
pdftoppm -f 2 -l 2 -singlefile -scale-to 1400 -png figures/source.pdf figures/page-2
node "<本技能绝对目录>/scripts/preserve-figures.mjs" region figures/manifest.json --page 2 --box 80,200,400,180
```

示例框仅说明参数形状，实际坐标须按原图确认；预览像素坐标需按页面 pt 宽高换算。脚本生成区域预览 PNG，返回 `latex` 并把结果写入清单 `regions`；查看预览，边框、箭头或标签被截断时调整框后重新执行。

正常朝向页面采用 `page=N,trim={...bp},clip` 直接裁切引用原 PDF，保留矢量线条和原有图内文字。带旋转的原页回落为 200 DPI 的区域图片（`method: raster-crop`），其余页面是 `method: pdf-clip`。不要把区域预览截图当作正常页面的首选素材。

PDF 裁切控制可见范围，内容流仍可能保留框外原文；`pdftotext` 有时会提取这些不可见文字。用最终 PDF 的渲染图确认是否混入正文/原图注，不要仅凭纯文本提取结果判断裁切失败或漏译。

## 插入译文

```latex
\usepackage{graphicx}
% 中文目标可加：\renewcommand{\figurename}{图}
...
\begin{figure}[htbp]
\centering
% 放入 images 或 regions 中的 latex 字段
\includegraphics[width=\linewidth,height=0.7\textheight,keepaspectratio]{figures/image-p001-01.png}
\caption{分拣实验结果。}
\end{figure}
```

在对应章节/段落附近插入，保留原文图号；只翻译图注，图内文字和颜色不改。双栏正文的跨栏大图用 `figure*`；多子图应连同子图标签一起保留。图片无法原样提取时先试区域裁切，确实失败才报告缺失原因，不用“【图：…】”冒充已保留的图片。
