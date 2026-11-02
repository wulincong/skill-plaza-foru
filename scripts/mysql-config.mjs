import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export const MYSQL_CONFIG_KEYS = ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']

// Configuration is read inside trusted tools. Never return its values to the Agent.
export function readMysqlConfig({ env = process.env, required = true } = {}) {
  const cfg = {}
  for (const key of MYSQL_CONFIG_KEYS) if (env[key] !== undefined) cfg[key] = env[key]
  const file = fileURLToPath(new URL('../web/.env', import.meta.url))
  if (!MYSQL_CONFIG_KEYS.every(key => cfg[key] !== undefined) && existsSync(file)) {
    for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
      const match = /^\s*(MYSQL_[A-Z_]+)\s*=\s*(.*?)\s*$/.exec(line)
      if (!match || !MYSQL_CONFIG_KEYS.includes(match[1]) || cfg[match[1]] !== undefined) continue
      let value = match[2]
      if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1)
      cfg[match[1]] = value
    }
  }
  const missing = MYSQL_CONFIG_KEYS.filter(key => key !== 'MYSQL_PORT' && !cfg[key])
  if (required && missing.length) throw Object.assign(new Error(`缺少数据库配置：${missing.join('/')}`), { code: 'CONFIG_MISSING' })
  return cfg
}
