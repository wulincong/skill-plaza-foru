import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { skillDocsPlugin } from './scripts/skill-docs-plugin'

/* /api/* 转发到本机 Node 后端（server/index.ts，默认 8767）：
  由它桥接 Pi RPC（DeepSeek）并提供运行记录只读 API。
  未启动后端时，运行记录页自动回落演示数据，在线运行页会提示启动方式。 */
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
  /* PLAZA_ 前缀与 VITE_ 同等暴露给 import.meta.env（PLAZA_ENV=test|prod，
     前后端共用一个环境标识；后端经 loadLocalEnv 读 process.env.PLAZA_ENV） */
  envPrefix: ['VITE_', 'PLAZA_'],
  server: {
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
