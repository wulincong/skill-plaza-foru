// Exercise the public handoff with synthetic observations, without database access.
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { validateRequest } from '../../../../scripts/talent-data/core.mjs'
import { buildPlan } from '../../../../scripts/talent-data/compile.mjs'
import { buildResult } from '../../../../scripts/talent-data/metrics.mjs'
import { persistResult } from '../../../../scripts/talent-data/artifacts.mjs'
import { parseDeliveredReport } from '../../../../web/server/lib/reportParse.ts'
import { publishDelivery } from '../../../../web/server/lib/delivery.ts'

const cli = fileURLToPath(new URL('./report.py', import.meta.url))
const template = JSON.parse(await readFile(new URL('../assets/templates.json', import.meta.url))).observation
const readAt = '2026-10-01T00:00:00Z'
const readJson = async path => JSON.parse(await readFile(path, 'utf8'))

async function savedResult(dir, n, partial) {
  const request = validateRequest({
    schema: 'talent-query/1', cohorts: [{id: 'all', filters: {region: {level:'national'}}}],
    metrics: partial ? ['positions.count', 'education.distribution', 'salary.summary'] : ['positions.count'],
  })
  const plan = buildPlan(request, request.cohorts.map(c => ({...c, fingerprint:'sample',
    resolved:{region:{name:'全国'}, industries:{entities:[],ids:[]}, roles:{entities:[],ids:[]}}})))
  const logs = plan.jobs.map(job => {
    let rows = [{count:n}]
    if (job.kind === 'salary') rows = [{status:'missing',mid:null,count:n}]
    if (job.kind === 'cube') rows = [{education:'BENKE',count:n-1},{education:'DAZHUAN',count:1}]
    return {...job,completed:true,rows}
  })
  const result = buildResult(request, plan, {logs,dataReadAt:readAt,startedAt:readAt})
  return persistResult(result, {fixture:true}, dir)
}

function draft(result) {
  const id = 'M1', sid = 'D1'
  return {
    title:'测试样本岗位观察',edition:'observation',region:'全国',industry:'不限',
    period:'在招截面',as_of:'2026-10-01',status:'draft',
    sources:[{id:sid,title:'测试结果',publisher:'测试',url:result.artifacts.result,locator:'all',
      published:'未标注',accessed:'2026-10-01',scope:'全国',excerpt:'岗位计数',
      dataReadAt:readAt,contentHash:result.contentHash}],
    metrics:[{id,label:'记录数',value:result.metrics.find(m => m.name==='positions.count').value,
      unit:'条',period:'在招截面',region:'全国',population:'平台岗位',definition:'按岗位去重',
      source_ids:[sid],binding:{metricId:'all/positions.count',field:'value'}}],
    claims:[{id:'C1',kind:'fact',text:'观测到平台岗位数。',metric_ids:[id],limitation:'仅限测试样本'}],
    sections:template.sections.map(s=>({id:s.id,claim_ids:['C1'],gap_ids:['G1']})),
    gaps:[{id:'G1',description:'缺院校材料',owner:'院校',required_data:'课程表',impact:'待核实课程建议'}],
    charts:[{id:'T1',title:'岗位计数',metric_ids:[id],note:'同一样本',type:'table'}],
  }
}

test('a verified result can be revised offline; changed values or artifacts cannot replace a delivery', async t => {
  const root=await mkdtemp(join(tmpdir(),'industry-report-'))
  t.after(()=>rm(root,{recursive:true,force:true}))
  const file=join(root,'report.json')
  const run=(...args)=>spawnSync('python3',[cli,...args],{cwd:root,encoding:'utf8'})
  await writeFile(join(root,'review.md'),'审核者逐项核对 C1 和 G1。')
  const result=await savedResult(root,4,true)
  assert.equal(result.status,'partial')
  const report=draft(result)
  report.metrics.push({...report.metrics[0], id:'edu', label:'学历分布',
    binding:{metricId:'all/education.distribution',field:'rows'}})
  delete report.metrics[1].value
  report.charts[0].metric_ids.push('edu')
  delete report.metrics[0].value
  delete report.sources[0].contentHash
  delete report.sources[0].dataReadAt
  await writeFile(file,JSON.stringify(report))
  const build=()=>run('build','report.json')
  const first=build()
  assert.equal(first.status,0,first.stderr+first.stdout)
  const manifest=await readJson(join(root,'delivery.json'))
  assert.equal(manifest.files.length,4)
  const revisionDir=join(root,manifest.files[0].path,'..')
  assert.ok((await stat(revisionDir)).mode & 0o2000)
  const canonical=await readJson(join(root,manifest.files.find(f=>f.path.endsWith('report.json')).path))
  assert.equal(canonical.sources[0].contentHash,result.contentHash)
  assert.equal(canonical.metrics[0].value,4)
  assert.equal(canonical.metrics[1].breakdown.denominator,4)
  assert.equal(canonical.metrics[1].breakdown.groups.length,2)
  const markdown=await readFile(join(root,manifest.files[0].path),'utf8')
  assert.match(markdown,/本科 \| 3 \| 75.0%/)
  const store=join(root,'delivery-store')
  const links=publishDelivery(root,manifest,store,'https://example.invalid')
  const parsed=parseDeliveredReport(links,store,'报告已生成')
  assert.equal(parsed.structurePass,true)
  assert.equal(parsed.stats.sources,1)
  assert.equal(parseDeliveredReport({},store,'我只想改标题。'),null)
  report.title='新标题'
  await writeFile(file,JSON.stringify(report))
  const revision=build()
  assert.equal(revision.status,0,revision.stderr+revision.stdout)
  const published=await readJson(join(root,'delivery.json'))
  assert.notEqual(published.files[0].path,manifest.files[0].path)
  await writeFile(join(root,'review.md'),'C10 已核对')
  assert.notEqual(build().status,0)
  assert.deepEqual(await readJson(join(root,'delivery.json')),published)
  await writeFile(join(root,'review.md'),'C1 已核对')
  report.metrics[0].value=5
  await writeFile(file,JSON.stringify(report))
  const changed=build()
  assert.notEqual(changed.status,0)
  assert.match(changed.stdout,/value differs/)
  assert.deepEqual(await readJson(join(root,'delivery.json')),published)
  report.metrics[0].value--
  report.metrics[0].binding.metricId='all/salary.summary'
  await writeFile(file,JSON.stringify(report))
  assert.match(build().stdout,/metric unavailable/)
  report.metrics[0].binding.metricId='all/positions.count'
  report.metrics[1].breakdown={groups:[]}
  await writeFile(file,JSON.stringify(report))
  assert.match(build().stdout,/分组明细与已验结果不一致/)
  delete report.metrics[1].breakdown
  await writeFile(file,JSON.stringify(report))
  await writeFile(join(root,result.artifacts.result),'{}')
  assert.match(build().stdout,/shared inspect failed/)
})

test('empty evidence is distinct from failed collection and an all-gap draft needs no table', async t=>{
  const root=await mkdtemp(join(tmpdir(),'industry-empty-'))
  t.after(()=>rm(root,{recursive:true,force:true}))
  const result=await savedResult(root,0,false)
  const report=draft(result)
  const validate=async()=>{
    await writeFile(join(root,'report.json'),JSON.stringify(report))
    const cliResult=spawnSync('python3',[cli,'validate','report.json'],{cwd:root,encoding:'utf8'})
    return JSON.parse(cliResult.stdout)
  }
  assert.equal(result.status,'empty')
  assert.equal(report.metrics[0].value,0)
  assert.equal((await validate()).structure_pass,true)
  report.sources=[]; report.metrics=[]; report.claims=[]; report.charts=[]
  report.sections.forEach(s=>{s.claim_ids=[]})
  assert.equal((await validate()).structure_pass,true)
  report.status='final'
  assert.equal((await validate()).structure_pass,false)
})
