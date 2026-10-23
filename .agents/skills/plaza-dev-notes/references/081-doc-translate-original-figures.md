# 081 · PDF 翻译默认保留原图

**状态**：已实现（2026-10-23：位图提取、原 PDF 矢量区域引用、图注翻译及真实 Pi 产物通过；4 项素材回归和前端构建通过。旋转原页、复杂透明蒙版/组合图与长文档仍待更多样本验证）。

## 动机

079 首版用图注占位而不保留图片，无法满足课件、论文中的图表阅读需求。用户本轮要求保留原图；目标是原图外观和图注对应，不做 OCR、图内文字翻译或精确原页码复刻。

## 约定细节

### 素材提取与清单

- `.agents/skills/doc-translate/scripts/preserve-figures.mjs:41` 提供 `extract <PDF> [--out-dir figures] [--first N --last N]`：只依赖 Node、poppler 的 `pdfinfo/pdftohtml/pdftoppm`，不引入 Python PDF 库。`pdftohtml -xml -zoom 1 -noroundcoord` 提取位图及坐标，`pdfinfo` 补精确页宽高；不加 `-nodrm`，加密/提取失败直接报错。
- 工作目录产物为 `figures/source.pdf`（原文副本）、稳定命名的 `image-pNNN-NN.png/jpg` 和 `manifest.json`。原始输入文件名不会进入 TeX 素材路径；带空格和中文的上传名已实测。
- manifest schema（`version:1`）：`sourcePdf` 为 cwd 相对路径，`sourceSha256` 绑定原文；`range:{first,last}`；`pages:[{page,widthPt,heightPt,rotation,imageCount,captions}]`；`images:[{id,page,file,bboxPt,latex,nearbyText}]`；`regions` 初始为空，`notes` 提醒位图清单不能代表全部图形。`bboxPt=[x,y,width,height]` 单位 pt，页面左上角为原点；图注候选含文本及位置。
- `images` 每次图像出现保留单独条目，避免静默丢掉重复图/页眉图片。提取在临时子目录完成，之后只清理脚本自身临时文件；重复提取重建当前清单，不沿用旧 PDF 的裁切框。

### 矢量图与组合图

- 同脚本 `:103` 提供 `region <manifest.json> --page N --box x,y,width,height`；检查有限数值、页界和源文件 hash，生成 200 DPI 预览 PNG 供模型检查，越界/源已变化时失败。
- 正常朝向页面生成 `page=N,trim={...bp},clip` 的原 PDF 引用，`method:pdf-clip` 保留线条、颜色与原有图内文字。旋转页面使用预览 PNG，`method:raster-crop`（该回落代码已实现，真实旋转页质量仍待验证）。不同裁切框用不同 ID，模型可迭代调整；清单可能包含未采用的早期裁切，最终以 `.tex` 实际引用为准。
- 返回区域对象包含 `id/page/bboxPt/preview/method/latex`，并写入 manifest.regions。原图和区域的 `latex` 默认限 `\linewidth`、0.7 文本高度并保持宽高比；正常页面的 PNG 仅用于预览。

### 技能和用户入口

- `doc-translate/SKILL.md:17` 将默认行为改为保留原图；`:44` 在重排前调用提取脚本，明确无位图不能推断无矢量图；`:68` 要求对照原文图注/各页与素材清单，渲染最终含图页核对可见范围。原图按对应章节插入、图注翻译、图号保持；图内文字不改，不用“【图：…】”替代能保留的图片。
- `references/figure-preservation.md` 说明清单、区域框选择和 `graphicx` 插入；`references/latex-rebuild.md` 模板加载 `graphicx`，跨栏大图用 `figure*`。新 Pi 会话读更新后的技能文件，无服务端新产物协议。
- `web/server/lib/skills.ts:181` 回落约束与技能一致；`web/src/data/skills.ts:145`、`useTaskConfigs.ts:81` 与 README 同步用户说明。最终交付仍是 079 的独立 `translation.pdf`；下载不需要携带原始素材目录。

## 成本与取舍

- 否决仅用 `pdfimages` 判断是否有图：不能保留 PDF 线条/文字组成的矢量图。位图坐标和图注线索采用 pdftohtml，矢量/多元素区域由原页预览确认后裁切，避免声称自动识别了全部逻辑图。
- 否决所有图统一截图：损失位图原始像素与矢量缩放清晰度。正常页面优先原素材/原 PDF；旋转页才回落为区域位图。
- 不引入 PyMuPDF/BabelDOC 新运行环境，复用沙箱现有系统工具；代价是复杂图形边界需要模型结合预览确认，而非专门版面模型自动识别。
- 原 PDF 裁切属于显示范围裁切，内容流可能仍包含框外原文，`pdftotext` 有时会抽取不可见文字；验收以最终 PDF 渲染图为准，不能用纯文本提取判断裁切外观。这是直接引用方案的已知取舍。
- 保存原文副本和预览占用会话磁盘，最终 PDF 大小仍受服务端 64MB 工件上限约束；原图越多越需关注体积。图内文字、OCR 与逐像素版式复刻不在本次范围内。

## 验证

- `node --test web/server/lib/docFigures.test.mjs`：4 过 0 挂，覆盖位图/坐标/精确纸张与矢量图注候选、位图+裁切引用可独立编译/渲染、重复运行/页码范围/越界/源变化、含中文空格的输入路径。测试生成自己的 PDF，不依赖用户历史文件；缺系统依赖时明确 skip。
- `npm run build`、技能 `quick_validate.py`、脚本 `node --check` 和 `git diff --check` 通过。
- 真实 Pi 运行 `20261023-155342-b9eb`：上传带一张彩色位图和一张矢量流程图的英文 A4 PDF，仅要求翻译并保留图；生成 2 页中文译文，图注对应原图号，位图嵌入且矢量用原 PDF 裁切。低权沙箱中提取、裁切预览、两遍 XeLaTeX 编译与 PDF 下载完成。核对最终两页渲染：彩色柱状图/边框和流程箭头/标签完整，无文字占位；从译文重新提取位图，与原素材逐像素一致。图形位置/复杂页能力不从该样本外推。

## 后续扩展路线

- 增加旋转页面、透明图层、裁切蒙版、多子图、混合单双栏和仅有矢量无显式图注的真实样本。
- 如需自动确定逻辑图形边界，再评估专门的版面解析器；不把当前图注候选当作完整图形识别。
- 图内文字翻译另建 OCR/重绘流程，须单独定义质量验收；维持本次原图保留与该能力的边界。
