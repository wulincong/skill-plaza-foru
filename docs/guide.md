# 在线运行与 API 指南

在网页上提交任务，或从自己的应用调用智能体。两种方式都由平台执行任务，完成后可以查看回答和交付文件。

## 在线运行

打开在线对话即可提问。需要专业能力时，在输入框键入 `$` 并选择技能。也可以在广场点击「在线运行」，按提示填写任务或上传资料。完成后，在当前对话中查看回答和交付文件。

[打开在线对话](#/experience) · [浏览智能体广场](#/skills) · [按技能查阅文档](#/docs)

## 通过 API 接入

从应用后端向平台发送 HTTP 请求。当前接口无需 API Key。使用 OpenAI 兼容客户端时，将 Base URL 设为 `http://biubiubiu.vip:18767/v1`，并在请求体中传入 `skill`。

### 选择智能体

通用问答使用 `general`。运行下面的命令，从返回的 `skills[].id` 取得专业技能的标识，例如就业指导的 `career-guidance`。

```bash
curl http://biubiubiu.vip:18767/api/skills
```

### 发送第一条消息

把下面的命令复制到终端即可发起一次问答。调用其他智能体时，替换 `skill` 和问题。`messages` 的最后一条须是 `user` 消息，内容为非空文本。

```bash
curl http://biubiubiu.vip:18767/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "skill": "general",
    "messages": [
      {"role": "user", "content": "请用一句话说明岗位调研前要准备什么。"}
    ],
    "stream": false
  }'
```

### 读取回答与交付文件

默认返回 JSON，从 `choices[0].message.content` 读取回答。报告任务的正文可能为空，同时检查顶层的 `webLinks[].url`（打开网页）、`downloads[].url`（下载文件）和 `reportUrl`（报告地址）。相对地址以 `http://biubiubiu.vip:18767` 为基准解析。

## 接入时的常见问题

### 如何流式读取长任务？

把 `stream` 改为 `true`，使用 curl 时加上 `-N`。按 SSE 事件读取并拼接 `choices[0].delta.content`。当 `choices` 为空数组时，读取顶层的交付链接或用量。收到 `finish_reason: "stop"` 后继续读取，直到 `data: [DONE]`。遇到 `error` 帧时读取 `error.message`。

### 如何继续同一段对话？

首次请求时由客户端生成一个随机 UUID，作为 `sessionId` 保存。后续请求沿用同一 `skill` 和 `sessionId`，只发送最新一条用户消息。同一会话等本轮结束后再发下一轮。

### 如何提交附件？

先向同一 API 服务的 `POST /api/upload` 发送 JSON，传入 `filename` 和 Base64 编码的 `dataBase64`。在对话请求中使用上传响应的 `sessionId`，并把返回的 `name` 和 `path` 放进 `attachments` 数组。向已有会话上传时，上传请求也要带上该会话的 `sessionId`。

### 请求报错时看哪里？

读取响应中的 `error.message`。HTTP 400 且错误码为 `unknown_skill` 时，核对 `skill` 的值。非流式请求返回 HTTP 429 表示同一会话仍在运行。浏览器跨站请求若收到 HTTP 403，请从应用后端调用。
