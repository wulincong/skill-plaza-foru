# 048 · 广场技能列表动态化：/api/skills 与幽灵卡移除

**状态**：已实现（vue-tsc + vite build 通过；/api/skills 实测返回 6 技能；浏览器页面回归待用户执行）

## 动机

用户反馈「智能体广场」页看不到 tech-forecast：该页卡片由 `web/src/data/skills.ts` 的 AGENTS 矩阵（T01–T24 规划智能体）驱动，只有挂 `skillSlug` 的才渲染真实技能卡，tech-forecast 接入时只加了 SKILLS 数组没分配 T 编号，于是整页缺席；其余 19 个"即将上线"置灰卡也是写死的规划清单。用户结论：**24 不能写死，广场应跟随后端可运行的技能动态增减，未上线的规划项不展示**。

## 约定细节

### 后端：GET /api/skills（无鉴权、无 Origin 限制，公开目录数据）

- **可运行权威集合 = `SKILL_PROMPTS` 键**（`web/server/lib/skills.ts`，与 `/v1/chat/completions` 的 400 可用值列表同源）；`INSTALLED_SKILLS` 标记哪些在仓库 `.agents/skills/` 下有真实技能文件夹。
- `listPlazaSkills()`（`web/server/lib/skills.ts`）返回 `{id, name, description, installed}[]`：已安装技能读 `skillDir(id)/SKILL.md` frontmatter 的 `name`/`description`（**注意 frontmatter name 是加载键不是中文展示名**，展示名仍以广场静态文案为准）；未安装技能（外部仓库接入的 classroom-assistant 等）取回落提示词 `SKILL 工作。` 后首句。
- 路由在 `web/server/index.ts` createServer 分发处，`/api/health` 之后；公开数据，与 `/api/reports/*` 同样不做 Origin 检查。

### 前端：SkillsPage 动态合并

- `web/src/pages/SkillsPage.vue`：`onMounted` 拉 `/api/skills` → `entries = remote.map(r => bySlug.get(r.id) ?? basicSkill(r))`；**后端不可达时回落静态 SKILLS**（与运行记录页回落演示数据同一模式）。`basicSkill()` 为后端先于前端文案上线的技能渲染基础卡（categoryId 暂落 industry，tags 标「已上线/可运行」）。
- 幽灵置灰卡分支、`Entry.kind`、AGENTS 排序逻辑全部删除；状态行从「共 X 个智能体 · Y 个已上线 SKILL」改为「共 X 个 SKILL」；筛选/搜索改用 Skill 字段（name/identifier/summary/tags）。
- `web/src/data/skills.ts`：AGENTS 矩阵、`Agent` 接口、`agentsOf()` 移除（历史数据见 git，9ab876f 之前版本）；SKILLS 数组语义变为"静态富文案层"，卡片数以 /api/skills 为准。

### 新增技能的上线路径（当前约定）

1. 技能文件夹放 `.agents/skills/<id>/`（或外部仓库），后端 `SKILL_PROMPTS` 注册 → 立即可运行并出现在广场（基础卡）。
2. 前端 `SKILLS` 数组补富文案条目（提供详情、输入示例与 API 标识，见 036 的公开指南约定）→ 基础卡自动升级为完整卡。

## 成本与取舍

- **否决：给 tech-forecast 新增 T25 或挂到 T02**——仍是写死，下一个技能还会遇到同样问题。
- **否决：构建期脚本扫描 .agents/skills 生成数据文件**——文件夹里有 plaza-dev-notes、chart-visualization 等非广场技能，目录名不等于可运行清单；且仍需构建才更新。后端注册表才是"可运行"的权威。
- **已知限制**：basicSkill 卡的「查看详情/在线运行」链接对未知 slug 会落到 DetailPage（无数据）与 UsePage 的 `bySlug.get(slug) ?? SKILLS[0]` 兜底（**会错跑第一个技能**）。当前 6 个 id 全有静态条目，路径不可达；后端先于前端上线新技能的窗口期要尽快补静态条目，后续可在 UsePage/DetailPage 加未知 slug 404 处理。
- 并行会话同日已提交 `b36a4c4`（openai 升级摘要）、`9ab876f`（/v1 标准 chunk 升级），本记录的接口改动与其无冲突。

## 后续扩展路线

- UsePage/DetailPage 对未知 slug 的显式 404/提示（消除 SKILLS[0] 错跑兜底）。
- `/api/skills` 可扩展返回分类、角色与输入示例，让广场页完全脱离前端静态清单；届时 DetailPage 也改为 API 驱动。
- 首页 Hero 与运行历史页的技能计数已随 SKILLS 动态，无需改动。
