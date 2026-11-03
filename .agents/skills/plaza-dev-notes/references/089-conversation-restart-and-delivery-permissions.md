# 089 · 服务重启后的对话恢复与低权产物交接

**状态**：已实现（2026-11-03；公网历史与下载恢复、真实低权打包/Pi 无模型恢复探针通过）。

## 动机

在线真实运行暴露两个持久缺陷：同一 clientSessionId 在服务重启后有不同 engineSessionId，历史接口只读取最新引擎 trace，导致页面只剩最后一轮；Python 的 NamedTemporaryFile/mkdtemp 默认权限为 0600/0700，低权 plaza-sandbox 写出的清单与网页目录不可被后端 wlc 读取，deliveryFingerprint 又吞掉 EACCES，运行被错误标为成功且无交付按钮。此前同用户测试未覆盖实际用户隔离边界。

## 约定与接入点

- `web/server/lib/conversation.ts:31` 的 deriveSessionConversation 按 **clientSessionId + 不晚于所选运行** 收集记录。相同 Pi 原生 `trace.session.id` 的累计快照只投影一次；旧记录回退 engineSessionId/runId。不同原生会话合并显示，重启恢复同一原生会话不会重复消息。先归集标识，允许后续完整快照恢复先前丢失的 trace。缺失/空 trace 保留已持久化的用户输入与交付链接，不编造回答。原始输入数量一致时才按顺序覆盖，沿用 080 的保守边界。
- `web/server/index.ts:393` 详情接口使用整段对话投影，原 `item` 和原始 `trace` 仍属于所选 run，不改写证据文件、不扩大到其他 clientSessionId。交付数组仍留在各自原轮次。
- `web/server/lib/piRunner.ts:525` 创建 RPC 进程带 `--continue`，由 Pi 从本工作区 `.pi-sessions` 恢复最近持久会话；不存在则新建。`hasConversationContext`（`:223`）读取 get_state.messageCount 并在 prompt 接收后更新。`index.ts:1474` 在此后决定 OpenAI 全历史是否拍平，避免服务内存为空时将完整历史再塞入已有持久上下文。
- 模型恢复与页面恢复是两个边界：模型只恢复最近 Pi 分支；旧版本已经分裂的原生分支可在页面合并，不宣称把全部旧工具上下文注入当前模型。持久 session 丢失时仍只能新建，旧 UI 历史以 traces 为准。
- `pack_delivery.py:23` 为公开网页临时目录增加共享组读/穿行，保留 setgid；`:51` 交付清单以 0640 生成后原子替换。实际 Linux 得到 `plaza-sandbox:plaza-run` 的 2750 site 和 0640 清单，后端 wlc 属于 plaza-run。仅公开交付调整权限，内部证据不因此公开。
- 通用沙箱交付说明和 `docs/agent-api.md` 同步共享组权限要求，其他生成技能同样遵守，不依赖对全工作区放宽权限。
- `web/server/lib/delivery.ts:48` 指纹仅将 ENOENT 视为没有文件；其他读取错误保留 unreadable 状态，`:63` 明确抛出读取权限错误，即使该不可读清单在本轮之前已存在。沿用终态 failure/error 展示与索引，不再静默成功。
- 为既有坏交付做一次性恢复时：重新打包已验证的本地报告，以正常发布函数保存产物，链接补入**原生成运行**，events 追加维护 note 说明时间与原因。不伪造新的模型/数据库运行，不批量搬动或公开工作区。

## 验证

- 101 项共享查询、报告、会话、交付与 HTTP/SSE 回归通过，含 Chrome 沙箱验证。新增覆盖跨引擎合并、恢复同一原生累计快照去重、缺失/空 trace、旧 trace 缺失后恢复、不可读旧清单明确失败。
- HTTP 集成通过真实服务重启验证：Pi 确定性传输保留原生上下文；OpenAI 带全历史续聊不重复注入；删除模拟 Pi 持久会话后，历史仍同时保留旧与新引擎的消息和原下载链接。无模型/数据库调用。
- 实际 `sudo … pi-sandbox` 低权打包成功，后端实际读取并发布；真实 Pi RPC 无 prompt 探针恢复原有 native session ID 与用户轮数，没有请求模型。
- 公网正常在线对话页面点击原会话，恢复 4 条用户消息与 4 条 AI 区块，报告回答下有打开网页、复制链接、下载；刷新页面再选会话仍恢复。网页、11 张资源图片、ZIP 均返回 200，ZIP 为 attachment。验收摘要在忽略目录 `web/server/traces/delivery-history-repair-20261103.json`，没有重新查库。
- Vue 类型检查与生产构建、Node 语法检查、wechat-report Skill 校验通过。没有重跑新的长模型报告任务。

~~~bash
DELIVERY_BROWSER=/usr/bin/google-chrome node --experimental-strip-types --test scripts/talent-data/*.test.mjs web/server/lib/*.test.* web/server/delivery-api.test.mjs web/src/composables/useChatApi.test.mjs
(cd web && npm run build)
node --experimental-strip-types --check web/server/index.ts
python3 /home/wlc/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/wechat-report
~~~

## 成本与取舍

复用现有索引、trace 和 Pi 原生持久会话，不引入另一套聊天存储或把工程提示/工具输出拼成用户消息。否决删除旧记录、强制开新对话、仅改前端缓存和移动整套产物目录：均未解决真实原因。页面投影需要读取本会话历史快照；超长会话的 I/O 优化未做。共享组是当前 Linux 部署前置条件，其他部署用户关系需保持一致。

## 后续扩展路线

若真实长会话读取成为瓶颈，再保存显式轮次 ID/原生会话 ID 并只读取必要快照；若需要跨已分裂分支恢复模型上下文，另行定义有界交接，不能把 UI 合并当成模型状态恢复。部署回归保留跨系统用户的打包/读取验证，不以同用户临时目录测试替代。
