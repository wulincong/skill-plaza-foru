#!/usr/bin/env node
/*
 * 岗位市场白名单查询工具：Agent 只能选择 queryId 并填写 JSON 参数。
 * 原始 SQL 不从命令行进入；并行批次受控，避免重查询同时压垮岗位库。
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
import { isAuthPluginError, mysqlBinCandidates } from './mysql-client.mjs'
import { readMysqlConfig } from './mysql-config.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const QUERY_DIR = join(HERE, 'career-market-queries')
const QUERY_IDS = new Set(['cohort-summary', 'education-distribution', 'experience-distribution', 'salary-distribution', 'title-top', 'source-distribution', 'city-distribution'])
const DEFAULT_TIMEOUT_MS = 120_000
const MAX_TIMEOUT_MS = 180_000
const MAX_PARALLEL = 2
const CLIENT_PROBE_TIMEOUT_MS = 5_000

function usage() {
  return `用法：\n  node scripts/career-market-query.mjs --query education-distribution --params '{"city":"广州市","keywords":["Java"]}'\n  node scripts/career-market-query.mjs --query city-distribution --params '{"province":"广东省","keywords":["Java"],"roleTerms":["后端","服务端","开发"],"internship":true,"limit":20,"timeoutMs":120000}'\n  node scripts/career-market-query.mjs --parallel '[{"query":"education-distribution","params":{}}]'\n\n允许 query：${[...QUERY_IDS].join(', ')}\n参数：普通查询使用 city；city-distribution 使用 province 且 limit 固定为 20；两者均支持 keywords、roleTerms、internship、timeoutMs`
}

function config() {
  return readMysqlConfig()
}

function sqlQuote(value) {
  return `'${String(value).replaceAll('\\', '\\\\').replaceAll("'", "\\'")}'`
}

function validateParams(raw = {}, queryId) {
  const isCityDistribution = queryId === 'city-distribution'
  const locationKey = isCityDistribution ? 'province' : 'city'
  const allowed = new Set([locationKey, 'keywords', 'roleTerms', 'internship', 'limit', 'timeoutMs'])
  for (const key of Object.keys(raw)) if (!allowed.has(key)) throw new Error(`不允许的参数：${key}`)
  const location = String(raw[locationKey] ?? (isCityDistribution ? '广东省' : '广州市')).trim()
  const locationPattern = isCityDistribution
    ? /^[\u4e00-\u9fff]{2,12}(省|自治区|市|特别行政区)?$/
    : /^[\u4e00-\u9fff]{2,12}(市|区|县)?$/
  if (!locationPattern.test(location)) throw new Error(`${locationKey} 格式非法`)
  const keywords = raw.keywords ?? ['Java']
  const roleTerms = raw.roleTerms ?? ['后端', '服务端', '开发']
  if (!Array.isArray(keywords) || keywords.length < 1 || keywords.length > 8) throw new Error('keywords 必须为 1-8 个字符串')
  if (!Array.isArray(roleTerms) || roleTerms.length < 1 || roleTerms.length > 8) throw new Error('roleTerms 必须为 1-8 个字符串')
  for (const term of [...keywords, ...roleTerms]) {
    if (typeof term !== 'string' || term.length < 1 || term.length > 30 || !/^[\w\u4e00-\u9fff+ .-]+$/u.test(term)) throw new Error(`关键词非法：${term}`)
  }
  const limit = Number(raw.limit ?? 20)
  if (isCityDistribution && limit !== 20) throw new Error('city-distribution 的 limit 固定为 20')
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new Error('limit 必须为 1-100 的整数')
  const timeoutMs = Math.min(Math.max(Number(raw.timeoutMs ?? DEFAULT_TIMEOUT_MS), 1000), MAX_TIMEOUT_MS)
  if (!Number.isFinite(timeoutMs)) throw new Error('timeoutMs 非法')
  return {
    [locationKey]: location,
    keywords,
    roleTerms,
    internship: raw.internship === true,
    limit,
    timeoutMs,
  }
}

function buildSql(queryId, params) {
  if (!QUERY_IDS.has(queryId)) throw new Error(`未知 query：${queryId}`)
  const file = join(QUERY_DIR, `${queryId}.sql`)
  let sql = readFileSync(file, 'utf8')
  const keywordSql = params.keywords.map(sqlQuote).map(v => `p.name LIKE CONCAT('%', ${v}, '%')`).join(' AND ')
  const roleSql = params.roleTerms.map(sqlQuote).map(v => `p.name LIKE CONCAT('%', ${v}, '%')`).join(' OR ')
  const internshipSql = params.internship
    ? "AND (p.name LIKE '%实习%' OR LOWER(p.name) LIKE '%intern%' OR p.experience IN ('GRADUATING','ON_CAMPUS'))"
    : ''
  sql = sql.replaceAll('{{CITY}}', sqlQuote(params.city))
    .replaceAll('{{PROVINCE}}', sqlQuote(params.province))
    .replaceAll('{{TITLE_PREDICATE}}', `(${keywordSql}) AND ((${roleSql}))`)
    .replaceAll('{{INTERNSHIP_PREDICATE}}', internshipSql)
    .replaceAll('{{LIMIT}}', String(params.limit))
  if (/{{[A-Z_]+}}/.test(sql)) throw new Error('查询模板存在未填充参数')
  return sql.trim()
}

function parseTabular(stdout, maxRows) {
  const lines = stdout.split('\n').filter(Boolean)
  if (!lines.length) return { columns: [], rows: [] }
  const columns = lines[0].split('\t')
  const rows = lines.slice(1, maxRows + 1).map(line => {
    const cells = line.split('\t')
    return Object.fromEntries(columns.map((c, i) => [c, cells[i] === 'NULL' ? null : cells[i] ?? '']))
  })
  return { columns, rows, totalRows: lines.length - 1, truncated: lines.length - 1 > maxRows }
}

function addRatios(queryId, result) {
  if (!['education-distribution', 'experience-distribution', 'salary-distribution', 'source-distribution'].includes(queryId)) return result
  const total = result.rows.reduce((sum, row) => sum + Number(row.count || 0), 0)
  if (!total) return result
  return { ...result, rows: result.rows.map(row => ({ ...row, ratio: Number((Number(row.count || 0) / total * 100).toFixed(2)) })) }
}

function spawnMysql(bin, sql, cfg, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(bin, [
      '-h', cfg.MYSQL_HOST, '-P', String(cfg.MYSQL_PORT || 3306), '-u', cfg.MYSQL_USER,
      '--default-character-set=utf8mb4', '-D', cfg.MYSQL_DATABASE, '-B',
      '--execute', `SET NAMES utf8mb4 COLLATE utf8mb4_general_ci; SET SESSION max_execution_time=${timeoutMs}; ${sql}`,
    ], { env: { ...process.env, MYSQL_PWD: cfg.MYSQL_PASSWORD } })
    let stdout = '', stderr = ''
    const started = Date.now()
    const timer = setTimeout(() => child.kill('SIGTERM'), timeoutMs + 5000)
    child.stdout.on('data', chunk => { stdout += chunk })
    child.stderr.on('data', chunk => { stderr += chunk })
    child.on('error', error => { clearTimeout(timer); reject(error) })
    child.on('close', code => {
      clearTimeout(timer)
      const elapsedMs = Date.now() - started
      if (code !== 0) return reject(new Error(stderr.trim() || `mysql 退出码 ${code}`))
      resolve({ stdout, elapsedMs })
    })
  })
}

/* 运行开始时只探测一次客户端，避免每条查询都重复触发 9.x 认证失败再回落。 */
async function selectMysqlBin(cfg, timeoutMs) {
  const bins = mysqlBinCandidates()
  let lastError
  for (const bin of bins) {
    try {
      await spawnMysql(bin, 'SELECT 1 AS mysql_client_probe', cfg, Math.min(timeoutMs, CLIENT_PROBE_TIMEOUT_MS))
      return bin
    } catch (error) {
      lastError = error
      const retryable = isAuthPluginError(error.message) || error.code === 'ENOENT'
      if (!retryable || bin === bins[bins.length - 1]) throw error
    }
  }
  throw lastError
}

async function execute(sql, cfg, timeoutMs, maxRows, mysqlBin) {
  const bin = mysqlBin || await selectMysqlBin(cfg, timeoutMs)
  const { stdout, elapsedMs } = await spawnMysql(bin, sql, cfg, timeoutMs)
  return { ...parseTabular(stdout, maxRows), elapsedMs, mysqlBin: bin }
}

async function runOne(item, cfg, mysqlBin) {
  const queryId = item.query
  const params = validateParams(item.params, queryId)
  const sql = buildSql(queryId, params)
  const started = Date.now()
  try {
    const result = addRatios(queryId, await execute(sql, cfg, params.timeoutMs, params.limit, mysqlBin))
    return { ok: true, queryId, params, ...result, snapshotDate: new Date().toISOString().slice(0, 10) }
  } catch (error) {
    return { ok: false, queryId, params, elapsedMs: Date.now() - started, error: String(error.message || error) }
  }
}

async function runParallel(items, cfg) {
  if (!Array.isArray(items) || items.length < 1 || items.length > 8) throw new Error('parallel 必须包含 1-8 个查询')
  const results = Array(items.length)
  const started = Date.now()
  const mysqlBin = await selectMysqlBin(cfg, Math.max(...items.map(item => validateParams(item.params, item.query).timeoutMs)))
  let cursor = 0
  async function worker() {
    while (cursor < items.length) {
      const index = cursor++
      results[index] = await runOne(items[index], cfg, mysqlBin)
    }
  }
  await Promise.all(Array.from({ length: Math.min(MAX_PARALLEL, items.length) }, worker))
  return { ok: results.every(r => r.ok), parallel: true, maxParallel: MAX_PARALLEL, mysqlBin, results, failed: results.filter(r => !r.ok).map(r => r.queryId), elapsedMs: Date.now() - started }
}

async function main() {
  const argv = process.argv.slice(2)
  if (argv.includes('--help') || !argv.length) return console.log(usage())
  const cfg = config()
  const parallelAt = argv.indexOf('--parallel')
  if (parallelAt >= 0) return console.log(JSON.stringify(await runParallel(JSON.parse(argv[parallelAt + 1]), cfg)))
  const queryAt = argv.indexOf('--query')
  if (queryAt < 0) throw new Error('必须指定 --query 或 --parallel')
  const paramsAt = argv.indexOf('--params')
  const params = paramsAt >= 0 ? JSON.parse(argv[paramsAt + 1]) : {}
  console.log(JSON.stringify(await runOne({ query: argv[queryAt + 1], params }, cfg)))
}

main().catch(error => { console.error(JSON.stringify({ ok: false, error: String(error.message || error) })); process.exitCode = 1 })
