# 120 · 沙箱执行的持久状态与稳定网页发布

**状态**：设计中，未实现（2026-11-10）。用户明确需求：Pi 在隔离沙箱执行，带入持久上下文和当前消息，运行后继续保存状态，网页链接长期有效。以下字段、状态机和发布规则是基于该需求的设计建议；不把现有本机会话恢复或静态交付视作完整实现。

## 动机与现状

119 定义用户/工作区/运行实例关系。本记录补齐三种独立生命周期：**会话和工作区长期保存、执行沙箱可回收、已发布网页独立托管**。

进一步的故障场景审查见 [121](121-sandbox-architecture-reliability-review.md)。本记录的接收步骤已补充同事务调度意图；Attempt、恢复组合、失联接管、独立读取服务及调试/升级契约以 121 的细化为后续实现依据，均未落地。

当前代码中可复用的基础和差距：

- `web/server/lib/piRunner.ts:543` 设置 .pi-sessions 并 --continue，`:586` 读取恢复后的状态；`web/server/index.ts:1919` 根据 hasConversationContext 决定是否注入历史。已有原生会话时不重复把全量历史拼成新用户消息，这一原则继续生效（089）。
- `web/server/lib/traceExport.ts:324` 追加运行事件，但会吞掉写入错误，且没有形成事务提交和已确认持久化语义；不能当作多用户任务的可靠队列或提交日志。
- `web/server/lib/delivery.ts:82` 校验交付清单，`:126` 分配随机 ID，`:128` 建暂存目录，`:160` 完整复制后 rename，`:166` 返回 /p 链接；`:200` 直接服务交付副本。产物已经脱离工作区，不依赖 Pi 进程，保留该方向。
- `web/server/index.ts:389` 删除会话只改索引，没有删除已发布副本。当前每次交付都是新 ID、旧链接保留旧内容；尚无稳定站点别名、版本指针、发布权限或保留策略数据库（088）。
- `web/server/index.ts:1631` 当前浏览器连接关闭会中止任务。拟议的持久任务服务应让连接成为事件订阅者，显式取消与连接断开分开处理；此语义变化尚未实现。

## 持久状态的边界

持久化是多个关联对象，不是一个不断变大的 prompt JSON。平台身份、权限、配额、任务状态及发布路由的权威副本在受信服务端；沙箱仅获得执行所需的配置、会话与授权文件。

| 对象 | 建议字段/保存内容 | 保存位置与权限 |
| --- | --- | --- |
| Workspace | workspaceId、tenantId、ownerUserId、environmentRevisionId、storageKey、revision、leaseGeneration | 平台数据库；沙箱不能修改授权/归属 |
| Conversation | conversationId、workspaceId、activeSessionCheckpointId、lastCommittedRunId | 平台数据库；分开页面历史和 Pi 原生恢复 |
| Message / RunEvent | messageId、conversationId、role、content/attachmentRefs；runId、seq、kind、payload | 数据库或受控追加日志；用户消息先保存，事件持续写入，UI 按 seq 续读 |
| SessionCheckpoint | checkpointId、conversationId、piVersion、sessionFormatVersion、nativeSessionId、branch/leafRef、blobRef、contentHash、throughMessageId | 完整原生会话文件及索引；保留工具调用/结果、压缩记录和分支关联，不仅是最后一条回答 |
| WorkspaceFiles | 用户上传、代码、依赖清单、安装结果、证据、输出 | 私有持久卷；需要明确版本恢复时另加文件系统快照/版本存储 |
| ExecutionRun | runId、requestId、inputMessageId、baseCheckpointId、environmentRevisionId、leaseGeneration、status、lastEventSeq、resultRefs、error | 平台数据库，幂等去重；状态由受信管理服务决定 |
| ArtifactVersion | artifactId、versionId、sourceRunId、manifest、fileHashes、storagePrefix、state | 沙箱外的不可变发布文件及元数据 |
| Publication | publicationId、owner、artifactVersionId、visibility、state、canonicalPath、retentionPolicy | 平台数据库；固定 URL 映射，访问策略由发布服务执行 |

SessionCheckpoint 的精确原生格式与 Pi 版本绑定；实施时核对 Pi 保存/恢复接口，不能只凭一个自定义 messages 数组声称完整恢复。用压缩摘要帮助构造模型上下文时仍保留恢复与审计所需的原始状态。所有权/预算由平台计算，不能信任原生会话文件中的任意声明。

## 进入沙箱的执行输入（拟议）

```json
{
  "schema": "plaza-execution-input/1",
  "runId": "run_…",
  "workspaceId": "ws_…",
  "conversationId": "conv_…",
  "baseCheckpointId": "cp_…",
  "environmentRevisionId": "env_…",
  "inputMessageId": "msg_…",
  "message": {"text": "用户当前消息", "attachments": ["uploads/file.pdf"]},
  "paths": {"workspace": "/workspace", "session": "/session"},
  "leaseGeneration": 7
}
```

输入由受信管理服务生成并校验，不接受客户端指定宿主机路径。它只包含当前任务可见信息；平台主凭据、其他用户数据和发布存储写权限不进入沙箱。租约代数用于服务端核验，不是让沙箱自行获得管理权限的口令。

首版单节点直接挂载私有工作区，恢复选定 conversation 的原生会话检查点，然后通过 RPC 发送本次消息。恢复原生会话后只发送尚未处理的当前消息；已有存活 Pi 时也不得重复恢复同一轮。消息和附件需与 inputMessageId/哈希绑定，重连不能新增一轮。

挂载/恢复文件与“放入模型上下文”不同：用户文件按需读取，不把整个目录或所有原始历史塞进 prompt。多节点扩展可在执行前按版本 materialize 文件，完成后上传增量；仅给出 storageKey 不代表新节点能自动访问本地磁盘。

## 执行与提交顺序

1. 验证身份、工作区归属和配额，将当前消息、run 和待执行 job/outbox 放在同一数据库事务中提交，以 `(tenantId, workspaceId, requestId)` 去重并核对 inputHash；提交后才确认接收。可直接从 DB job 表领取；使用外部队列时由 outbox 投递和对账，不留下“DB 已成功但入队丢失”的窗口。
2. 获取单写租约，确认旧实例已停止写入后恢复工作区、环境和指定会话；启动沙箱并确认 Pi ready，再派发消息。
3. 执行期间持续保存消息、工具调用/结果及事件，并按 seq 推送 SSE。UI 增量可批量落库，但须明确已确认持久化的位置，断线后从该位置补读；不能把未提交事件声称为可恢复状态。
4. 任务结束进入 `persisting`，停止继续写入并收集一致的 Pi 会话检查点；校验并保存交付文件到发布暂存区。对恶意/后台写进程，冻结或停止运行实例后从只读视图收集，不能只依靠模型声称“写完了”。
5. 全部文件上传/复制、长度和哈希核验完成后，在数据库事务中提交 checkpoint 指针、run 结果、artifact/publication 记录及完成通知的 outbox。只在事务成功后暴露链接、发送成功终态。存储与数据库不做虚假的跨系统原子事务：先写不可变文件，后提交引用；未引用暂存由延迟回收处理。
6. 通知投递可重试；用 runId/发布幂等键去重。收尾完成后释放配额和租约，空闲沙箱可回收。下轮从已提交检查点继续。

建议状态：`queued → preparing → running → persisting → completed`，异常落 `failed/cancelled/interrupted` 并保留原因。生成成功与发布成功分别记录；若任务要求网页交付但发布失败，不发送完整成功，允许从已保存文件重试发布而不重跑模型。

**一致性边界**：直接挂载的普通工作区会在执行中逐步改变。DB checkpoint 提交并不能回滚这些文件；必须记录中断状态并在恢复时处理。若要求文件也按轮次全成或全败，需每次运行的写层/快照及提交机制另行实现。接管只改变数据库租约不能阻止旧容器继续写同一卷，故必须停止旧写者或用存储层 fencing/隔离写层后再调度。

当前消息在执行前保存可以避免“用户输入消失”，不能自动保证外部副作用 exactly-once。工具产生外部写操作后若确认丢失，应核对幂等键/状态再恢复，不能盲目重放。

## 网页链接的生命周期

稳定地址的目标是：**任务完成、沙箱销毁、下一轮执行、服务重启及受控迁移，不改变已发布网页地址和内容**。是否公开和是否撤销是独立权限状态；长期可用依赖域名、托管、存储与备份的持续维护，不承诺物理意义上的永不故障。

- 默认沿用 088 的“每次发布独立版本”：历史回答里的 URL 指向当时完整的 HTML/CSS/JS/图片/JSON。更新报告产生新版本，不悄悄替换旧回答的内容。
- 发布服务从沙箱外的专用目录或对象存储读取；执行沙箱不得挂载发布存储为可写。生产可独立部署静态服务/网关/CDN，首版本地实现可复用现有路由，但存储寿命必须独立。
- 首版可规划 `/home/wlc/data/gvisor/workspaces/…` 与独立 `/home/wlc/data/plaza-publications/…`；这是目标路径，不表示本机 DELIVERIES_DIR 已迁移。数据盘持久化不是备份，发布资产及路由数据库须有独立备份和恢复演练。
- 对外固定域名/路径，不暴露容器 IP、临时端口或临时文件地址。不把带到期时间的对象存储签名 URL 作为用户收藏的长期链接；私有网页由稳定入口鉴权，再通过代理或短期授权读取内容。
- 网页发布必须包含完整依赖并使用版本内相对路径。若后续增加“同一地址看最新版”，用独立 siteId 指向 immutable version；入口重定向到版本目录，CSS/图片也固定该版本，防止读到新旧混合内容。切换指针用事务/条件更新，并处理缓存。默认版本链接继续不变。
- 运行临时文件、工作区、会话、发布作品分别回收。清理沙箱或删除聊天不能隐式删除已发布作品；显式删除/撤销作品由所有者确认并应用独立保留政策。发布存储的生命周期规则不得清理仍有效 URL 引用的对象。
- 固定地址不等于公开无权限：允许 private/shared/public 策略；私有作品每次检查授权。历史持链接公开产物保留既有语义，新多用户入口默认私有，公开分享需明确操作。隔离用户网页 origin/CSP 与主站权限。
- “始终有效”先覆盖自包含静态网页。依赖 Python/Node 后端、数据库或外部 API 的网页需要另外部署持续服务/按需唤醒服务，不能依赖已回收的任务沙箱。

## 成本与取舍

- 仅在运行成功后保存：实现简单，但异常丢输入/过程；采用先存输入、过程增量、结束提交。
- 每轮把完整持久结构拼到 prompt：既重复原生会话又占用上下文，且容易混淆数据和权限；采用引用/挂载、原生恢复、当前消息增量。
- 网页直接服务工作区：无需复制，但容器回收、目录修改和后续运行破坏旧链接；保留独立发布副本，接受存储开销。
- 固定 URL 直接覆盖原目录：会暴露半成品或新旧混合资源；采用不可变版本和提交后的发布引用。
- 从第一版实现分布式文件系统、任意快照及完整事务：成本高；单写私有卷 + 可靠元数据/检查点 + 独立发布先落地，明确中断后文件状态不是自动回滚。

## 验证与后续路线

本次核对源码、088/089/119 和官方存储文档；相对链接、引用源码位置、120 编号唯一性、索引下一号 121、必需章节、代码围栏及 diff 格式检查通过。未变更 Pi、SSE、Docker、存储目录或线上网页，未执行运行恢复或发布故障注入验收。

实施顺序：持久对象/幂等入队 → 指定 Pi 检查点恢复及单写租约 → 容器通道与增量事件 → 收尾提交/outbox → 独立发布与访问策略 → 再考虑版本别名及多节点文件恢复。

待验收：输入确认后崩溃仍可查；指定会话恢复不重复消息；停止任务/连接断开语义正确；旧 worker 不能继续写入或提交；发布到一半不可见；提交成功但 SSE 丢失后能重查结果；删容器、回收工作区、重启/迁移发布服务后旧页面及所有资源仍有效；旧网页不因修改而变；访问权限与撤销生效；备份可恢复完整资产和 URL 映射。断电耐久性要验证实际提交/fsync/存储配置，不能用普通进程退出代替。

## 参考

- [Docker Volumes](https://docs.docker.com/engine/storage/volumes/)：持久卷与容器生命周期分离。
- [Amazon S3 预签名 URL](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)：访问授权有期限，不能直接用作长期发布地址；不代表选定 AWS 为存储产品。
- 项目：[088 网页交付](088-artifact-presentation-and-web-hosting.md)、[089 会话恢复](089-conversation-restart-and-delivery-permissions.md)、[119 多用户工作区](119-multi-user-gvisor-workspaces.md)。
