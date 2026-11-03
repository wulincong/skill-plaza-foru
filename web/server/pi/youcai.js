/* 自部署 vLLM / Qwen 服务：由 PiRunner 显式注册以支持会话内切换。
   保留 Pi 内置的流式、工具调用、取消与 usage 转换，不另写模型客户端。 */
import { loadLocalEnv } from '../lib/env.ts'

export default function registerYoucai(pi) {
  loadLocalEnv()
  pi.registerFlag?.('plaza-youcai-endpoint', { type: 'string', description: '广场后台配置的优才 API 地址' })
  pi.registerFlag?.('plaza-deepseek-route', { type: 'string', description: '当前 Pi 会话的本地 DeepSeek 凭据转发地址' })
  const relayIndex = process.argv.indexOf('--plaza-deepseek-route')
  if (relayIndex >= 0) {
    pi.registerProvider('deepseek', { baseUrl: process.argv[relayIndex + 1], apiKey: 'plaza-relay' })
  }
  const flagIndex = process.argv.indexOf('--plaza-youcai-endpoint')
  const endpoint = flagIndex >= 0 ? process.argv[flagIndex + 1] : undefined
  pi.registerProvider('youcai', {
    name: '优才自部署模型',
    baseUrl: endpoint || process.env.YOUCAI_BASE_URL?.trim() || 'https://u496025-7845e5610890.bjb2.seetacloud.com:8443/v1',
    api: 'openai-completions',
    // Pi / OpenAI SDK 需要非空占位值；下方请求钩子会移除认证头，不发送此值。
    apiKey: 'unused',
    authHeader: false,
    models: [{
      id: 'youcai',
      name: 'youcai',
      reasoning: true,
      input: ['text'],
      // 自部署服务无第三方 token 账单；不代表 GPU / 云主机成本为零。
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      // /v1/models 的 max_model_len 实测值；输出为本项目保守上限。
      contextWindow: 262144,
      maxTokens: 8192,
      compat: {
        thinkingFormat: 'qwen-chat-template',
        maxTokensField: 'max_tokens',
      },
    }],
  })

  pi.on('before_provider_headers', (event, ctx) => {
    if (ctx.model?.provider !== 'youcai') return
    // null 显式删除 SDK 默认注入的 Bearer 头，大小写不同的已有头也一并移除。
    for (const name of Object.keys(event.headers)) {
      if (name.toLowerCase() === 'authorization') event.headers[name] = null
    }
    event.headers.Authorization = null
  })
}
