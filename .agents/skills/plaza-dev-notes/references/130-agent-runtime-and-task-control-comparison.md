# 130 · ZCode 与 Claude Code 的隔离和多 Agent 调度对照

**状态**：源码调研完成，接入建议待实现（2026-11-24）。本地 ZCode 源码快照根包标为 3.18.2、CLI 包标为 0.17.1。Claude Code 是标为 2.1.88 的第三方拆包快照，README 标注缺失部分功能模块。对照 Claude 官方文档核实公开行为。两个参考目录没有 Git 元数据，ZCode 的 freshness 检查因此不能比较远端基线。本次证据来自源码和文档，没有启动两套参考程序或执行其工作流。

## 动机

[129](129-sandbox-v2-greenfield-migration.md) 提出了运行 Worker、按轮隔离、检查点和短时保留环境。这里区分三种状态的所有者：Agent 上下文归会话，任务准入和生命周期归调度器，宿主机文件与网络边界归隔离运行时。参考路径均相对于用户指定的两个源码目录。

## ZCode

| 层级 | 核对结果与位置 |
| --- | --- |
| Shell 工具 | 工具层做 Bash 权限判断，普通执行链由 Node 用工作目录与环境启动子进程，并有进程树停止逻辑。查看 `apps/zcode-cli/packages/core/src/tool/handlers/bash.ts:401`、`apps/zcode-cli/packages/adapters/src/exec/node-execution-adapter-run.ts:327` 和 `node-execution-adapter-process.ts:125`。在已跟踪的执行链未发现每个 Agent 由 Docker/runsc 启动。 |
| Dynamic Workflow 脚本 | Workflow harness 用单独的 Node 子进程运行脚本，脚本在 VM 上下文中通过受限宿主接口与父侧引擎通信，harness 与 child 走 NDJSON。脚本隔离和工作流 Actor 的执行边界分开。设计明确说明 Node VM 不能作为不可信代码的安全边界。查看 `apps/zcode-cli/packages/dynamic-workflow-runtime/src/harness.ts:286`、`src/child-source.ts:390` 和 `apps/zcode-cli/packages/dynamic-workflow/docs/execution-engine.md:91`。 |
| 准入与常驻 | 单会话输入由 `CommandInbox` 串行准入。Workflow 节点有本次运行的并发控制，模型层另按 provider/model 做每次请求的准入和跨 run 轮转。会话池用 idle TTL、LRU 和操作租约回收空闲会话，后台在途工作阻止回收。查看 `apps/zcode-cli/packages/bootstrap/src/zcode-protocol-v4/command-inbox.ts:164`、`src/app/workflow-concurrency-governor.ts:2`、`src/zcode-protocol/session-resident-pool.ts:151`。 |
| 终止与继续 | 当前 Dynamic Workflow 的 cancel 向运行的尝试发 abort，停止在途 ask 并结束脚本进程。按原因结算为 stopped。可续跑的记录重新启动执行器，从 journal 恢复，已结算节点按身份和输入验证命中记录。老脚本 Workflow 另有 paused 与终态 cancelled 的语义。查看 `apps/zcode-cli/packages/bootstrap/src/app/dynamic-workflow-run-service.ts:590`、`src/app/dynamic-workflow-run-submit.ts:427`、`apps/zcode-cli/packages/dynamic-workflow/src/engine/scheduler.ts:155` 和 `apps/zcode-cli/docs/design/v2/workflow-failure-recovery.md:25`。运行结算与子 Agent 全部停止写入有时间差，文档为修订续跑设有等待安静的步骤。查看 `apps/zcode-cli/packages/dynamic-workflow/docs/execution-engine.md:666`。 |

## Claude Code

| 层级 | 核对结果与位置 |
| --- | --- |
| 命令沙箱 | `sandbox-adapter.ts` 把配置和权限映射成文件、网络规则。Shell 启动前按需经 `SandboxManager.wrapWithSandbox` 包装命令。官方文档确认 macOS 使用 Seatbelt，Linux/WSL2 使用 bubblewrap 与 socat。该边界覆盖沙箱化 shell 及其子进程。原生文件、Web 工具等另有权限规则。查看 `src/utils/sandbox/sandbox-adapter.ts:172`、`src/utils/Shell.ts:259` 和 [官方沙箱文档](https://code.claude.com/docs/en/sandboxing#what-runs-outside-the-sandbox)。 |
| 普通子 Agent | 同一 CLI 内运行独立模型上下文，可前台或后台。相关工具权限按 Agent 上下文组织；可选 Git worktree 负责分开工作目录和代码修改，不负责内核、网络隔离。后台 Agent 有自己的取消信号；`TaskStop` 按任务类型调用停止实现，Agent 收尾清理自己启动的 shell。续跑可加载 Agent transcript。查看 `src/tools/AgentTool/AgentTool.tsx:582`、`src/tools/AgentTool/runAgent.ts:698` 与 `:847`、`src/tasks/stopTask.ts:38` 和 `src/tools/AgentTool/resumeAgent.ts:63`。 |
| Agent Teams | 队友可以进程内运行或由 pane 后端启动 CLI。共享任务文件用锁领取，检查 owner 与前置依赖。进程内队友工作结束后保持 idle，等信箱消息或领取可运行任务，当前工作被中断也可回到 idle。协作退出通过 shutdown request/response，另有强制停止。查看 `src/utils/tasks.ts:541`、`src/utils/swarm/inProcessRunner.ts:624` 与 `:689`、`src/tools/SendMessageTool/SendMessageTool.ts:268` 和 `src/utils/swarm/backends/PaneBackendExecutor.ts:295`。官方文档说明进程内队友不会随主会话 resume 恢复。参见 [Agent Teams 文档](https://code.claude.com/docs/en/agent-teams#limitations)。 |

## 广场接入建议

- **任务和执行实例分开**：沿用 129 的 `Workspace / Run / Attempt`，需要编排时再加 `RunStep(parentRunId, stepId, dependsOn, resultRefs)`。PostgreSQL 保存准入、归属、状态版本、当前 attempt、检查点和事件。常驻 Worker 读取已放行且依赖完成的步骤，先占租户/工作区执行名额，再分配 runsc 实例。模型网关另外负责 provider/model 的请求限额。Claude 的文件锁适合本地协作，ZCode 动态引擎也明确限定了跨进程同时持有同一 run 的支持范围（`execution-engine.md:637`），广场用数据库事务和 attempt 租约处理跨进程领取和旧实例晚到的回执。
- **保留三种独立控制**：暂缓派发任务，业务安全点挂起或等待人工输入，停止当前 attempt 并核验容器退出。等待人工确认的任务持久保存问题、已提交结果及恢复信息。运行中止后过期 attempt 不可提交，复跑只从已提交结果继续，外部写动作由回执和幂等键管理。SSE 断开只结束订阅。容器冻结可作为短时运维操作，保留此前对上游请求和资源占用的限制。
- **按独立停止粒度分配容器**：同一任务的上下文切换不必启动多个容器。要求分别暂停、终止或隔离写入的步骤使用各自的实例与工作目录，协调者汇总已提交结果。父任务取消时，由调度器向登记的子步骤传播停止并核实实际回收。用户数据所在实例始终限同一工作区。会话快照保存后可回收空闲实例，T03 的实测耗时再决定是否提供有 TTL 和容量上限的复用。
- **验收示例**：T03 的本地语料对标和标准核对可各自使用只读输入并行完成。两份结果提交后由主步骤合并。若需要用户决定或补证，提交已有材料后释放运行资源。故障测试覆盖重复领取、取消一个步骤时其他步骤继续、工作区单写和父任务取消后的子实例回收。

ZCode 的 VM、Claude Code 的 worktree 和本地队友进程解决脚本调度、代码工作区或会话协作问题。广场的公网执行仍沿用 runsc 沙箱、受控挂载、网关和服务端授权。首期不必引入完整的 Dynamic Workflow 脚本平台或 Agent Teams 信箱，先按 129 打通任务队列、检查点和取消，再加依赖步骤、并发控制及可选的短时保留。
