// Maintainer command. The public lookup only reads the committed snapshot.
import {execFileSync} from 'node:child_process'
import {rename, writeFile, rm} from 'node:fs/promises'
import {randomUUID} from 'node:crypto'
import {fileURLToPath} from 'node:url'

const source = fileURLToPath(new URL('../mysql-query.mjs', import.meta.url))
const target = fileURLToPath(new URL('../../.agents/skills/talent-data-query/data/position-catalog.json', import.meta.url))
// Pick one spelling per name using the database collation and a stable representative.
// All fields, including the timestamp and the chain metadata, come from the same SELECT.
const sql = `SELECT UTC_TIMESTAMP() AS read_utc, c.id AS node_id, TRIM(rep.position_name) AS job_name,
    i.id AS industry_id, i.name AS industry_name, i.level AS industry_level, i.open_status AS open_status
  FROM c_industry_chain_position c
  JOIN (SELECT TRIM(position_name) AS name_key, MIN(id) AS rep_id
        FROM c_industry_chain_position WHERE deleted=0 AND industry_chain_position_type='POSITION'
        GROUP BY TRIM(position_name)) names ON names.name_key <=> TRIM(c.position_name)
  JOIN c_industry_chain_position rep ON rep.id=names.rep_id
  LEFT JOIN c_industry_chain_info i ON i.id=c.industry_chain_id
  WHERE c.deleted=0 AND c.industry_chain_position_type='POSITION'
  ORDER BY BINARY TRIM(rep.position_name), i.id, c.id`
const result = JSON.parse(execFileSync(process.execPath,
  [source, '--max-rows', '100000', '--max-cell-chars', '2048', '--timeout-ms', '30000', sql],
  {encoding:'utf8', maxBuffer:32*1024*1024}))
if (!result.ok || result.truncated || !result.rows.length) throw new Error('未取得完整的岗位目录')
const industries = new Map(), jobs = new Map(), nodeIds = new Set()
let pairs = 0
for (const row of result.rows) {
  if (!row.job_name?.trim() || !row.industry_name?.trim() || !/^\d+$/.test(row.industry_id)
      || !/^\d+$/.test(row.node_id) || nodeIds.has(row.node_id)
      || !/^-?\d+$/.test(row.industry_level) || !['0','1','2'].includes(row.open_status)) {
    throw new Error('发现缺失或重复的节点、无法解析的产业或未知产业状态；未替换快照')
  }
  nodeIds.add(row.node_id)
  industries.set(row.industry_id, {id:row.industry_id, name:row.industry_name, level:Number(row.industry_level), openStatus:Number(row.open_status)})
  if (!jobs.has(row.job_name)) jobs.set(row.job_name, {name:row.job_name, nodes:{}})
  const nodes = jobs.get(row.job_name).nodes
  if (!nodes[row.industry_id]) { nodes[row.industry_id] = []; pairs++ }
  nodes[row.industry_id].push(row.node_id)
}
const counts = {jobs:jobs.size, industries:industries.size, pairs, nodes:nodeIds.size}
const readAt = result.rows[0].read_utc.replace(' ','T')+'Z'
const catalog = {schema:'talent-position-catalog/1', source:'talent-main', readAt, counts}
const lines = [
  JSON.stringify(catalog).slice(0,-1)+',',
  '"industries":[',
  [...industries.values()].sort((a,b)=>Number(a.id)-Number(b.id)).map(r=>JSON.stringify(r)).join(',\n'),
  '],"jobs":[',
  [...jobs.values()].map(r=>JSON.stringify(r)).join(',\n'),
  ']}',
]
const temporary = target+'.'+randomUUID()+'.tmp'
try {
  await writeFile(temporary, lines.join('\n')+'\n', {flag:'wx'})
  await rename(temporary,target)
} finally { await rm(temporary,{force:true}) }
console.log(JSON.stringify(catalog))
