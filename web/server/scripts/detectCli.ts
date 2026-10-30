#!/usr/bin/env node
/* 环境自检：Pi CLI 与模型配置；退出码 0 = Pi 可用 */

import { resolvePiCli, piModelRef } from '../lib/piRunner.ts'
import { loadLocalEnv } from '../lib/env.ts'

loadLocalEnv()

const mark = (ok: boolean) => (ok ? '✓' : '✗')

console.log('引擎环境自检')
console.log(`- 平台：${process.platform}`)
console.log('- 执行引擎：pi')

const piEnv = process.env.PI_CLI?.trim()
console.log(`- PI_CLI（环境变量 / web/.env）：${piEnv ? piEnv : '未设置（扫描 PATH）'}`)
const pi = resolvePiCli()
if (!pi) {
  console.log(`- 结果：${mark(false)} PATH 上未找到 pi`)
  console.log('  安装：npm i -g @earendil-works/pi-coding-agent；自定义位置时在 web/.env 配置 PI_CLI。')
  process.exit(1)
}

const model = piModelRef()
console.log(`- 结果：${mark(true)} 找到 ${pi}`)
console.log(`- PI_MODEL：${model.provider}/${model.modelId}`)
if (model.provider === 'youcai') {
  console.log('- youcai：无需 API Key；PiRunner 显式加载仓库 provider，不发送 Authorization。')
} else if (model.provider === 'deepseek') {
  console.log(`- DEEPSEEK_API_KEY（或 pi auth 里的凭据）：${mark(Boolean(process.env.DEEPSEEK_API_KEY))} ${process.env.DEEPSEEK_API_KEY ? '已在环境中' : '未在当前环境（确认启动后端的 shell 或 pi auth）'}`)
} else {
  console.log('- 凭据：使用所选 provider 对应的环境变量或 pi auth 配置。')
}
console.log('\n可用引擎：pi')
