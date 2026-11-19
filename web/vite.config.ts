import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { skillDocsPlugin } from './scripts/skill-docs-plugin'

/* /api/* 转发到本机 Node 后端（server/index.ts，默认 8767）：
  由它桥接 Pi RPC（DeepSeek）并提供受管理员认证保护的运行记录 API。 */
const apiProxy = {
  '/p/': {
    target: 'http://127.0.0.1:8767',
    changeOrigin: false,
  },
  '/api': {
    target: 'http://127.0.0.1:8767',
    changeOrigin: false,
  },
}

export default defineConfig({
  plugins: [vue(), skillDocsPlugin()],
  /* 仅暴露前端需要的环境标识（PLAZA_ENV=test|prod，
     前后端共用一个环境标识；后端经 loadLocalEnv 读 process.env.PLAZA_ENV） */
  envPrefix: ['VITE_', 'PLAZA_ENV'],
  server: {
    // Development serves the source tree. Keep private runs and workspaces behind the API.
    fs: { deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/server/**', '**/*.sqlite*'] },
    allowedHosts: ['biubiubiu.vip'],
    host: '127.0.0.1',
    port: 4188,
    proxy: apiProxy,
  },
  preview: {
    allowedHosts: ['biubiubiu.vip'],
    host: '127.0.0.1',
    port: 4188,
    proxy: apiProxy,
  },
})
