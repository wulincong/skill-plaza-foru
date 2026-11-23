# 067 · 在线对话默认通用智能体与 $ 技能选择器

- 状态：已实现（2026-10-16。构建通过；后端重启后 e2e 验证；浏览器 $ 选择器交互与 skill 字段断言通过。真实多轮对话与中途换技能回归待用户执行）。**2026-10-16 晚间补注（068）**：本记录的「体验页历史 = localStorage 本地会话」约定已被 068 取代（侧栏改为 /api/runs 运行记录）；「后续路线」中的体验页接入 ToolCallGroup 与报告链接渲染均已在 068 落地，登录相关的会话持久化逻辑随本地会话一并删除。
- 动机：在线对话页把所有未命中示例的输入默认路由到 industry-education-report（`DEFAULT_SLUG` 兜底 + matchDemo 关键词模糊匹配），任何普通问题都被套上产教报告技能的系统提示词、20 分钟超时与报告产出预期，属于路由级错误。正确形态：默认由通用智能体直接回答；需要专业技能时用户显式通过 `$` 挂载。

## 约定细节

### 后端：general 作为一等 skill id

- `web/server/lib/skills.ts`：新增 `GENERAL_SKILL_ID = 'general'`，并把它注册进 `SKILL_PROMPTS`（通用智能体系统提示词：先结论后依据、不编造；遇到产教报告/就业指导/技术预判等专业场景时提示用户在输入框输入 `$` 挂载 SKILL）。
  - 两套入口 `/api/chat`、`/v1/chat/completions` 的校验都是 `skill in SKILL_PROMPTS`，自动放行 general，协议零改动（036 冻结边界不破）。
  - `listPlazaSkills()` 过滤 general：`/api/skills` 仍返回 6 项（048 契约不变），通用智能体不进广场卡片。
  - 不在 `INSTALLED_SKILLS`：pi `createSession` 不加 `--skill`、`buildPrompt` 走 `SKILL_PROMPTS[skill]` 前缀回落、超时用默认 10 分钟而非已安装技能的 20 分钟。
- 运行记录：`RunRecord.skill = 'general'` 正常落盘；前端显示名走 `web/src/data/skills.ts` 的 `GENERAL_SKILL_NAME = '通用智能体'`，RunListPage / RunDetailPage 的 skillName 兜底映射（未知 slug 才裸显）。

### 前端：$ 选择器与发送路由（ExperiencePage.vue）

- `activeSkill: Ref<Skill | undefined>`——undefined 即通用智能体，是输入条的稳定默认态。
- 呼出：光标前命中 `/(?:^|\s)\$([^\s$]*)$/`（@input 驱动 `syncSkillMenu`）或点输入条 `$` 钮（`toggleSkillMenu`，无 token 场景）。菜单按 slug/名称/标签过滤，↑↓ 移动高亮、Enter/Tab 选中、Esc/点击外部关闭；选中后从文本移除 `$token` 并把光标落回原位。
- 挂载态：输入条左侧分类色 chip（图标+技能名+x 清除）；AI 消息无技能时名称显示「通用智能体」。
- 示例问题（`试试这些`）点击时同步挂载对应技能——取代 matchDemo 模糊匹配，该函数与 `DEFAULT_SLUG` 已删除。
- 发送路由（`send()`）：`requested = activeSkill?.slug ?? GENERAL_SKILL_ID`；对话已绑定其它技能时切换 = 删除 `convSessions` 中旧 Pi 会话（旧上下文属于旧技能），下轮不带 sessionId 新建，`buildPrompt` 的 `isFirstTurn = !existingEntry` 随之为 true、按首轮注入新技能指令。

### 验证（2026-10-16 实测）

- `npm run build`（vue-tsc + vite）通过。
- 重启后端后：`/api/skills` 6 项不含 general；假 skill 400 报错不变；`POST /api/chat {"skill":"general"}`「只回复两个字：验收」→ SSE text→usage→done（runId 20261016-153211-fchx），`/api/runs` 首条 `skill=general`。
- CDP 无头浏览器（拦截 fetch 断言请求体）：`$career` 过滤至 1 项、↓+Enter 选中后 chip=就业指导且 `$career` 从文本移除、挂技能发送 `body.skill=career-guidance`（消息内容无 token 残留）、清除 chip 后发送 `body.skill=general`、`$` 钮可呼出菜单。
- 明暗双主题截图核对：菜单玻璃层、chip、发送后消息流均正常，深色下菜单文字对比度名称 15.8:1 / 描述 6.7:1 / slug 5.2:1。

## 成本与取舍

- 否决「把 general 做成 INSTALLED_SKILLS 假技能」：会误加 `--skill` 路径解析、`/skill:` 命令展开语义与 20 分钟超时，通用对话都不需要。
- 否决「$ 语法在后端解析消息文本」：skill 字段已是显式选择通道，前端 chip 状态机足够，后端协议保持冻结。
- 否决「保留 matchDemo 内容模糊路由」：正是本次错误根源；显式 $ 与示例挂技能完全取代。
- 换技能丢弃旧会话的代价：该对话旧轮上下文不延续到新技能（也不可换回恢复）；接受原因是 Pi 会话与 `--skill` 注册在创建时绑定，跨技能复用会话会让 `/skill:` 展开失效。

## 后续扩展路线

- 体验页接入 ToolCallGroup（066 路线）：general 对话同样吃 status 事件，可直接复用。
- 会话内换技能时把旧会话上下文按 036 的历史拍平方式注入新会话，保留记忆。
- $ 菜单标注「已安装」状态（复用 /api/skills 的 installed 字段）。

## 2026-11-23 补注：取消 8 条上限、限高滚动与类别筛选

- 现象：`skillMatches` 固定 `slice(0, 8)`。`/api/skills` 增至 15 项后，只输入 `$` 只显示登记顺序前 8 项，菜单也没有「还有更多」的提示；排在第 11–15 位的 teaching-diagnosis、courseware-studio、training-program-design、course-scheduling、course-development 不输入关键词就看不到。后端清单本身是自动的（`listPlazaSkills()` 每次请求现读 SKILL.md，前端路由守卫每次导航重拉，都不需要重启），问题只在前端截断。
- 约定（`web/src/pages/ExperiencePage.vue`、`web/src/styles/styles.css`、`web/src/data/skills.ts`）：
  - `skillMatches` 不再截断（ExperiencePage.vue:180）。`.exp-skill-menu` 改为纵向 flex 容器并 `overflow: hidden`（styles.css:1252，高度上限仍是 `min(320px, 46vh)`），`.exp-skill-list` 独立滚动（styles.css:1261）；↑↓ 移动高亮时由 `revealSkillHighlight` 把高亮项滚入可视区（ExperiencePage.vue:220，调用点 :307）。
  - 类别筛选：`SKILL_FILTERS` = 全部 / #产业与专业建设 / #课程与教学开发 / #实训与就业 / #其他（skills.ts:481）；`skillFilterOf(slug)`（skills.ts:486）取技能在静态表里的 `categoryId`，industry / teaching / career 各自成组，其余（data 与没有静态条目的技能）归入「其他」。与 `$关键词` 是「且」关系；每次呼出菜单回到「全部」；某类别下无匹配时，空态文案写明当前类别。
  - 筛选行放在列表下方、贴着输入框（ExperiencePage.vue:1161）。菜单以底边锚定输入框、高度随匹配数伸缩（实测 1 项 100px、15 项 320px），只有贴底的内容位置稳定；放在顶部时切换类别会让筛选行跳动约 220px，鼠标落空。
  - teaching-diagnosis 补静态条目（skills.ts:410，`categoryId: 'teaching'`）。此前它是唯一没有静态条目的已上线技能，回落对象的 `categoryId: 'industry'` 只是图标占位，后果：
    - 详情页 `/skill/teaching-diagnosis` 空白、标题为「没有这个 SKILL」，任务页标题缺技能名（改动前浏览器实测）。
    - 没有标签，`$考勤` 搜不到（按前端过滤规则复算确认）。
    - 挂载后不显示技能 chip、广场计入「产业与专业建设」——由代码确认（`activeSkill.value = bySlug.get(...)` 取不到；SkillsPage 按 `categoryId` 筛选），改动前未在浏览器实测。
    - 运行本身不受影响：发送用 skill id 字符串（`runReal(text, slug, …)`），不经静态表。
- 验证（2026-11-23，Chrome 138 无头 + CDP，真实键盘/鼠标事件；`vue-tsc --noEmit` 通过）：
  - 只输入 `$`：15 项全部进入列表，列表可视 270px / 内容 755px，菜单完整落在视口内，焦点留在输入框。
  - ↓×12 后高亮项在可视区外时，列表滚动 384px 跟随；↑ 回绕到首项后回到顶部。
  - 五个类别逐个鼠标点击：15 / 4 / 7 / 3 / 1 项；切换时筛选行位置不变、指针不落在条目上、列表回到顶部。
  - 类别 + 关键词：「#课程与教学开发」+ `$排` 命中文档翻译（标签含「PDF 重排」）与排课智能体；「#实训与就业」+ `$排` 空态文案正确；Enter 选中后挂载 chip、清除 `$token`、关闭菜单；再次呼出回到「全部」。
  - `$考勤`、`$teach` 命中学勤与教学诊断，单项结果时菜单高 100px。
  - 明暗主题与 390px 窄屏截图核对通过（窄屏下胶囊换成两行，菜单不越界，页面无横向溢出）；详情页、任务页标题、广场归类三项通过。
  - 工具坑：无头 Chrome 带 `--disable-gpu` 时不渲染 backdrop-filter，截图里菜单背后的文字会透出来；核对玻璃层需改用 `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`。
- 取舍：
  - 否决「把上限从 8 调大」：登记数持续增长（蓝图 26 个智能体），固定上限仍会溢出。
  - 否决「选择器另维护 slug→类别映射」：与静态表 `categoryId` 是两份事实，容易漂移。
  - 否决「筛选行放顶部 + 菜单固定高度」：输入精确关键词只命中 1–2 项时会留大片空白；贴底放置同时保住位置稳定与高度自适应。
  - 没有改 `CATEGORIES` 第四类的名称：广场页分类标签仍是「数据治理与模型底座」，「#其他」只是选择器里的归并标签。
- 后续扩展路线：
  - 类别取自静态表，新技能若不补静态条目会落入「#其他」且没有标签；技能数继续增长时，可让 `/api/skills` 从 SKILL.md frontmatter 带出分类与标签，去掉这层手工登记。
  - 菜单顺序仍是后端登记顺序，新技能排在末尾；需要时可改为与广场页一致。
