# 009 · MySQL 只读查询工具（Agent 可用）

**状态**：已实现（CLI 直测 + pi Agent 端到端验收通过，2026-09-23）

**补注（2026-10-19）**：沙箱 AGENTS.md 的送达方式变更——pi 改以 `--no-context-files` 关闭 AGENTS.md 目录链发现、沙箱说明经 `--append-system-prompt` 显式注入（防止仓库根开发 AGENTS.md 链式进入运行上下文），工具声明内容不变，见 075。

**补注（2026-11-02）**：配置读取抽出到 `scripts/mysql-config.mjs:7`，本工具及 career-market-query 复用，保留原有命令/统计语义。新增共享人才查询 Skill 与结构化 CLI、缓存和队列见 085；在线仅声明共享结构化入口，不因此开放原始 SQL。旧工具尚未迁移新队列。

**动机**：广场 Agent（pi/zcode 会话）与开发会话此前只能靠人手拼 mysql 客户端长命令查岗位库（连接方式、utf8mb4 坑散在个人记忆里）。需要一个仓库内的标准工具：凭据不进公开仓库、固化字符集坑、只读防呆、输出对 Agent 上下文友好。用户选定范围：工具 + 接入 pi Agent 运行时，**不新增广场智能体卡片**。

## 约定细节

### 工具本体：`scripts/mysql-query.mjs`（零 npm 依赖，Node ≥20）

- 用法：`node scripts/mysql-query.mjs [选项] "SQL"` 或 `--file f.sql`（单条语句）。
- 选项：`--format json|table`（默认 json）、`--max-rows`（默认 200）、`--max-cell-chars`（默认 400，JD longtext 防撑爆上下文）、`--timeout-ms`（默认 120000）、`--mysql-bin`。
- 配置：`MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` 进程环境优先，缺的键回落解析 `web/.env`（脚本按 `../web/.env` 相对定位，不覆盖已有环境变量）。模板键见 `web/.env.example` 尾部。
- 执行：spawnSync mysql 客户端 `-B --batch`，密码走 `MYSQL_PWD` 环境变量（密码含 @，避开引号/ps 问题）；每连接前置 `SET NAMES utf8mb4 COLLATE utf8mb4_general_ci; SET SESSION max_execution_time=<timeout>;`（8.4 客户端连 5.7 服务端握手退 latin1 的已知坑）。
- 只读守卫：注释清洗后拒绝多语句；首关键字必须 ∈ {select/show/desc/describe/explain/with}。**这是防呆不是安全边界**——账号本身仅 SELECT 权限。
- 输出：`{ok, sql, elapsedMs, columns, rowCount, totalRows, truncated, rows:[{col:val}]}`；出错 exit 1 输出 `{ok:false,error}`；table 格式输出 markdown 表。

### Agent 接入：沙箱 AGENTS.md（不改 runner 协议）

- `web/server/index.ts` 的 `workspaceDirFor()`（约 `web/server/index.ts:121` 起，含 `sandboxAgentsMd()`/`mysqlConfigured()`）在创建沙箱目录时同步写入服务端维护的 `AGENTS.md`：声明工具绝对路径、选项、使用约定（先小范围探查再聚合、中文岗位名用 LIKE、报告类技能默认以内置口径文档为准除非用户明确要求查库——维持 006/007 与 industry-education-report 的禁网禁库决策）。
- 送达方式（2026-10-19 起，见 075）：pi 以 `--no-context-files` 关闭 AGENTS.md 目录链发现，沙箱 AGENTS.md 经 `--append-system-prompt` 显式注入系统提示词（两个 createSession 调用点均先经 `workspaceDirFor()` 写好该文件）；zcode 引擎不在当前执行链，如恢复仍走 cwd 链式发现（resource-loader 从 cwd 向祖先遍历收集）。
- 条件化：`mysqlConfigured()`（MYSQL_HOST/USER/PASSWORD/DATABASE 齐）才写工具节，公开部署无凭据时不给 Agent 坏工具。
- 凭据与路径边界：MYSQL_* 真实值只落本地 `web/.env`（gitignore 实证）；机器相关的脚本绝对路径只写进沙箱 AGENTS.md（不入 git）。

## 成本与取舍

- **否决：给 pi 加 MCP/扩展工具**——PiRunner 以 `--no-extensions` 无头启动（裁上下文开销），为单一工具引入扩展机制不成比例。
- **否决：HTTP 查询接口**——Agent 侧调 HTTP 比 bash 麻烦，且多一条鉴权面。
- **否决：纯 JS MySQL 客户端依赖**——破坏后端零第三方依赖惯例；mysql 客户端本机已有，`--mysql-bin` 可覆盖。
- 已知限制（MVP 接受）：`-B` 批处理输出 NULL 与字面 "NULL" 不可区分；大结果集受 32MB maxBuffer 截断报错（查询应自带 LIMIT）；多语句不支持。

## 验证记录（2026-09-23）

- CLI 直测：`SELECT 1 AS ok,'中文测试'`（utf8mb4 往返正常，72ms）；中文 LIKE 检索岗位名 3 行正常返回；`INSERT`/多语句被守卫拒绝（exit 1）；`LIMIT 300` 配 `--max-rows 50` → `truncated:true, rowCount:50, totalRows:300`；`--format table` markdown 表正常。
- 端到端（8799 端口测试实例，pi + deepseek-flash）：会话问「PUBLISHING 总数 + 3 条样例」→ Agent 依沙箱 AGENTS.md 自发执行两条 `node ".../scripts/mysql-query.mjs" "SELECT ..."` bash 命令（events.jsonl 留痕），11.0s 完成、$0.0028、outcome success；回答总数 9,625,580（与 9-20 基线 9,616,999 同量级，库在增量为合理漂移）。

## 后续扩展路线

- 升级为广场「数据查询」智能体卡片时，按 4 接入点（skills.ts/useTaskConfigs/DEMOS/hero）+ 父子仓库模式建独立技能仓库，AGENTS.md 通道与工具本体可直接复用。
- 如需多语句/批次分析，可加 `--file` 多语句按序执行逐条输出的能力。
- 图2/3/7/8 补算（广东报告 gap）可直接用本工具跑，替代手拼 mysql 长命令。
