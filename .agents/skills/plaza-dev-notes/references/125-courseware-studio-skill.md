# 125 · courseware-studio：智能课件生成技能（课证对齐、逐页出处、安全确认）

**状态**：已实现（构建链 12 项单测、python-pptx 回读、真实 Pi 两轮 E2E 通过；PPTX 在教师机 Office/WPS 的打开效果待用户验收）。

## 动机

T08 面向任课教师的课件智能体：与讯飞智文/Gamma 的排版速度路线差异化，定位**课证对齐 + 证据可查**。硬性业务规则：课件内容只来自教师允许的材料（禁止模型记忆补课程事实）、每页事实性内容标出处、实训安全内容未经教师确认不得定稿、素材只用授权来源。

## 约定细节

### 技能与接入点

- 技能目录 `.agents/skills/courseware-studio/`：SKILL.md、docs/index.md、agents/openai.yaml、references/{spec-schema,evidence-rules,delivery}.md、scripts/{spec_model,build_pptx,build_preview,register_delivery,material_tools}.py、tests/test_build.py + examples/valid-spec.json。
- 后端注册：`web/server/lib/skills.ts:223` SKILL_PROMPTS['courseware-studio'] + `:244` INSTALLED_SKILLS。无伴生挂载（不依赖 report-rendering，预览为技能自带渲染）。
- 前端：`web/src/data/skills.ts` SKILLS 条目（teaching 类）、`web/src/data/useTaskConfigs.ts` 表单（含教学材料必传 + 图片素材选传）、ExperiencePage DEMOS。
- 共享通道小改：`web/server/lib/delivery.ts:196` MIME 表补 `.pptx`/`.md`；`web/server/index.ts:86` UPLOAD_EXT_WHITELIST 与 `web/src/composables/useUpload.ts:18` ALLOWED_EXTS 扩展 png/jpg/jpeg/webp（6MB 上限不变）。

### courseware-spec/1 契约（`scripts/spec_model.py` 为校验权威）

- spec 是课件唯一事实源；PPTX 与网页预览同源渲染；附录页（材料与逐页出处总表/版权授权/教师确认与资源入库）由构建器从 spec 派生，模型不手写。
- 机器校验位：事实性页型（objectives/intro/concept/diagram/procedure/safety-warning/quiz/rubric/summary）sources 必填；知识点要么挂 standardId 要么 extension:true；safety-warning 页必须同时有 callout(warn)+safety.items+pendingConfirmations(safety-order)；`meta.final=true` 要求每条待确认项都有 confirmations（decision=confirmed）——**定稿门是代码强制的**。
- 交付走 088 通道：web[]=output/site（自包含单页预览，CSP 沙箱友好），files[]=courseware.pptx + courseware-archive.md；`register_delivery.py` 原子替换 delivery.json（0640、sha256、越界/符号链接拒绝）。
- 两阶段确认复用 095 决策卡：首轮交付校订稿（页面带「校订稿·待教师确认」标记）→ 正文逐条列安全步骤 → plaza-question confirm → 确认后补 confirmations+final 重建定稿。

### PPTX 生成技术决策（本记录的核心新决策）

**采用 stdlib OOXML 写入器**（zipfile + 字符串 XML 模板），不用 python-pptx：

- 动机：沙箱（plaza-sandbox，系统 Python 3.12）无 python-pptx/lxml；沿用 079「零新增系统组件」原则。产物为 ECMA-376 最小集（1 母版 + 2 版式 + 主题 + slides），形状/文本框/表格/图片全部原生可编辑。
- 否决方案：pip 安装 python-pptx（需 root 装系统 + 引入 lxml C 扩展，破坏低权沙箱零依赖约定）；vendor python-pptx+lxml wheel 进技能目录（仓库带二进制 blob，丑且脆）。
- 验证方式：单测解包校验（全部 XML 良构 + rels 图闭合 + content-types 覆盖）+ 开发侧 `pip install --user python-pptx` 回读断言（仅测试，非运行时依赖）。本机无 PowerPoint/LibreOffice，无法离线渲染截图，最终视觉验收在教师机做（未完待验）。
- 已知边界：v1 无备注页（notesSlide/notesMaster），出处由页脚标注 + 预览侧栏 + 附录页承载；表格无 tableStyles.xml，用显式单元格填充与边框控制样式。

### 工作区布局

`courseware/spec.json`（内部）、`courseware.pptx`、`courseware-archive.md`（模型手写：版权/待确认/资源清单）、`output/site/{index.html,assets/}`、`material-images/`（教材图提取，内部）。公开面仅 output/site 与两个交付文件。

## 成本与取舍

- stdlib 写 OOXML 换来零依赖与确定性，代价是版式能力受投入约束（单栏堆叠 + 两栏 + 表格 + 图，自适应缩字号两趟测量）；复杂母版/动画不支持，对课件场景够用。
- 附录页由构建器派生而非模型书写：多一层约定，换来清单与 spec 永不漂移。
- 决策卡一轮一问：安全顺序与缺口取舍合并为一张 confirm 卡（确认项逐条在正文列明），避免多轮拉扯。

## 后续扩展路线

- WeKnora 检索接入（凭据未配置）：材料范围可扩「知识库文档」，走 107 记录的共享检索工具方案。
- PPTX 备注页（speaker notes）：notesMaster/notesSlide 组合，教师讲稿放 notes 字段。
- 平台课程资源库真入库：resources[] 目前交付清单，待资源库系统出现后接登记 API。
- 模板主题扩展（更多 style）与课标条目库（T05 结构化条目直连）。

## 验证记录

- `python3 -m unittest discover -s tests`：12 项通过（spec 校验、pptx 结构/rels 闭合/content-types、预览断言）。
- python-pptx（--user 安装）回读：14 页（11 教学 + 3 附录），标题/文本齐全。
- material_tools 对真实 PDF（docs/project-overview/project-overview.pdf）：text 逐页 ok、images 提取 7 张达标图。
- 真实 Pi E2E（youcai）：上传教材/指导书/设备图 → 首轮校订稿 + confirm 决策卡 + webLinks/downloads → 答复确认 → 定稿重建交付（详见运行 traces）。
