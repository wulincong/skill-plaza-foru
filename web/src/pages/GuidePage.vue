<script setup lang="ts">
import Codebox from '../components/Codebox.vue'
import Icon from '../components/Icon.vue'

const apiOrigin = 'http://biubiubiu.vip:18767'
const requestExample = `curl ${apiOrigin}/v1/chat/completions \\
  -H 'Content-Type: application/json' \\
  -d '{
    "skill": "general",
    "messages": [
      {"role": "user", "content": "请用一句话说明岗位调研前要准备什么。"}
    ],
    "stream": false
  }'`
</script>

<template>
  <section class="page">
    <div class="wrap wrap-read" id="guide-content">
      <header class="guide-head">
        <h1>智能体使用指南</h1>
        <p>在网页上提交任务，或从自己的应用调用智能体。两种方式都由平台执行任务。</p>
      </header>

      <section class="block">
        <h2 class="block-title">在线运行</h2>
        <p class="block-note">打开在线对话即可提问。需要专业能力时，输入 <code>$</code> 选择智能体，也可以在广场点击「在线运行」，按提示填写任务或上传资料。完成后，在对话中查看回答和交付文件。</p>
        <div class="detail-actions">
          <RouterLink class="btn btn-primary" to="/experience">打开在线对话<Icon name="arrow" :size="15" /></RouterLink>
          <RouterLink class="btn btn-quiet" to="/docs">按技能查阅文档</RouterLink>
          <RouterLink class="btn btn-quiet" to="/skills">浏览智能体广场</RouterLink>
        </div>
      </section>

      <section class="block">
        <h2 class="block-title">通过 API 接入</h2>
        <p class="block-note">从应用后端发送 HTTP 请求。当前平台接口无需 API Key。使用 OpenAI 兼容客户端时，将 Base URL 设为 <code>{{ apiOrigin }}/v1</code>，并在请求体中传入 <code>skill</code>。</p>
        <div class="rail">
          <div class="rail-item">
            <span class="rail-no">1</span>
            <div class="rail-body">
              <h3 class="rail-title">选择智能体</h3>
              <p class="rail-desc">通用问答使用 <code>general</code>。要获取专业智能体的标识，运行下面的命令，取返回列表里的 <code>skills[].id</code>，例如就业指导的 <code>career-guidance</code>。</p>
              <Codebox label="查询可用智能体" :text="'curl ' + apiOrigin + '/api/skills'" message="查询命令已复制" />
            </div>
          </div>
          <div class="rail-item">
            <span class="rail-no">2</span>
            <div class="rail-body">
              <h3 class="rail-title">发送第一条消息</h3>
              <p class="rail-desc">将下面的命令复制到终端即可发起一次问答。调用其他智能体时，替换 <code>skill</code> 和问题。<code>messages</code> 的最后一条须是 <code>user</code> 消息，内容为非空文本。</p>
              <Codebox label="POST /v1/chat/completions" :text="requestExample" message="调用示例已复制" primary />
            </div>
          </div>
          <div class="rail-item">
            <span class="rail-no">3</span>
            <div class="rail-body">
              <h3 class="rail-title">读取回答与交付文件</h3>
              <p class="rail-desc">默认返回 JSON，从 <code>choices[0].message.content</code> 读取回答。报告任务的正文可能为空，同时检查顶层的 <code>webLinks[].url</code>（打开网页）、<code>downloads[].url</code>（下载文件）和 <code>reportUrl</code>（报告地址）。相对地址以 <code>{{ apiOrigin }}</code> 为基准解析。</p>
            </div>
          </div>
        </div>
      </section>

      <section class="block">
        <h2 class="block-title">接入时的常见问题</h2>
        <div class="faq">
          <details>
            <summary>如何流式读取长任务？<Icon name="chev-down" :size="16" /></summary>
            <p>把 <code>stream</code> 改为 <code>true</code>，使用 curl 时加上 <code>-N</code>。按 SSE 事件读取并拼接 <code>choices[0].delta.content</code>。当 <code>choices</code> 为空数组时，读取顶层的交付链接或用量。收到 <code>finish_reason: "stop"</code> 后继续读取，直到 <code>data: [DONE]</code>。遇到 <code>error</code> 帧时读取 <code>error.message</code>。</p>
          </details>
          <details>
            <summary>如何继续同一段对话？<Icon name="chev-down" :size="16" /></summary>
            <p>首次请求时由客户端生成一个随机 UUID，作为 <code>sessionId</code> 保存。后续请求沿用同一 <code>skill</code> 和 <code>sessionId</code>，只发送最新一条用户消息。同一会话等本轮结束后再发下一轮。</p>
          </details>
          <details>
            <summary>如何提交附件？<Icon name="chev-down" :size="16" /></summary>
            <p>先向同一 API 服务的 <code>POST /api/upload</code> 发送 JSON，传入 <code>filename</code> 和 Base64 编码的 <code>dataBase64</code>。在对话请求中使用上传响应的 <code>sessionId</code>，并把返回的 <code>name</code> 和 <code>path</code> 放进 <code>attachments</code> 数组。向已有会话上传时，上传请求也要带上该会话的 <code>sessionId</code>。</p>
          </details>
          <details>
            <summary>请求报错时看哪里？<Icon name="chev-down" :size="16" /></summary>
            <p>读取响应中的 <code>error.message</code>。HTTP 400 且错误码为 <code>unknown_skill</code> 时，核对 <code>skill</code> 的值。非流式请求返回 HTTP 429 表示同一会话仍在运行。浏览器跨站请求若收到 HTTP 403，请从应用后端调用。</p>
          </details>
        </div>
      </section>
    </div>
  </section>
</template>
