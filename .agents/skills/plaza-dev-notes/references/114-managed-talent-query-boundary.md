# 114 · 产教业务与受管人才查询的执行边界

**状态**：已实现。原生工具、范围校验、失败停止、每轮预算、取消与分段诊断已接入产教在线会话；真实低权 Pi 取数通过。其他业务技能仍使用各自现有共享 CLI 接入，未宣称全部迁移。恶意任意代码的网络/凭据硬隔离不属于本次实现。

## 动机

086 的诊断确认：模型虽调用共享 CLI，仍能把产业替换成岗位名词、猜请求结构、套外层 timeout 并连续重查。只共享 SQL 执行器而由业务模型自由组织调用，不能保障范围和性能纪律。需要让查询技能拥有从业务取数需求到统计工件的执行过程，并给每层留下真实诊断。

## 职责、协议和接入点

- `.agents/skills/talent-data-query/scripts/pi-tools.mjs:25` 由查询技能维护 `talent_query`、`talent_query_capabilities`、`talent_inspect`。前者接收 samples/metrics/analysis/freshness；samples 的 region、industries 名称、roles 名称及显式筛选描述业务需求，不暴露 SQL、内部请求文件、连接或超时参数。能力枚举来自共享核心注册表；完整数据仍用原 talent-result/1 与工件验签，报告 `binding` 无需改协议。
- `scripts/talent-data/demand.mjs:39` 校验业务需求并构造内部 talent-query/1；`:62` 解析唯一同名 level=0 产业并保留子树，未知/歧义返回候选，禁止静默改为 title。目录词与明确措辞识别用户原话中的产业意图，阻止遗漏这些产业；这不是完整自然语言解释器，复杂排除和隐含指代仍需语义核对。原生能力目前以整个产业为默认业务语义，精确细链的直接 ID 查询保留在共享 CLI，不借名称猜细链。
- `scripts/talent-data/demand.mjs:78` 管理每轮累计 240000ms、最多两次统计批次、相同需求已验工件复用和失败停止。状态保存在 `.talent-query/<hash(runId)>.json`，支持进程重开后识别未完成调用；原生适配器串行执行，源库统计仍由现有跨进程重查询锁约束。单条最长 120000ms，不增加外层 shell timeout。格式/范围错误可在启动统计前修正，数据库/执行失败阻止本轮后续调用。新用户轮次预算重置，业务层仍须遵守用户对缺口和范围的选择，不能把预算重置当作获准重试。
- `scripts/pi-tools.mjs:9` 的 tool_call hook 拦截直接查询 CLI、旧白名单、常见数据库驱动/内部模块调用、连接配置读取及查询请求/状态改写；`before_agent_start` 每轮读取最新查询技能入口。该层用于正常智能体的工作流执行纪律，不声称能防御任意编码、间接脚本或外部网络调用。
- `web/server/lib/piRunner.ts:561` 显式挂载查询技能和其扩展；`web/server/index.ts:138` 对产教会话注入原生入口说明，去掉冲突的兼容白名单/手写请求指引；`:1885` 写入通用 `talent-query-turn/1`（runId、startedAt、caller、messages 原始用户文本）。运行器只负责挂载和上下文交接，不解析产业、构造统计请求或计算指标。业务 SKILL 和 docs 指向查询技能，避免出现第二套执行规则。

## 诊断与取消

- `scripts/talent-data/service.mjs:47` 在 validation/setup/resolution/cache_lookup/request_queue/capability/database_queue/database/aggregation/cache_write/artifacts 等实际边界记录事件。`database_result` 保留实际语句完成状态。`demand.mjs:88` 写 `.talent-query/events.jsonl`：schema=talent-query-stage/1、owner、runId、traceId、at、stage、state，按事件附 durationMs/code/实际 requestId/结果路径。handoff 返回同一关联标识，出错可归到具体阶段；日志不复制 SQL 或密码，SQL 仍只存内部 evidence。
- `scripts/talent-data/db.mjs:14` 在每条统计前后用独立 MySQL 语句记录服务器时刻，完整语句增加 sourceStartedAt/serverElapsedMs，失败为 null。这是包含少量边界语句开销的包围计时，不冒充 performance_schema 的精确执行计时。保留旧 elapsedMs 的客户端到达间隔语义，避免历史字段被误读。sqlBatchMs 含连接和传输；缓存复用时源批次计时与当前 wallMs/stages 区分。未改统计语义，因此未为计时字段单独改变内容指纹算法或引擎版本。
- `db.mjs:36` 接受 AbortSignal、终止当前 mysql 子进程并返回 QUERY_ABORTED；`state.mjs:63` 与 `entities.mjs:36` 让排队和实体解析感知取消。原生调用不包外层进程超时，内部可完成失败/部分结果的落盘。彻底退出进程仍可能只留下 started/inFlight，后续据此标记中断，不伪造完成事件。

## 验证

- 69 项针对性测试通过：共享查询、产业候选/多组聚合、目录、分析指标、城市薪酬、产教证据/交付，以及新增 9 项需求与原生工具边界测试。新增测试验证产业子树优先、拒绝换词、明确名称条件可用、未知产业不降级、失败持久停止、缓存复用、批次上限、无 SQL 的分段日志、真实适配器子进程和锁的取消、CLI 与配置绕行拦截。测试的合成数据不进入生产结果。
- 额外全量共享测试为 86 项：73 通过、13 个公众号集成测试因夹具缺 `assets/regional_sources.json` 失败。用本轮前 HEAD 的独立临时检出复跑全部 17 个公众号测试，同样 4 通过/13 失败，确认是既有夹具缺陷；未把该套件写成全绿。
- 技能格式、文档索引、Node 语法、Vue 构建通过。后端在无活跃任务时按 systemd 约定重启，后端及前端代理 health 均成功。
- HTTP 交付、SSE、续聊历史、浏览器会话隔离与服务重启的 8 项回归通过（与新增 9 项边界测试合跑，17/17）。验证结束时已有其他在线运行，不再次重启服务打断任务。
- 真实 Pi/优才、低权 plaza-sandbox，经兼容 API 执行广州智能网联汽车需求任务，运行 `20261105-114303-fdw8`。实际只调用一次 talent_query，由查询技能解析产业14，8项指标/6条统计在同一事务完成，随后业务层说明本校材料缺口并等待选择，未 build/发布终稿。此次原生调用 wallMs=39690，SQL批次37052ms，排队102ms；各完整 SQL 的服务端包围计时均非零并保存在 evidence。该观察证明新链路可用，不与旧 title 口径做等价性能倍数比较，也不代表任意产业时延承诺。
- 在线消息仍可能先写一份未经 build 的报告草案，且会从已知字段推导业务建议；本轮验收不涵盖这些建议的教育适用性或最终报告质量。受管查询只约束取数，不替代业务证据门槛。

## 成本、取舍和后续

采用同一 Pi 进程中的技能原生工具与现有查询核心，不增加另一个模型客户端/子智能体，不复制统计实现。业务侧保留“需要哪些指标”的判断；查询侧维护范围、执行与错误。代价是原生适配器与需求协议需要测试，按轮预算可能要求把大型取数计划拆成用户明确的多轮任务。

否决只再加一句“严格查库”的提示、业务技能自写查询模板、失败后换词试查，以及直接并行多个重聚合。真实本次耗时仍主要在各指标的重复产业集合扫描；后续可在查询技能内评估共享筛选结果、索引或预聚合，业务报告无需同步改查询逻辑。

待扩展：将同一受管接口接入其他业务技能并分别验收；对复杂产业排除/跨轮范围变更增强明确的范围交接；在运行管理页按 traceId 汇总阶段诊断；独立推进数据库权限与网络硬隔离。上述均不作为本轮已完成能力。

参考：[Pi 扩展契约](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)（实现时核对本机0.87.1类型和事件）；[MySQL日期时间函数](https://dev.mysql.com/doc/refman/8.4/en/date-and-time-functions.html#function_now)（语句时刻和微秒差值，实际部署已执行验证）。
