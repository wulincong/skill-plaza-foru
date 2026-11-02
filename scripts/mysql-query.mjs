#!/usr/bin/env node
/* ============================================================
   MySQL 只读查询工具（开发会话与广场 Agent 的 bash 均可调用）
   ------------------------------------------------------------
   用法：
     node scripts/mysql-query.mjs [选项] "SELECT ..."
     node scripts/mysql-query.mjs [选项] --file 查询.sql     # 单条语句
   选项：
     --format json|table    输出格式，默认 json（table 输出 markdown 表）
     --max-rows N           返回行数上限，默认 200（超出截断并标 truncated）
     --max-cell-chars N     单元格字符上限，默认 400（JD 为 longtext，防撑爆上下文）
     --timeout-ms N         服务端 max_execution_time，默认 120000
     --mysql-bin PATH       mysql 客户端路径，默认 $MYSQL_BIN 或 PATH 上的 mysql
   配置：MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE
   取进程环境，缺失键回落解析 web/.env（不覆盖已有环境变量）。
   客户端 8.4 连 5.7 服务端握手会退回 latin1，本工具每连接前置
   SET NAMES utf8mb4 COLLATE utf8mb4_general_ci（中文变 ? 的已知坑）。
   只读守卫：拒绝多语句，首关键字必须是 SELECT/SHOW/DESC/DESCRIBE/
   EXPLAIN/WITH。守卫是防呆而非安全边界——账号本身仅 SELECT 权限。
   已知限制：mysql -B 批处理输出中 NULL 与字面 "NULL" 文本不可区分；
   大结果集会被 maxBuffer 截断报错，查询请自带 LIMIT。
   ============================================================ */

import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { isAuthPluginError, mysqlBinCandidates } from './mysql-client.mjs'
import { readMysqlConfig } from './mysql-config.mjs'

const USAGE = `用法：node scripts/mysql-query.mjs [选项] "SQL" | --file 文件
选项：--format json|table  输出格式（默认 json）
      --max-rows N         行数上限（默认 200，超出截断）
      --max-cell-chars N   单元格字符上限（默认 400）
      --timeout-ms N       max_execution_time（默认 120000）
      --mysql-bin PATH     mysql 客户端路径（默认 $MYSQL_BIN 或 PATH）`

const READ_ONLY_HEAD = new Set(['select', 'show', 'desc', 'describe', 'explain', 'with'])
const CFG_KEYS = ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE']

/* --- 参数解析 --- */
function parseArgs(argv) {
  const opt = {
    format: 'json',
    maxRows: 200,
    maxCellChars: 400,
    timeoutMs: 120_000,
    mysqlBin: process.env.MYSQL_BIN || 'mysql',
    file: null,
    help: false,
  }
  const rest = []
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--file') opt.file = argv[++i]
    else if (a === '--format') opt.format = argv[++i]
    else if (a === '--max-rows') opt.maxRows = Number(argv[++i])
    else if (a === '--max-cell-chars') opt.maxCellChars = Number(argv[++i])
    else if (a === '--timeout-ms') opt.timeoutMs = Number(argv[++i])
    else if (a === '--mysql-bin') opt.mysqlBin = argv[++i]
    else if (a === '--help' || a === '-h') opt.help = true
    else rest.push(a)
  }
  opt.sql = opt.file !== null ? readFileSync(opt.file, 'utf8') : rest.join(' ')
  return opt
}

/* --- 配置：进程环境优先，缺的键从 web/.env 补齐 --- */
function config() {
  return readMysqlConfig({ required: false })
}

/* --- 只读守卫（防呆，非安全边界）：注释清洗后单条 + 白名单首关键字 --- */
function guardSql(sql) {
  const s = sql
    .replace(/--[^\n]*/g, ' ')
    .replace(/#[^\n]*/g, ' ')
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .trim()
    .replace(/;+\s*$/, '')
    .trim()
  if (!s) throw new Error('SQL 为空。')
  if (s.includes(';')) throw new Error('只支持单条语句（检测到多余的分号）。')
  const head = s.split(/\s+/)[0].toLowerCase()
  if (!READ_ONLY_HEAD.has(head))
    throw new Error(`只读工具，仅支持 ${[...READ_ONLY_HEAD].join('/')} 开头的语句（收到 ${head.toUpperCase()}）。`)
  return s
}

/* --- mysql -B 转义还原：\n \t \0 \\ ; NULL 字面量按 NULL 处理（见头部限制） --- */
function unescapeCell(v) {
  if (v === 'NULL') return null
  let out = ''
  for (let i = 0; i < v.length; i++) {
    if (v[i] === '\\' && i + 1 < v.length) {
      const c = v[++i]
      out += c === 'n' ? '\n' : c === 't' ? '\t' : c === '0' ? '\0' : c
    } else out += v[i]
  }
  return out
}

function clip(text, max) {
  if (text === null || text === undefined) return null
  const s = String(text)
  if (s.length <= max) return s
  return s.slice(0, max) + `…[已截断，原 ${s.length} 字符，可 --max-cell-chars 调大]`
}

function fail(error) {
  process.stdout.write(JSON.stringify({ ok: false, error }) + '\n')
  process.exit(1)
}

/* --- 输出 --- */
function emitTable(out) {
  const cells = (v) => String(v ?? 'NULL').replace(/\|/g, '\\|').replace(/\r?\n/g, ' ')
  const lines = [`| ${out.columns.map(cells).join(' | ')} |`, `| ${out.columns.map(() => '---').join(' | ')} |`]
  for (const row of out.rows) lines.push(`| ${out.columns.map((c) => cells(row[c])).join(' | ')} |`)
  const meta = [`行数 ${out.rowCount}/${out.totalRows}${out.truncated ? '（已截断，--max-rows 调整）' : ''}`, `耗时 ${out.elapsedMs}ms`]
  process.stdout.write(meta.join(' · ') + '\n\n' + lines.join('\n') + '\n')
}

function main() {
  const opt = parseArgs(process.argv.slice(2))
  if (opt.help || (!opt.sql && !opt.file)) {
    process.stdout.write(USAGE + '\n')
    process.exit(opt.help ? 0 : 2)
  }
  if (!['json', 'table'].includes(opt.format)) fail(`非法 --format：${opt.format}（仅 json|table）`)

  const cfg = config()
  const missing = CFG_KEYS.filter((k) => k !== 'MYSQL_PORT' && !cfg[k])
  if (missing.length) fail(`缺少数据库配置：${missing.join('/')}（进程环境或 web/.env）`)

  let sql
  try {
    sql = guardSql(opt.sql)
  } catch (exc) {
    fail(exc.message)
  }

  const prelude = `SET NAMES utf8mb4 COLLATE utf8mb4_general_ci; SET SESSION max_execution_time=${opt.timeoutMs};`
  const args = (bin) => [
    '-h', cfg.MYSQL_HOST,
    '-P', String(cfg.MYSQL_PORT || 3306),
    '-u', cfg.MYSQL_USER,
    '--default-character-set=utf8mb4',
    '-D', cfg.MYSQL_DATABASE,
    '-B',
    '--execute', `${prelude} ${sql}`,
  ]
  const bins = mysqlBinCandidates(opt.mysqlBin)
  const started = Date.now()
  let r
  let usedBin = bins[0]
  for (let i = 0; i < bins.length; i++) {
    usedBin = bins[i]
    r = spawnSync(
      usedBin,
      args(usedBin),
      {
        encoding: 'utf8',
        timeout: opt.timeoutMs + 30_000,
        maxBuffer: 32 * 1024 * 1024,
        env: { ...process.env, MYSQL_PWD: cfg.MYSQL_PASSWORD },
      },
    )
    const failure = r.error ? String(r.error.message || r.error) : String(r.stderr || '')
    if (r.error && r.error.code === 'ENOENT') continue
    if (!r.error && r.status === 0) break
    if (!isAuthPluginError(failure) || i === bins.length - 1) break
  }
  const elapsedMs = Date.now() - started

  if (r.error) {
    const hint =
      r.error.code === 'ENOENT'
        ? `找不到 mysql 客户端（${opt.mysqlBin}），用 --mysql-bin 指定路径`
        : String(r.error.message || r.error).includes('maxBuffer')
          ? '结果集超过 32MB 缓冲上限，请给查询加 LIMIT 或减小返回列'
          : (r.error.message || String(r.error))
    fail(`mysql 执行失败：${hint}`)
  }
  if (r.signal) fail(`mysql 客户端被信号 ${r.signal} 终止（疑似超时 ${opt.timeoutMs + 30_000}ms）`)
  if (r.status !== 0) {
    const detail = String(r.stderr || r.stdout || '').trim() || `mysql 退出码 ${r.status}`
    fail(isAuthPluginError(detail) ? `${detail}（当前客户端 ${usedBin} 缺 mysql_native_password 插件，用 --mysql-bin 指定 8.x 客户端）` : detail)
  }

  /* SET 前置语句不产生输出行；首行即结果列头 */
  const lines = r.stdout.split('\n').filter((l) => l !== '')
  const columns = lines.length ? lines[0].split('\t') : []
  const dataLines = lines.slice(1)
  const truncated = dataLines.length > opt.maxRows
  const rows = dataLines.slice(0, opt.maxRows).map((l) => {
    const cells = l.split('\t')
    const row = {}
    columns.forEach((c, i) => {
      row[c] = clip(unescapeCell(cells[i] ?? ''), opt.maxCellChars)
    })
    return row
  })

  const out = { ok: true, sql, elapsedMs, columns, rowCount: rows.length, totalRows: dataLines.length, truncated, rows }
  if (opt.format === 'table') emitTable(out)
  else process.stdout.write(JSON.stringify(out) + '\n')
}

main()
