#!/usr/bin/env node
// Execute the checked-in 20 requests once, sequentially, using the shared Skill CLI.
import { readFile, writeFile, mkdir, access } from 'node:fs/promises'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
import { performance } from 'node:perf_hooks'
import { randomUUID, createHash } from 'node:crypto'
import { validateRequest } from '../../../scripts/talent-data/core.mjs'
import { readResult } from '../../../scripts/talent-data/artifacts.mjs'

const directory = fileURLToPath(new URL('.', import.meta.url))
const cli = fileURLToPath(new URL('../../../scripts/talent-data-query.mjs', import.meta.url))
const suiteText = await readFile(join(directory, 'queries.json'), 'utf8')
const suite = JSON.parse(suiteText)
const sha256 = text => createHash('sha256').update(text).digest('hex')
const suiteHash = sha256(suiteText)
const args = process.argv.slice(2)
if (args.some(a => !['--resume', '--rerun'].includes(a)) || args.length > 1) throw new Error('用法：node run.mjs [--resume | --rerun]')
if (suite.cases.length !== 20 || new Set(suite.cases.map(c => c.id)).size !== 20) throw new Error('需要 20 个唯一查询')
const byIndustry = new Map()
for (const item of suite.cases) {
  if (!/^Q\d{2}$/.test(item.id)) throw new Error('无效查询 ID')
  validateRequest(item.request)
  if (item.request.execution.freshness !== 'live' || item.request.metrics.length !== 1 || item.request.metrics[0] !== 'positions.count') throw new Error('本轮须为实时单指标计数查询')
  byIndustry.set(item.industry, (byIndustry.get(item.industry) ?? 0) + 1)
}
if (byIndustry.size !== 5 || [...byIndustry.values()].some(n => n !== 4)) throw new Error('需要五产业各四条查询')

const resultsFile = join(directory, 'results.json')
let existing = false
try { await access(resultsFile); existing = true } catch { /* first execution */ }
if (existing && !args.length) throw new Error('已有计时结果，使用 --resume 继续未完成项，或 --rerun 显式重测')
if (!existing && args[0] === '--resume') throw new Error('没有可继续的计时结果')
let run
if (args[0] === '--resume') {
  run = JSON.parse(await readFile(resultsFile, 'utf8'))
  if (run.suiteHash !== suiteHash || !Array.isArray(run.results)) throw new Error('原查询清单已变化，不能混入同一次计时')
} else {
  run = { schema: 'talent-query-benchmark-results/1', suiteHash, engine: suite.engine,
    runId: `${new Date().toISOString().replaceAll(':', '-')}-${randomUUID().slice(0, 8)}`,
    startedAt: new Date().toISOString(), finishedAt: null, runStatus: 'running', protocol: suite.protocol, results: [] }
}
run.runStatus = 'running'
const rawDirectory = join(directory, 'raw', run.runId)
await mkdir(rawDirectory, { recursive: true })
await mkdir(join(directory, 'sql'), { recursive: true })

const seconds = ms => ms === null || ms === undefined ? '' : (ms / 1000).toFixed(3)
function csvCell(v) {
  const s = v === null || v === undefined ? '' : String(v)
  return '"' + s.replaceAll('"', '""') + '"'
}
async function save() {
  const succeeded = run.results.filter(r => r.success)
  run.summary = { attempted: run.results.length, succeeded: succeeded.length, failed: run.results.length - succeeded.length,
    wallMs: run.results.reduce((sum, r) => sum + r.wallMs, 0),
    sqlBatchMs: run.results.reduce((sum, r) => sum + (r.sqlBatchMs ?? 0), 0) }
  await writeFile(resultsFile, JSON.stringify(run, null, 2) + '\n')
  const headers = ['id', 'industry', 'query', 'status', 'job_records', 'request_wall_seconds', 'db_batch_seconds', 'queue_seconds', 'application_cache_mode', 'sql_count', 'exit_code', 'started_at_utc', 'finished_at_utc', 'source_read_time', 'error', 'sql_file', 'raw_result']
  const rows = run.results.map(r => [r.id, r.industry, r.label, r.status, r.positions, seconds(r.wallMs), seconds(r.sqlBatchMs), seconds(r.queueMs), r.mode, r.sqlCount, r.exitCode, r.startedAt, r.finishedAt, r.sourceReadTime, r.errors.map(e => `${e.code}: ${e.message}`).join(' | '), r.sqlFile, r.rawResult])
  await writeFile(join(directory, 'timings.csv'), '\uFEFF' + [headers, ...rows].map(row => row.map(csvCell).join(',')).join('\n') + '\n')
  const lines = ['# 五产业岗位查询与计时', '', `运行状态：${run.runStatus}；已执行 ${run.summary.attempted}/20；成功 ${run.summary.succeeded}；失败 ${run.summary.failed}。`, '',
    '五产业各四条查询：全国总量、广东总量、广州明确大专/高职、深圳经验标注应届/在校生。全部只统计在招且未删除记录，产业采用一级分类及全部子节点；未限制岗位名称、行业之外的岗位类型或时间窗。', '',
    '计时方式：每条只执行一次，依次串行，freshness=live 禁用应用结果缓存；未清空数据库缓冲池。主耗时从 CLI 进程启动前到关闭后，以单调时钟测量，包含解析、等待、连接、查询、传输和工件写入。数据库批次耗时包含建连/传输，不是纯服务端 SQL 计时。', '',
    '现有逐语句日志 elapsedMs 受 mysql 标准输出缓冲影响，本表不将其当作 SQL 执行耗时。零结果保留 0，失败保留空值；不会将超时写成零岗位。', '',
    '| 编号 | 产业 | 查询 | 状态 | 岗位记录数 | 请求耗时/秒 | 数据库批次/秒 |', '|---|---|---|---|---:|---:|---:|']
  for (const r of run.results) lines.push(`| ${r.id} | ${r.industry} | ${r.label.split('：').slice(1).join('：')} | ${r.status} | ${r.positions === null ? '未取得' : r.positions.toLocaleString('en-US')} | ${seconds(r.wallMs)} | ${seconds(r.sqlBatchMs)} |`)
  lines.push('', `已测请求累计耗时：${seconds(run.summary.wallMs)} 秒。不同产业的岗位集合可能重叠，岗位数不能跨产业直接相加。每条请求独立读取快照，读取时间见 results.json。`, '',
    '## 复查与复现', '',
    '- [20 条请求](queries.json)：自然语言题目与完整 talent-query/1 请求。',
    '- [产业字典映射](industry-mapping.json)：实际一级分类 ID、子树大小与字典版本。',
    '- [计时 CSV](timings.csv)、[结构化结果](results.json)。',
    '- sql/ 中的 SQL 仅来自实际查询证据；仅供内部核查，不是公众号公开产物。',
    '- raw/ 保留本机原始输出、完整结果、证据与 manifest；该目录不提交 Git。results.json 中记录原工件路径及 SHA-256。', '',
    '```bash', 'node reports/query-benchmarks/2026-11-02-five-industries-optimized/run.mjs --resume', '# 显式重新测量全部请求（会重新查库）', 'node reports/query-benchmarks/2026-11-02-five-industries-optimized/run.mjs --rerun', '```', '')
  await writeFile(join(directory, '计时结果.md'), lines.join('\n'))
}
await save()
console.log(JSON.stringify({ event: 'benchmark-start', runId: run.runId, completed: run.results.length, rawDirectory }))
for (const item of suite.cases) {
  if (run.results.some(r => r.id === item.id)) continue
  const workspace = join(rawDirectory, item.id)
  await mkdir(workspace, { recursive: true })
  await writeFile(join(workspace, 'request.json'), JSON.stringify(item.request, null, 2) + '\n')
  const startedAt = new Date().toISOString(), monotonicStart = performance.now()
  console.log(JSON.stringify({ event: 'query-start', id: item.id, label: item.label, startedAt }))
  const processResult = await new Promise(resolve => {
    const child = spawn(process.execPath, [cli, 'query', '--request', 'request.json'], { cwd: workspace, env: process.env })
    let stdout = '', stderr = ''
    child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8')
    child.stdout.on('data', chunk => { stdout += chunk })
    child.stderr.on('data', chunk => { stderr += chunk })
    child.on('error', () => { stderr += 'CLI 启动失败' })
    child.on('close', exitCode => resolve({ exitCode, stdout, stderr, wallMs: Math.round(performance.now() - monotonicStart) }))
  })
  const finishedAt = new Date().toISOString()
  await writeFile(join(workspace, 'stdout.json'), processResult.stdout)
  await writeFile(join(workspace, 'stderr.txt'), processResult.stderr)
  let output, result, evidence, verificationError = null
  try {
    output = JSON.parse(processResult.stdout)
    if (output.artifacts?.result) {
      result = await readResult(output.artifacts.result, workspace)
      evidence = JSON.parse(await readFile(join(workspace, output.artifacts.evidence), 'utf8'))
    }
  } catch (error) { verificationError = { code: 'ARTIFACT_CHECK_FAILED', message: error.message } }
  const metric = result?.metrics.find(m => m.name === 'positions.count')
  const success = processResult.exitCode === 0 && ['complete', 'empty'].includes(result?.status) && result.quality.allPass && Number.isSafeInteger(metric?.value) && metric.value >= 0 && result.freshness.mode === 'live' && !result.execution.reused
  const errors = [...(result?.errors ?? output?.errors ?? []), ...(verificationError ? [verificationError] : [])]
  if (!success && !errors.length) errors.push({ code: 'INVALID_BENCHMARK_RESULT', message: '未获得经校验的实时完整结果' })
  let sqlFile = null, sqlHash = null
  if (evidence?.queries.length) {
    sqlFile = `sql/${item.id}.sql`
    const text = `-- ${item.id}: ${item.label}\n-- Actual statements captured from execution evidence.\n` + evidence.queries.map(q => `-- queryId: ${q.id}; completed: ${q.completed}\n${q.sql};`).join('\n\n') + '\n'
    sqlHash = sha256(text)
    await writeFile(join(directory, sqlFile), text)
  }
  const record = { id: item.id, industry: item.industry, industryId: item.industryId, variant: item.variant, label: item.label,
    status: result?.status ?? output?.status ?? 'failed', success, positions: success ? metric.value : null,
    wallMs: processResult.wallMs, sqlBatchMs: result?.execution.sqlBatchMs ?? null, queueMs: result?.execution.queueMs ?? null,
    toolTotalMs: result?.execution.totalMs ?? null, sqlCount: evidence?.queries.length ?? 0, mode: result?.freshness.mode ?? null,
    exitCode: processResult.exitCode, startedAt, finishedAt, sourceReadTime: result?.freshness.sourceReadTime ?? null,
    dataReadAt: result?.freshness.dataReadAt ?? null, sourceLatestUpdateAt: result?.freshness.sourceLatestUpdateAt ?? null,
    contentHash: result?.contentHash ?? null, snapshotId: result?.snapshotId ?? null, sqlFile, sqlSha256: sqlHash,
    rawResult: output?.artifacts?.result ? relative(directory, join(workspace, output.artifacts.result)) : null,
    rawManifest: output?.artifacts?.manifest ? relative(directory, join(workspace, output.artifacts.manifest)) : null,
    stdoutSha256: sha256(processResult.stdout), errors }
  run.results.push(record)
  await save()
  console.log(JSON.stringify({ event: 'query-finished', id: record.id, status: record.status, success, positions: record.positions, wallSeconds: record.wallMs / 1000, batchSeconds: (record.sqlBatchMs ?? 0) / 1000, errors }))
}
run.finishedAt = new Date().toISOString()
run.runStatus = 'finished'
await save()
console.log(JSON.stringify({ event: 'benchmark-finished', ...run.summary, outputDirectory: directory }))
