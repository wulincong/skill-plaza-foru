# 101 · 技能文档的原文目录与汇总方式

**状态**　已实现。

## 动机

036 的使用指南解决「如何运行和接 API」，详情页帮助读者选择技能。各技能的材料准备、示例、交付解读和专题需要能独立更新，内部开发技能也需要可检索的仓库入口。

## 约定与接入点

- `web/scripts/skill-docs.mjs:13` 扫描顶层技能与专业注册表。每个技能只从自己的 `docs/index.md` 和同级专题取文，提示词技能也可只有 docs 目录。三个原子模块已随 092 的后续迁移内置。
- `web/scripts/skill-docs.mjs:58` 解析同一份 Markdown，产出 `{ key, title, blocks, outline }`。正文片段按原顺序渲染，禁用原始 HTML。独立的 `prompt` 围栏作为文字块输出，原文中换行、缩进和尖括号都可复制。引用与命令沿用各自的 Markdown 语义。二级标题生成当前页的小节目录。
- `web/src/pages/SkillDocsPage.vue:47` 使用常驻的左侧目录展示技能和专题，下方列出当前页小节，选中项有独立状态。手机宽度使用可收起的“文档目录”，选页后收起。`web/src/router/index.ts:35` 处理 hash 路由下的小节定位。`web/src/pages/SkillDocsPage.vue:116` 为每个示例实例化项目已有的 Codebox，复制仅取该块文本。
- 网站随前端构建发布，原有的技能与专题直链、仓库索引和 `#/guide` API 指南继续使用。`web/scripts/skill-docs.mjs:90` 仅发布注册表中专业技能的文档；内部开发技能从仓库索引进入。
- `web/scripts/docs-index.mjs:5` 从相同文档集合生成仓库索引，包含内部技能。维护者执行 `npm run docs:index` 一起提交索引；`npm run docs:check` 比较当前文件内容并验证公开页链接。写作流程见 [给技能写文档](../../../../docs/writing-skill-docs.md)。

## 成本与取舍

公开页随前端构建发布，线上更新需要发布新的静态文件。运行时从文件系统提供整棵技能目录会把阅读绑定到后端，并扩大可读文件范围。将每篇正文抄入 Vue 或数据注册表又需要双份编辑。当前约定只维护 Markdown，使用已有的 Vite、Vue 与 Markdown 依赖。

早期为三个子模块设置的配套文档目录已随技能迁入主仓库，后续只维护技能内的 docs。章节位置锚点按页内次序生成，调整标题顺序可能改变小节直链，技能与专题的地址由文件名决定。

导航参考分层侧栏与独立的页内目录。示例块的复制按钮常态可见，作者明确标记可运行的提问，读者可以先看输入条件，再复制原文。[VitePress 侧栏](https://vitepress.dev/reference/default-theme-sidebar) · [Starlight 文档结构](https://starlight.astro.build/guides/authoring-content/) · [Docusaurus 示例复制](https://github.com/facebook/docusaurus/blob/main/packages/docusaurus-theme-classic/src/theme/CodeBlock/Buttons/CopyButton/index.tsx)

## 验证与扩展

- 开发验证命令为 `cd web && npm run docs:check && node --test scripts/skill-docs.test.mjs && npm run build`。本次通过，13 个技能、14 页原文，8 个公开 ID 与后端清单逐个一致，14 个索引目标及指南中的相对链接均可打开。测试夹具覆盖章节自动发现、缺首页、失效链接、HTML 转义、内部文档隔离和多示例文本边界。
- Chrome 已在本地生产构建的 1366px、390px 视口打开全部八个详情页的指南入口，并验证搜索、专题链接、刷新直达、无横向溢出。在独立的 Vite 开发副本中新增、修改、删除专题页，浏览器自动出现新章节、刷新正文、最后显示未找到文档。公网入口实测从文档中心打开 PDF 翻译指南及其核对专题。
- 2026-11-04 在 1366px、390px 的 Chrome 中核对目录、搜索、专题切换、小节深链、刷新和浏览器后退，移动端展开/收起与深色显示通过。从 9 个公开页面逐一复制 11 个提示词，实际剪贴板逐字匹配源文本；另测 HTTP 回退、复制失败时选中原文、公网 HTTP 粘贴结果。
- 后续在单技能的专题数增长后再增加多级章节。涉及运行能力或交付方式变更时，在改技能的同一提交更新对应指南。
