# 083 · 微信公众号报告技能：项目安装与无表单对话入口

**状态**：已实现（2026-10-30；依赖安装、真实低权 Pi 加载、8 项技能目录、浏览器入口、离线样例工具链、12 项回归及构建通过）。真实数据库聚合、完整报告质量与微信草稿推送未验证。

## 动机

用户要求安装 `MJL629/Official-Account-Skill`，明确不要注册表单。仓库实际技能位于 `wechat-report/`，上游 SKILL.md 缺少 frontmatter，脚本默认写入自身目录并写死 Windows Edge 路径，不能直接适配当前只读技能目录和 Linux 低权 Pi。现有 UsePage 对没有表单的技能会回落至第一个技能，必须避免用户点“在线运行”后进入错误任务。

## 约定细节

- 来源固定为 `https://github.com/MJL629/Official-Account-Skill` 的 `286cee93072e1b8e8539a88b80487967440a2f74`，使用 skill-installer 的 Git 方式安装 `wechat-report/` 到 `.agents/skills/wechat-report/`。公开 HTTP 返回 404，本机既有 SSH 权限可读；不据此推断仓库的公开性。保留完整 scripts/references/assets/example 与字典、机器人样例，采用目录快照，不添加子模块。
- `.agents/skills/wechat-report/SKILL.md:1` 补充 `name: wechat-report` / description；`:8` 规定先读 `references/project-installation.md`，将脚本与资源复制到会话 workspace 的 `./wechat-report/`，后续轮次沿用该副本，避免向只读安装目录写入。真实凭据、`.venv` 与历史输出不随副本复制。生成大纲后按用户确认的内容渲染；只有明确要求推送且账号配置齐备时才调用草稿接口。
- `requirements.txt:1` 声明 PyMySQL、Pillow、openpyxl；本机通过 `/usr/bin/python3 -m venv` 安装到技能下 `.venv/`，运行时使用解释器绝对路径，避免开发 shell 的 Conda Python 与低权 PATH 不一致。`.gitignore:1` 排除依赖、运行产物与真实配置，`/report_data.json` 只锚定根目录，**保留** `example/report_data.json` 入库。
- `scripts/db_setup.py:22` 将配置保存位置由 scripts/ 修正到技能副本根目录，与 fetch_data.py 一致。未自动复制项目已有数据库凭据，未创建公众号配置。
- `scripts/render_report.py:22` 自动发现 Edge / Chrome / Chromium，允许 `WECHAT_REPORT_BROWSER` 覆盖；`:28` 与 `:838` 使用 Path.as_uri 生成本地资源和页面 URI；`:839` 对浏览器进程失败抛错。`:354` 修复上游横向柱状图模板参数错位：原来把颜色值填入布尔表达式，生成非法 JavaScript，图片虽存在但图表空白。
- `scripts/publish_draft.py:175` 支持 Noto CJK / 文泉驿中文字体及 `WECHAT_REPORT_FONT`，保留 Windows 字体回落。本次仅验证字体加载，没有调用微信接口。
- `web/server/lib/skills.ts:185` / `:193` 注册 SKILL_PROMPTS 与 INSTALLED_SKILLS，复用 Pi 的显式 `--skill` 和首轮 `/skill:wechat-report`；不加入 HTML_REPORT_SKILLS、PDF_REPORT_SKILLS 或 report-meta。前端静态文案在 `web/src/data/skills.ts:316`，保留现有 SKILLS[0] 与其他默认行为。
- **不修改 useTaskConfigs.ts，不创建表单。** `web/src/router/index.ts:35` 对已知、无表单技能的 `/use/:slug` 重定向到 `/experience?skill=<slug>`，保留查询参数；`web/src/pages/ExperiencePage.vue:868` 只接受已知技能并挂载，不自动发送任务。DetailPage.vue:52 根据是否有表单说明使用入口。广场卡片和详情页现有“在线运行”链接均可复用。
- 输出仍沿上游的 `output/report/`、`output/article/`、`output/evidence_核查表.xlsx`，在当前会话副本内部。**未增加图片或 ZIP 下载接口**，不得伪造 reportUrl 或套用其他报告技能的固定文件协议。

## 验证

- `/tmp/wechat-ui-smoke.mjs`：真实 Chrome 断言直接 `/use/wechat-report` 与广场卡片均进入已挂载技能的对话、没有表单；`$wechat` 选择器能找到技能；现有 doc-translate 表单正常。
- `/tmp/wechat-pi-smoke.mjs`：真实 youcai / 低权 Pi 显式加载技能，读取项目运行说明并通过 bash 使用安装目录 `.venv/bin/python` 导入三个依赖，最终返回 `wechat-skill-ok`；2 次真实工具调用。没有数据库/微信访问。
- `/tmp/wechat-install-smoke.py`：离线示例生成 12 页大纲；12 页 HTML 内联脚本与百分比/计数两种 hbar 代码通过 Node 语法检查。仅取封面和一页 hbar 作渲染夹具，得到 943px 图片、拼接图、文章和含四张工作表的 XLSX；render_check.py 图表存在性 PASS，并人工查看图表可见。此项只验证工具链，不等同于完整报告内容验收。
- `node --test web/src/composables/useChatApi.test.mjs web/server/lib/conversation.test.mjs`：12 项通过；`cd web && npm run build`：通过。安装目录 Python/JSON 语法检查通过，注册断言确认无表单、不改变默认技能与 HTML/PDF 集合。
- 项目后端已重启，`GET /api/skills` 返回 8 项、wechat-report.installed=true；`/api/health` 正常且仍使用 youcai。

## 成本与取舍

- 否决仅复制 SKILL.md：会丢失脚本、ECharts、图表范例和字典。否决立即改为子模块：本次有必要的本地兼容修正，目录快照便于审查；代价是之后升级需手工比较上游提交与本地修改。
- 否决给技能填空表单或复用第一个报告表单：违背用户要求且会带入错误的报告参数。采用“已知技能但无表单”的路由规则，现有表单路径保持有效。
- 工作副本会重复约 4.4MB 资源，但不复制 Python 环境；换取只读安装目录与会话输出隔离，避免大范围改写上游 BASE/默认输出逻辑。Python 环境和浏览器属于部署依赖，Git 不携带已安装环境。
- 未把数据库配置自动转换为项目 MySQL 工具协议，未接入新下载协议；两者会扩大权限、查询口径与工件交付边界，安装任务先保留显式配置和真实文件输出。

## 后续扩展路线

- 配置合适的数据库只读账号后验证聚合口径、查询成本和实际报告质量；完整低权浏览器渲染、各主题/图表、重试与并发仍待验证。
- 如需从网页下载分屏图、文章与压缩包，另行设计受控工件清单与下载接口。
- 在用户明确要求并提供账号配置后测试微信草稿接口；升级上游时对照固定来源提交保留本地兼容修正。
