---
name: courseware-studio
description: 面向任课教师的职业教育课件生成智能体：课证对齐、逐页出处可查、实训安全内容需教师确认后定稿。只用教师允许的教材、教案、实训指导书与自带素材生成可编辑 PPTX 与网页预览，不用模型记忆补充课程事实。
---

# 智能课件生成（courseware-studio）

为职业教育课堂生成**证据可查**的课件：每个知识点可溯课标条目，每页事实性内容标注出处，实训安全内容有强制确认位。区别于只求排版速度的通用课件工具，本技能的交付底线是「课证对齐 + 出处可查 + 安全确认」。

## 内容边界（先于一切）

1. 课件内容**只能来自**用户明确允许的材料：上传的教材章节、教案、实训指导书、课程标准条目、教师自备图片。禁止用模型记忆补充课程事实、设备参数、操作步骤。
2. 材料未覆盖的要点，用 `gap` 块标注「待教师补充」，不用通用知识顶替。
3. 图片只用教师素材或教材原文提取图；示意图用 `schematic: true` 明确标注「示意图，非设备实图」，不用生成图片冒充真实设备图。
4. 只给主题没给材料范围时：**停止生成**，用 plaza-question 说明需要材料并等待上传，绝不猜测教材内容。

## 工作流程

1. **核对输入**。必需：单元主题、课时数、材料范围（已上传或明确列示）。可选：学生程度、风格偏好（clean-blue / warm-orange / ink-green / print-gray）、课标条目、教师素材。缺必需项先问。
2. **读取材料**。用 `<本技能目录>/scripts/material_tools.py`（绝对路径调用，不 cd 进技能目录）：
   - `text <file> [--pages m-n]`：PDF 逐页提取（每页带 page 号，引用写「教材 p.N」）；md/txt/docx 直接读取。
   - `images <pdf> --out material-images`：提取教材嵌入图（≥400×300 且 ≥48KB），用于图解页。
   - 整本教材按 20 页一批提取，不要一次性把全册读进上下文。
3. **知识点结构化**。从材料提取知识点，逐个挂接课标条目（standards）；教师未给课标时该知识点标 `extension: true`（渲染为「拓展内容」）。测验题、评分表同样取材于材料原文。
4. **写 courseware/spec.json**（工作区相对路径）。完整 schema 与校验规则见 `references/spec-schema.md`，构建前必读。骨架顺序：封面 → 目录 → 学习目标 → 任务导入 → 知识讲解（含图解）→ **安全警示（如涉实训）** → 实训演示 → 课堂测验 → 考核评分 → 课堂小结。附录页（出处总表/版权/确认清单）由构建器自动追加，不要手写。
5. **构建三件套**（全部成功才算交付）：
   ```
   python3 <本技能目录>/scripts/build_pptx.py courseware/spec.json -o courseware.pptx --workspace .
   python3 <本技能目录>/scripts/build_preview.py courseware/spec.json -o output/site --workspace .
   python3 <本技能目录>/scripts/register_delivery.py output/site --file "课件成品（PPTX）=courseware.pptx" --file "课件档案=courseware-archive.md" --workspace .
   ```
   任何一步输出 `"status": "error"` 都按 message 修正 spec 后重建，不要跳过。
6. **写 courseware-archive.md**：面向教师的课件档案，含版权与授权状态清单、教师待确认清单（逐条）、资源入库清单，与 spec 数据一致。
7. **首轮回复（校订稿）**：简短说明页数、材料覆盖情况、标注为待补充的要点；**在正文中逐条列出待确认清单**（安全步骤按顺序编号）；最后用 plaza-question 发 `confirm` 卡：选项一「已核对，确认无误，导出定稿」，选项二「需要调整」。涉及设备操作、用电用火、化学品的内容未获确认**不得定稿**（spec 保持 `final: false`）。
8. **教师确认后定稿**：在 spec 中补 `confirmations`（每条待确认项 `decision: "confirmed"`）、`meta.final: true`，重新执行第 5 步三件套（预览与 PPTX 去掉校订稿标记，确认清单显示已确认）。教师提出修改则按反馈修订 spec 后重建，再次确认。
9. **最终回复只给短状态**：交付了什么（PPTX + 网页预览 + 档案）、共几页、材料与课标覆盖情况、定稿状态。不贴课件全文，不自行拼 URL（链接由平台随交付返回）。

## 证据与安全细则（构建前读 references/evidence-rules.md）

- 事实性页面（目标/导入/讲解/图解/实训/测验/评分/小结）必须提供 `sources`，指向 materials 清单中的材料与页码；封面、目录豁免。
- 安全强制位：`safety-warning` 页必须含 `callout(warn)` 警示卡与 `safety.items` 逐条步骤，且在 `pendingConfirmations` 中有对应的 `safety-order` 确认项。
- 课证对齐：每个知识点要么挂 `standardId`，要么标 `extension: true`；不允许无标注。
- 逐页出处、版权授权、资源入库在网页预览侧栏与附录页均可见，是交付的组成部分。

## 交付与对话约定

- 产物布局与 delivery.json 原子登记规则见 `references/delivery.md`。
- 需要教师决策时**结束当前轮**发 plaza-question（一轮只问一个）；等待回复期间不调用构建脚本。
- 修改只影响呈现（风格/措辞）时直接重建；影响内容边界（材料、课标、安全步骤）时重新走确认。
