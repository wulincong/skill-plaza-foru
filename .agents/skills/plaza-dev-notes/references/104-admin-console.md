# 104 · 独立管理后台与运行控制

**状态**：已实现并在当前部署启用。适用于 Vue + Node/Pi 主应用。本条更新 048 的目录回退策略、072/077 的历史访问边界及 082 的模型默认值来源。

## 动机

运营人员需要在运行中上下架技能、选择模型和轮换凭据。原运行列表与完整工具入参、输出及原始文件使用同一组公开 API，公开对话侧栏也能枚举所有会话。管理和使用必须分别授权，同时保留已有 trace 和原生 Pi 续聊。

## 约定与接入点

- 网页入口为真实路径 `/admin`，后台使用 history 路由，广场继续使用 hash 路由。旧的 `#/runs/:runId?` 跳转至后台并保留深链。见 `web/src/router/index.ts:23`、`web/src/admin/routes.ts:3`。登录卡、工作台、设置分组、发布开关及表格采用 Zero4-UI 参考设计，适配明暗和移动端。
- `web/server/scripts/adminAccount.ts:1` 仅在服务机初始化或重置单管理员。后端以独立 SQLite 文件存储 `account(username,salt,hash)`、`sessions(token,expires)`、`configuration(data)`。密码使用随机盐和 scrypt，随机 256 位会话令牌仅存摘要，八小时到期。改密或重置事务内撤销全部会话。`web/server/lib/adminStore.ts:136`、`:211`，`web/server/lib/adminApi.ts:20`。Cookie 为 HttpOnly、SameSite=Strict、路径 `/api/admin`，HTTPS 下启用 Secure。修改接口校验来源、JSON 和专用请求头。
- 配置字段为 `revision / runtimeRevision / disabledSkills / settings / activeKey / keys`。写入带版本号，过期返回 409。技能限已注册的专业技能，通用智能体及内部开发技能不作为卡片上下架。首页、广场、表单深链、聊天选择器读取公开目录；入口不可达时显示空态。服务端在目录、网页入口和兼容入口统一验证发布状态，Pi 只加载显式声明的技能。见 `web/src/composables/catalog.ts:9`、`web/server/index.ts:290`、`:706`、`:785`、`web/server/lib/piRunner.ts:547`。
- 设置含默认模型、前台选模权限、思考档位、公众号报告使用优才时的可选专属档位、优才地址、两类任务超时及会话空闲回收。初始值继承部署配置，保存值持久化。CLI、目录、系统用户和数据库连接仍属于部署层。网页可选模型和默认值从健康接口取得。兼容 API 的 `skill` 字段语义保留，默认路由与网页一致。每轮固定一份配置，原运行完成后再应用凭据和进程配置变更，沿用工作目录及 Pi 的持久会话。见 `web/server/lib/adminStore.ts:154`、`web/server/index.ts:1128`。
- DeepSeek 有部署凭据和命名密钥两种来源，后台只返回命名密钥的 ID 和名称。使用命名密钥时，Node 为 Pi 进程开启独占的回环转发地址，只接收带随机路径的 Chat Completions POST。后端向固定上游加入选定凭据，拒绝重定向，沙箱参数、环境及 trace 不包含此命名 Key。Pi 退出时关闭转发。优才保留无认证调用。见 `web/server/lib/modelRelay.ts:8`、`web/server/lib/piRunner.ts:563`、`web/server/pi/youcai.js:6`。数据库及其备份包含可恢复的模型密钥，必须以服务账号私有权限保存。
- 全站 `/api/admin/runs` 从原索引读取，支持查询、分页、归档、恢复、删除索引和导出文件。无 trace 的旧记录显示已保存摘要。旧 `/api/runs` 返回 401。浏览器向对话、附件、恢复及 `/api/conversations` 发送本地随机能力值，服务器用摘要命名空间分隔公开会话，返回用户视图；其他能力值无法读写该会话。旧数据没有浏览器归属，只在后台列出。交付物链接仍按原协议分享。见 `web/server/index.ts:345`、`web/server/lib/browserHistory.ts:6`、`web/src/composables/browserHistory.ts:3`。Vite 禁止直接静态读取 server 目录，运行目录收紧为 0700，见 `web/vite.config.ts:25`、`web/server/lib/traceExport.ts:23`。

## 成本与取舍

SQLite 利用现有 Node 运行时，在单服务进程下持久化设置和登录状态。拒绝直接网页编辑 .env，其内容原本供低权查询工具读取，而且重启会干扰运行中的任务。密钥转发为每个使用命名凭据的 Pi 进程增加一个本地监听端口，换取真实密钥停留在服务端并避免 Pi 本地鉴权优先级意外覆盖选中的 Key。保留单管理员及匿名浏览器历史，避免猜测旧会话所有者或把前台演示手机号当作身份凭证。

## 验证

- Vue 类型检查和 Vite 生产构建通过。74 项 Node 回归通过，覆盖登录授权、旧入口封闭、双协议上下架、配置持久化、改密撤销、跨浏览器访问拒绝、历史与交付兼容，参见 `web/server/delivery-api.test.mjs:332`。独立回环转发测试核对两组出站请求头、可用路径及错误响应，见 `web/server/lib/modelRelay.test.mjs:7`。
- 真实 Pi 0.87.1 经部署的低权 sudo 包装器，在隔离目录与本地协议上游完成同会话 Pro → Flash → 优才。两把临时命名 Key 分别出现在正确的出站请求，优才没有 Authorization，所查 trace 中没有命名 Key。该项验证线路与轮换，不衡量第三方模型回答质量或计费。
- Chrome 验证后台深链登录、技能下架后的列表及直接入口、配置保存、凭据启用和移除、退出与旧链接迁移。390px 暗色六个主页面无整页横向溢出。用户侧 Chrome 发送真实 Pi 请求至本地验证上游，刷新恢复对话，归档后由管理员查看完整时间线并恢复，清除浏览器身份后列表为空；改密后重新登录通过。部署验收时索引共 196 条，其中 184 条有可解析 trace，12 条只有索引或本地结果。管理员可打开旧记录及原始文件，匿名请求被拒；Vite 文件路径和 /@fs 路径都返回 403。

## 后续扩展

若需要多人运营，再拆分账号与角色、增加个人操作审计。如果迁移到多实例，应把配置修订与会话进程编排统一到共享存储，并为密钥增加独立的密钥管理服务。公网 HTTPS 终止和进程托管由部署层配置。
