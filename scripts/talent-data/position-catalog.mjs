import {readFile} from 'node:fs/promises'
import {fail, textValue} from './core.mjs'

const file = new URL('../../.agents/skills/talent-data-query/data/position-catalog.json', import.meta.url)
const pageSize = 20

export async function lookupCatalog(options) {
  const job = options.job === undefined ? '' : textValue(options.job,256,'目录岗位').toLowerCase()
  const industry = options.industry === undefined ? '' : textValue(options.industry,256,'目录产业').toLowerCase()
  const match = options.match ?? 'contains'
  if (!['contains','exact'].includes(match)) fail('INVALID_REQUEST','--match 支持 contains 或 exact')
  const matchesName = (name,term) => !term || (match==='exact' ? name.toLowerCase()===term : name.toLowerCase().includes(term))
  const offset = Number(options.offset ?? 0)
  if (!/^(0|[1-9]\d*)$/.test(options.offset ?? '0') || !Number.isSafeInteger(offset)) {
    fail('INVALID_REQUEST','--offset 需要非负整数')
  }
  const data = JSON.parse(await readFile(file,'utf8'))
  const byId = /^\d+$/.test(industry)
  const chains = data.industries.filter(row => byId ? row.id === industry : matchesName(row.name,industry))
  const chainIds = new Set(chains.map(row => row.id))
  const matchedCounts = new Map(), matches = []
  for (const row of data.jobs) {
    if (!matchesName(row.name,job)) continue
    const links = Object.entries(row.nodes).filter(([id]) => chainIds.has(id))
    if (!links.length) continue
    matches.push({name:row.name, nodes:Object.fromEntries(links)})
    for (const [id] of links) matchedCounts.set(id,(matchedCounts.get(id) ?? 0)+1)
  }
  // Preserve snapshot order within each group while promoting the exact name.
  if (job) matches.sort((a,b) => Number(b.name.toLowerCase()===job)-Number(a.name.toLowerCase()===job))
  return {
    schema:'talent-catalog-lookup/1', source:'local-snapshot', readAt:data.readAt, catalogCounts:data.counts,
    matchedJobs:matches.length, industries:chains.filter(row => matchedCounts.has(row.id))
      .map(row => ({...row, matchedJobs:matchedCounts.get(row.id)})),
    jobs:matches.slice(offset,offset+pageSize), nextOffset:offset+pageSize<matches.length ? offset+pageSize : null,
  }
}
