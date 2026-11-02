# 083 · 微信公众号报告技能：项目安装与无表单对话入口

**状态**：安装与入口已实现（2026-10-30；依赖安装、真实低权 Pi 加载、8 项技能目录、浏览器入口、离线样例工具链、12 项回归及构建通过）。2026-11-02 审查复现数据范围、质检、渲染与交付缺陷，见文末；缺陷尚未修复。真实数据库聚合、完整报告质量与微信草稿推送未验证。

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

## 2026-11-02 · 技能整体审查（缺陷待修）

**动机与范围**：用户要求整体检查技能质量并确认 `.venv` 是否适用于 Linux。本轮只审阅全部 13 个 Python 脚本、运行规范与配套文档，执行离线夹具及本机 Chrome 布局探针；未修改技能代码，未访问真实数据库或微信 API，保留用户已有的 `assets/brand.json` 修改。以下复现不能推定真实岗位查询或公众号推送已经通过验收。

### 已核实的环境事实

- `.agents/skills/wechat-report/.venv/pyvenv.cfg:1` 的 home 为 `/usr/bin`，executable 为 `/usr/bin/python3.12`，创建命令为本机 `/usr/bin/python3 -m venv .../.venv`。
- 实际执行该环境的解释器，得到 Python **3.12.3**、`sys.platform=linux`、`sysconfig.get_platform()=linux-x86_64`、`base_prefix=/usr`；解释器解析到 `/usr/bin/python3.12`。
- PyMySQL **1.2.3**、Pillow **12.3.0**、openpyxl **3.1.5** 均可导入；Pillow 加载 `_imaging.cpython-312-x86_64-linux-gnu.so`。本机浏览器可执行文件为 `/usr/bin/google-chrome`，本轮实际渲染与 DOM 测量成功。
- `git ls-files .agents/skills/wechat-report/.venv` 无条目；`git check-ignore .../.venv/pyvenv.cfg` 命中忽略规则。该环境是当前 Linux 主机上的可用依赖，不是可跨操作系统/路径直接搬运的交付物。

### 优先修复项与证据

1. **地区参数实际失效**：`scripts/fetch_data.py:148` 仅按 `--scope` 在“广东”与 `1=1` 之间切换，未使用 `args.region`。模拟连接并在首次 SQL 执行前截获语句，`--region 河北省` 与 `--region 佛山市` 得到相同的广东全省过滤；`--scope custom --region 河北省` 得到全国过滤。违背 `SKILL.md:22` 的单地区承诺，也违背脚本顶部的河北示例。应显式解析省/市范围、拒绝未知 scope，并让输出 meta 与实际过滤共享同一份范围对象。
2. **通用行业和空样本缺少边界处理**：`scripts/fetch_data.py:66` 的 PRIORITY、`scripts/report_common.py:9` 的 TRACK_GROUPS 固定为 AI 分类。`scripts/gen_outline.py:153`、`:183` 直接访问首个方向。把非 AI 数据归入“其他”，或传入空样本，均复现 `IndexError`。应按行业选择分类配置，未支持行业明确提示；空样本/无有效薪酬/不足两个城市分别降级，不输出零值假结论。
3. **数字溯源未绑定指标语义**：`scripts/verify_data.py:285` 把所有输入数字放入同一集合，随后只判断文案数字是否在集合中。把样例企业数 **5089** 写成“深圳市共有5089条岗位”（样例深圳实际 **7496**），校验仍退出 **0/PASS**。`:278` 只信任 `all_checks_pass` 并展示 hash，没有重算指纹；`:192` 的正文枚举遗漏摘要 `lead`/`tail`，导致其中的数值、禁语未参加对应检查。应让 claim/chart 引用明确字段路径、分母和公式，核对数值与对象，并遍历全部可见文案。
4. **缺图会被判定为通过**：`scripts/render_check.py:286` 初始 `all_ok=True`，`:289` 遇到不存在的 PNG 直接跳过。12 页大纲无任何 PNG，仍退出 **0**，结果为 `{"all_pass":true,"checks":[]}`。构造一页 manifest（PNG 不存在）后，上述错误数字夹具也能通过完整 `verify_data.py`，未使用跳过选项。`verify_data.py:414` 只比较页数，`:423` 调用 render_check 未传用户的 outline/report-dir/theme。应将缺图、空检查、旧大纲/旧产物判为失败，传递路径与主题，并绑定大纲指纹。
5. **自适应高度实现不一致**：`scripts/render_report.py:820` 给内容容器固定 `SCREEN_H=2000`，`:826` 却返回估算高度供截图；`:73` 的容器设置 `overflow:hidden`。Chrome 实测：区域页请求截图高 **1655**，页脚在 **y=1943–1970**，因此截图不含页脚；双图页按文案规范放入约 **300 字**的布局夹具后，请求高 **2675**，容器仍高 **2000**，总结框底到 **2089.97**，与页脚重叠且超出部分被裁。不能把此前两页渲染夹具的成功推广为完整报告布局验收。应统一容器/截图高度，并在字体和图表就绪后测量实际 DOM 高度、检查溢出。
6. **结论模板预设数据没有证明的事实**：`scripts/gen_outline.py:118` 固定写“广东”，`:227` 固定写“非本科通道约占一成”，`:262` 固定写“月薪2万元上下”，`:308`、`:462` 固定写广深；`:167` 预设“岗位分工正在加速细化”。北京单城离线夹具仍生成“广东/广深/双核/全省”。`scripts/build_article.py:45` 在 voc 风格预先断言“进得去，而且通道清晰”，`:49` 的 scene 风格无实际场景证据却断言人员“大多数”来自职校。应让描述依据数据成立条件生成；结构事实、分析推断与待验证解释分开表述，禁止单时点数据生成动态结论。
7. **SQL 拼接与查询成本边界不足**：`scripts/fetch_data.py:162` 直接插入 `name_kw`；含单引号可破坏语法，离线截获确认 `机器人' OR 1=1 -- ` 会进入 WHERE。`:179` 使用普通游标 `fetchall()` 一次加载全部岗位描述，而通用 scope 会放开全国；`:498` 的技能提及率分母只在有 description 时累加（`:301`），与文档“该方向岗位数”分母不同。应参数化关键词、明确通配符规则，限定查询规模或流式聚合，记录有描述的有效样本量；薪资分位算法与精度亦需统一定义。
8. **证据核查表不是实际执行日志**：`scripts/evidence_sheet.py:53` 重建 SQL，`:159` 使用重建语句而非直接消费 qlog，并在 `:162` 依赖 SQL 前缀匹配计时。样例有 **8** 条已记录查询，却生成 **9** 条核查 SQL，其中主扫描字段与实录不同，额外职教池查询未见实际执行；`:252`、`:253` 把城市排序第 1/2 项硬标成深圳/广州，单城会越界。应直接使用实际 SQL、参数、执行时间与查询 ID，另标“建议复核 SQL”，按真实城市名输出指标；固定取数截止时间，避免后续 `NOW()` 重跑改变时间窗。
9. **交付包扫描存在遗漏且会混入旧页**：`scripts/pack_delivery.py:67` 原样打包含 SQL 的证据 XLSX；`:119` 只复检 json/md/html。使用虚构 SQL 单元格生成 XLSX，打包退出 **0/脱敏完成**，解包后该 SQL 原样存在。`:58` 按 glob 收集 PNG，夹具中的旧 `page_99.png` 不在 manifest 中却仍入包。应区分内部审计包和对外交付包，扫描工作簿的文本内容，并仅按本次 manifest 的工件清单打包；失败时不保留貌似成功的 ZIP。
10. **编辑台会备份密钥且不受现有忽略保护**：`scripts/edit_server.py:30` 允许编辑真实 `mp_config.json`，`:200` 每次保存创建 `.bak`；这也与项目“用 Git，不用 .bak”约定冲突。`git check-ignore --no-index .agents/skills/wechat-report/assets/mp_config.json.bak` 退出 **1**（不忽略）。当前没有创建或读取真实微信凭据；风险发生在后续配置并编辑时。应停止为密钥创建备份，统一配置与编辑台边界；`references/project-installation.md:26` 的递归复制 assets 示例也需显式排除未来可能存在的真实配置文件。

### 说明文档与工作流需要收敛

- `SKILL.md:26`、`:31` 鼓励趋势预测，后文及 data-aggregation 禁止用非均匀 update_time 下时间趋势结论，缺少“预测需额外证据/方法”的明确入口。
- `references/copywriting.md:15` 禁用“可投递”，`:69` 自检清单却要求“累计可投递”；`:38` 禁“值得一提的是”，`:49`、`:56` 又推荐同一句；`:28` 要 1–2 句导语，`:40` 要 250–320 字；SKILL 面向政府/企业/院校，而文案规范把受众固定为职校。旧版本补注应整合为一套有效规则，风格示例也要一起更新。
- 先校验再渲染与像素校验依赖已渲染图片形成流程循环。`--skip-render-check` 当前仍可输出“全部通过，可渲染/发布”；render/publish/pack 本身未消费绑定当前产物的最终验收状态。建议拆分数据/大纲预检与渲染后验收；跳过项保留 pending，交付和推草稿只消费完整验收。
- 图表“12种”混合了基础 kind 与复用样式，image-spec 仍称 8 种，实际有 10 种基础 kind（含 HTML table/bignum）；新增 kind 未实现时应明确报错。image-spec 的外部切片目录不随技能安装存在。
- `publish_draft.py:279` 的标题参数提示“32字”与 `:306` 的“64字节”校验不一致，生成文章标题没有提前适配这套本地校验；公众号文档还包含上游接口实测结论。本轮未查验当前微信官方限制或调用接口，不把这些限制当作本项目已验证事实。
- 当前网页图片/ZIP 下载缺口仍与原安装决策一致，不能仅凭 workspace 路径认定在线用户已取得可下载交付物。

### 本轮验证、取舍与下一步

- 一次性离线审查脚本 `/tmp/wechat_report_audit.py`：13 个脚本 AST 解析通过，样例生成 12 页大纲，并复现上述地区过滤、空样本/未知分类崩溃、错误数字通过、缺图通过、摘要未扫描、SQL 重建偏差和 ZIP 漏扫/旧页入包问题；结果在 `/tmp/wechat-report-review-vai96njy/audit-results.json`。夹具使用安装目录的 `.venv/bin/python -B`，只向 `/tmp` 写入，不连接数据库/微信。
- `/tmp/wechat_render_probe.py`：本机 Chrome 实际渲染薪酬样页，读取短页与约 300 字双图页的 DOM 布局；结果在同目录 `layout-results.json`、`layout-extra-results.json`。临时夹具不是正式报告产物，不入库。
- **取舍**：本轮为审查，否决顺带批量修改上游脚本或更换报告口径，以免超出用户范围；只把已复现事实并入本主题记录。没有运行与文档变更无关的前后端全套测试，也没有把通过的语法检查等同于业务验收。
- **后续顺序**：先修地区/行业与空样本边界 → 指标绑定和完整性校验 → 高度/溢出 → 内外部交付和配置边界 → 文档与受众/风格统一。真实只读数据库口径、查询内存/耗时、完整低权全主题渲染、在线下载及微信草稿验收仍待单独授权范围内实现与验证。
