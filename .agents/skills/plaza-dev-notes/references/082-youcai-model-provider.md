# 082 · 自部署 youcai 模型接入

**状态**：已实现（2026-10-30；真实无密钥服务、低权 Pi 读写工具、项目 HTTP/SSE、实际出站请求头和思考开关验证通过，18 项回归与构建通过）。长报告质量、上下文溢出、取消及图像输入仍待专项验证。

## 动机

用户提供自部署模型 `youcai` 和服务文档地址，明确无需 API Key。现有项目通过 Pi RPC 运行，且部署为 `sudo -u plaza-sandbox`；仅设置 OpenAI 客户端环境变量无法在 Pi catalog 中登记新模型，修改开发用户的全局模型配置也不会自动作用于低权用户。

## 约定细节

- 模型路由仍使用 `PI_MODEL=provider/model`；本次为 `youcai/youcai`。`web/server/lib/piRunner.ts:530` 初版仅在 provider 为 `youcai` 时显式传 `--extension <repo>/web/server/pi/youcai.js`。保留 `--no-extensions` 的自动发现关闭行为和 075/078 的上下文、低权用户边界。
- `web/server/pi/youcai.js:5` 注册 `youcai`，API 类型为 `openai-completions`，复用 Pi 的消息转换、流式、工具结果、usage、取消机制；没有引入第二个模型执行引擎。
- 默认 `baseUrl` 为 `https://u496025-7845e5610890.bjb2.seetacloud.com:8443/v1`，请求路径为 `/v1/chat/completions`。可用 `YOUCAI_BASE_URL` 覆盖（`web/server/pi/youcai.js:9`）；值须包含 `/v1`，从 `web/.env` 读取时保持外部环境优先。低权部署将覆盖值放在 `web/.env`，不增加 sudo 环境透传项。
- Pi / OpenAI SDK 要求非空 API Key，内部使用非凭据占位值 `unused`（`web/server/pi/youcai.js:12`）。`authHeader: false` 本身不会阻止 SDK 默认 Bearer 头，因此还通过 `before_provider_headers` 将所有大小写形式的 Authorization 显式设为 `null`（`:31`）。仅作用于 `ctx.model.provider === 'youcai'`，切换其他 provider 时保留其认证头。
- `/v1/models` 无认证请求实测返回 `id=youcai`、`owned_by=vllm`、`root=./qwen3.5-27b-gptq-int4-vl`、`max_model_len=262144`。登记上下文 262144，输出上限 8192 为本项目保守配置，不声称这是服务的最大输出能力；当前仅登记文本输入（`:18-23`）。
- `compat.thinkingFormat='qwen-chat-template'`（`:25`）：Pi 将 `PI_THINKING=off` 转为 `chat_template_kwargs.enable_thinking=false`，其余允许档位开启思考，档位不表示不同推理预算。未覆盖时保留项目 medium 默认。
- 自部署 token 费率登记为 0，表示无第三方 token 账单，不涵盖 GPU/云主机费用。模型与上下文信息继续通过原有 trace 和 usage 字段传递。
- 配置与运维说明：`web/.env.example:34`、`web/docs/pi-runner.md:76`。`web/server/scripts/detectCli.ts:27` 对 youcai 显示无需 Key；`web/server/index.ts:1465` 的启动日志同步区分认证方式。本机忽略的 `web/.env` 已将 `PI_MODEL` 切为 `youcai/youcai`，原 provider 凭据保留。

## 成本与取舍

- 初版选择按需加载的仓库 provider，使普通用户和低权 Pi 共用同一代码，且不修改 `~/.pi`、`/opt` 或 sudoers。否决修改全局 `models.json` / `PI_AGENT_DIR`：它们需要同步两个用户的目录，并容易影响既有认证与设置。
- 否决重写 OpenAI SDK 客户端或直连模型替代 Pi：会重复实现工具循环、会话、流式和 trace。扩展只声明模型与认证差异。
- 使用 Pi 已安装版本提供的 `qwen-chat-template` 与请求头钩子；本机低权运行时 v0.87.1 已实测。旧版 Pi 若不支持这些接口需先验证/升级，不将兼容性推定为已完成。
- 服务地址与上下文元数据是当前部署快照；迁移地址用配置覆盖，换模型/上下文需重新核实。图像能力不依据目录名推定为已经验证。

## 验证

- 无认证 `curl`：`/openapi.json` 返回 200；`/v1/models` 返回 youcai 与上述元数据；普通 Chat Completions 返回 `youcai-ok`，SSE 返回文本、usage、`[DONE]`；自动工具选择返回 `ping({text:'tool-ok'})`。
- `PI_THINKING=off node /tmp/plaza-youcai-probe.mjs`：通过项目 `PiRunner` 和实际 sudo 包装脚本运行，写入并读回 `youcai-probe.txt`，最终回复 `youcai-tool-ok`，trace 记录 2 次工具调用、provider/model=youcai、上下文 262144。该脚本为本次临时探针，非仓库接口。
- `node /tmp/plaza-youcai-wire-probe.mjs`：实际 Pi 请求发往本机模拟 HTTP 服务，off/medium 两档均不含 Authorization，思考开关分别为 false/true。该临时探针覆盖 SDK 层，避免只凭扩展注册对象判断请求头。
- `npm run detect:cli`：显示低权包装脚本与 `PI_MODEL=youcai/youcai`，无需 Key。
- 项目后端 `/api/health` 回报 `youcai (youcai · pi)`；`POST /api/chat` 的 general 请求以默认 medium 思考完成 started→session→thinking→text→usage→done，最终 `youcai-api-ok`。运行标识以 trace 为准，不为单次测试另立运行记录主题。
- `node --test web/server/pi/youcai.test.mjs web/server/lib/conversation.test.mjs web/server/lib/pdfReport.test.mjs web/server/lib/docFigures.test.mjs`：18 项通过；认证隔离 3 项覆盖大小写头移除、切换 provider 和迁移地址覆盖。
- `cd web && npm run build`：通过。服务端另用 Node 语法检查覆盖最终入口改动。

## 后续扩展路线

- 用真实业务长报告核对内容质量、工具稳定性、延迟与输出上限，再决定是否提高 maxTokens。
- 如需图像能力，先验证普通图片与工具返回图片，再登记 `image` 输入。
- 专项验证取消、上下文溢出、断流与自动重试；复用 Pi 已有实现不等于这些场景已对当前部署实测。
- 需要更多自部署模型时再提取通用 provider 配置，不因单个服务预建动态模型管理系统。

## 2026-11-03 在线对话切换模型（已实现）

原体验页菜单包含模拟选项，发送时始终使用服务的全局模型。现在每次发送都能独立指定提供方，同一对话沿用当前 Pi 进程、工具上下文及附件目录。

- `web/server/index.ts:88` 维护两个服务端别名。健康接口（同文件第 255 行）返回 `chatModels: [{id,name}]` 与 `defaultChatModel`。网页默认匹配配置的提供方，否则选 DeepSeek。DeepSeek 优先复用部署配置的 DeepSeek 型号，否则为 `deepseek/deepseek-v4-pro`。优才使用 `youcai/youcai`。
- `POST /api/chat` 在 `web/server/index.ts:681` 校验可选 `model`，接受 `deepseek`、`youcai`，其他值返回 HTTP 400。省略字段及 OpenAI 兼容入口继续使用部署默认模型。已有 SSE 帧可直接复用。
- `web/server/lib/piRunner.ts:545` 在创建每个 Pi 会话时显式注册仓库 youcai 扩展，取代初版的按提供方加载。保留禁用扩展自动发现和按 provider 隔离认证头的规则。启动选定模型或恢复会话后，每轮先核对会话状态，再按需发送 `set_model` 并检查 Pi 返回的 provider/id（第 244 行），确认后才发送 prompt。会话标识互斥覆盖异步创建和换模（`web/server/index.ts:973`），相互独立的会话各自选模型。
- `web/src/pages/ExperiencePage.vue:1101` 使用原生有标签的下拉框与现有明暗主题令牌，键盘或触屏均可选择，运行时禁用。第 435 行把当前选择传给真实聊天请求。旧服务未声明能力时仅展示其模型，离线显示演示模式。
- 运行用量与环境快照记录本轮模型。恢复对话时按最近运行选中模型；历史回答的标签仅在原始输入与轮次数量吻合且有成功运行的提供方记录时显示（`web/server/lib/conversation.ts:63`）。历史数据未记录提供方时不补猜。

**取舍与后续。** 统一注册一个本地扩展，换取同一会话内即时切换。重建进程会额外付出启动与重载成本；修改全局环境变量会让其他用户的请求串用提供方。若以后加入新模型，先验证 Pi 工具、鉴权与可切换性，再扩充服务端白名单。当前验收限于短对话，跨模型长报告质量仍待专项验证。

**验证。** 50 项服务端、HTTP/SSE、提供方与前端回归通过（含 Chrome 交付测试），Vue 类型检查与 Vite 构建通过。在使用实际低权 Pi 与单独 trace 目录的 390px Chrome 会话中，先选 DeepSeek 发送口令，再选优才追问，第二轮正确复述；两条记录的 clientSessionId 和 engineSessionId 均相同，环境快照分别为 `deepseek/deepseek-v4-pro` 和 `youcai/youcai`。重启验证服务、重新进入历史对话后，两条回答保留各自的模型标签。现有 4188 页面加载新的模型列表，窄屏深色布局无横向溢出。


### Flash / Pro 型号与弹出菜单修订（已实现）

用户要求区分 DeepSeek 型号并恢复原弹出式菜单。第 49–52 行记录的双选项与原生下拉框由本节替代。

- `web/server/index.ts:91` 按低权 Pi catalog 公布 `deepseek-flash → deepseek/deepseek-flash`、`deepseek-pro → deepseek/deepseek-v4-pro`、`youcai → youcai/youcai`。健康接口提供 `{id,name,provider,modelId}`，默认按完整路由匹配部署配置，否则用 Pro。原 `deepseek` API 别名保留旧路由语义。
- `web/src/components/ChatModelPicker.vue:7` 在输入栏使用紧凑文字触发器与向上弹出的三个互斥菜单项，选中项带对勾；支持方向键、首尾键、回车、Esc、移出焦点或点击外部关闭。窄屏触摸菜单项增高。继承现有亮暗令牌。`ExperiencePage.vue:628` 恢复时按 provider 与型号匹配每条回答和最近选择。
- 单层菜单减少选完提供方再选型号的一步操作，代价是自行实现并验证键盘与焦点管理。更多提供方出现后再评估分组。

真实低权 Pi 目录确认两个 DeepSeek 标识。390px 浏览器选 Flash 调用 bash、切 Pro 复述上轮命令输出，实际运行记录为对应的两个 modelId。刷新重开同一对话，历史标签分别为 Flash / Pro，菜单回到 Pro；窄屏深色、键盘选项和 Esc 关闭通过。
