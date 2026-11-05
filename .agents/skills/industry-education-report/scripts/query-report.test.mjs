// Exercise the public handoff with synthetic observations, without database access.
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { validateRequest } from '../../../../scripts/talent-data/core.mjs'
import { buildPlan } from '../../../../scripts/talent-data/compile.mjs'
import { buildResult } from '../../../../scripts/talent-data/metrics.mjs'
import { persistResult } from '../../../../scripts/talent-data/artifacts.mjs'
import { expectsIndustryBuild, industryDelivery, parseDeliveredReport } from '../../../../web/server/lib/reportParse.ts'
import { deliveryFingerprint, handleDelivery, publishDelivery } from '../../../../web/server/lib/delivery.ts'

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
  report.claims[0].metric_ids.push('edu')
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
  report.sources=[]; report.metrics=[]; report.claims=[]
  report.sections.forEach(s=>{s.claim_ids=[]})
  assert.equal((await validate()).structure_pass,true)
  report.status='final'
  assert.equal((await validate()).structure_pass,false)
})

test('the decision brief waits for the user on a material gap; minor gaps do not block an answer', async t=>{
  const root=await mkdtemp(join(tmpdir(),'industry-choice-'))
  t.after(()=>rm(root,{recursive:true,force:true}))
  const cliRun=command=>spawnSync('python3',[cli,command,'report.json'],{cwd:root,encoding:'utf8'})
  const quote='按现有证据继续，是否增班留作未决。'
  const excerpt='企业希望练习安全停机与复位。'
  const source={id:'T',title:'访谈',publisher:'企业',url:'user:访谈',locator:'第2条',excerpt,
    published:'未标注',accessed:'2026-11-04',scope:'本次调研'}
  const report={
    title:'是否增开实训班',edition:'decision',region:'佛山',industry:'机器人',period:'下学期',as_of:'2026-11-04',
    status:'draft',decision:{reader:'专业负责人',question:'能否新增一个班？',critical_gap_ids:['G']},
    sources:[source],metrics:[],
    claims:[{id:'C',kind:'inference',text:'可把复位操作纳入校企访谈。',basis:excerpt,implication:'应先核实工位。',limitation:'单次访谈',source_ids:['T']}],
    gaps:[{id:'G',description:'缺实训室排课表',owner:'教务处',required_data:'空闲课时',impact:'能否增班未决'}],
    sections:['D01','D02','D03'].map(id=>({id,claim_ids:['C'],gap_ids:['G']})),
  }
  const save=()=>writeFile(join(root,'report.json'),JSON.stringify(report))
  const runId='20261104-121314-test'
  let previousBuildRun
  const context=(message,offered,uploads=[])=>writeFile(join(root,'industry-report-input.json'),
    JSON.stringify({runId,previousBuildRun,message,offered,earlierMessages:[excerpt],uploads}))
  await save(); await writeFile(join(root,'review.md'),'C 已核对访谈。')
  await context('请直接生成报告',false)
  for (const command of ['preview','build']) assert.notEqual(cliRun(command).status,0)
  await assert.rejects(readFile(join(root,'delivery.json')), {code:'ENOENT'})
  report.decision.continue_quote='请直接生成报告'
  await save()
  assert.notEqual(cliRun('build').status,0)
  report.decision.continue_quote='按现有证据继续'
  await save()
  for (const answer of ['不要按现有证据继续，我先补材料。','暂时不按现有证据继续','按现有证据继续？']) {
    await context(answer,true)
    assert.notEqual(cliRun('build').status,0)
  }
  report.decision.continue_quote=quote
  await save(); await context('扩大范围',true)
  assert.notEqual(cliRun('build').status,0)
  await context(quote,true)
  report.decision.critical_gap_ids=[]
  await save()
  assert.notEqual(cliRun('build').status,0)
  report.decision.critical_gap_ids=['G']
  await save()
  let built=cliRun('build')
  assert.equal(built.status,0,built.stderr+built.stdout)
  let manifest=await readJson(join(root,'delivery.json'))
  previousBuildRun=runId
  await writeFile(join(root,'delivery.json'),JSON.stringify({files:[{name:'模型另打的包',path:'output/report.zip'}]}))
  const declared=industryDelivery(root,runId,undefined,'按现有证据继续')
  assert.deepEqual(declared.files,manifest.files)
  assert.equal(industryDelivery(root,runId,undefined,'请提供压缩包').files.length,5)
  assert.throws(()=>industryDelivery(root,'20261104-121500-test',undefined,'交付报告'),/未通过本轮 build/)
  const original=await readFile(join(root,manifest.files[0].path),'utf8')
  assert.match(original,/能否增班未决/)
  assert.match(original,/企业希望练习安全停机与复位。 应先核实工位。/)
  const links=publishDelivery(root,manifest,join(root,'store'),'https://example.invalid')
  const parsed=parseDeliveredReport(links,join(root,'store'),'已完成')
  assert.equal(parsed.structurePass,true)
  assert.equal(parsed.stats.inferences,1)
  await writeFile(join(root,declared.files[0].path), original + '伪造结论')
  assert.throws(()=>publishDelivery(root,declared,join(root,'store'),'https://example.invalid'),/核验的内容不一致/)
  await writeFile(join(root,declared.files[0].path),original)
  await context('改一下标题',false)
  report.decision.critical_gap_ids=[]
  await save()
  assert.notEqual(cliRun('build').status,0)
  report.decision.critical_gap_ids=['G']
  report.title='校企实训安排'; await save()
  built=cliRun('build'); assert.equal(built.status,0,built.stderr+built.stdout)
  manifest=await readJson(join(root,'delivery.json'))
  report.region='珠海'; await save()
  assert.notEqual(cliRun('build').status,0)
  assert.deepEqual(await readJson(join(root,'delivery.json')),manifest)
  report.decision.critical_gap_ids=[]; delete report.decision.continue_quote
  report.status='final'; await context('补充了排课证据，请重新判断。',true); await save()
  assert.equal(cliRun('build').status,0)
  source.excerpt='新增训练一定可行'; await save()
  assert.match(cliRun('build').stdout,/excerpt/)
  await mkdir(join(root,'uploads'))
  source.url='uploads/访谈.md'
  await writeFile(join(root,source.url),excerpt)
  await context('按提供的访谈写简报',false,[source.url])
  await save()
  assert.match(cliRun('validate').stdout,/不在上传文件原文/)
  source.excerpt=excerpt
  delete report.claims[0].basis; await save()
  assert.match(cliRun('validate').stdout,/missing basis/)
})

test('a requested industry report website and its assets are served alongside the four verified files', async t => {
  const root = await mkdtemp(join(tmpdir(), 'industry-site-'))
  t.after(() => rm(root, {recursive:true, force:true}))
  const runId = '20261104-150053-cwtb'
  const request = '生成网页版报告，注意图文结合'
  const report = draft(await savedResult(root,4,false))
  report.decision = {reader:'专业负责人',question:'调研样本覆盖多少岗位？',critical_gap_ids:[]}
  Object.assign(report.claims[0], {basis:'同一查询结果记录了岗位数。',implication:'按这个样本解释岗位范围。'})
  await writeFile(join(root,'industry-report-input.json'), JSON.stringify({runId,message:request,offered:false,earlierMessages:[],uploads:[]}))
  await writeFile(join(root,'report.json'), JSON.stringify(report))
  await writeFile(join(root,'review.md'), 'C1 已复核岗位计数。')
  const built = spawnSync('python3',[cli,'build','report.json'],{cwd:root,encoding:'utf8'})
  assert.equal(built.status,0,built.stderr+built.stdout)
  const originals = (await readJson(join(root,'industry-build-'+runId+'.json'))).files
  assert.equal(originals.length,4)
  const page = {name:'报告网页版',directory:'output/public/site',entry:'index.html'}
  const html = '<!doctype html><title>产业人才报告</title><link rel="stylesheet" href="report.css">'
  const css = 'body { color: #123; }'
  await mkdir(join(root,page.directory),{recursive:true})
  await writeFile(join(root,page.directory,page.entry),html)
  await writeFile(join(root,page.directory,'report.css'),css)
  const beforeWeb = deliveryFingerprint(root)
  await writeFile(join(root,'delivery.json'),JSON.stringify({
    web:[page],files:[{name:'无关文件',path:'output/public/site/index.html'}],
  }))
  const store = join(root,'published')
  const server = createServer((req,res) => {
    if (!handleDelivery(req,res,store)) { res.writeHead(404); res.end() }
  })
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
  t.after(()=>new Promise(resolve=>server.close(resolve)))
  const origin = 'http://127.0.0.1:'+server.address().port
  const manifest = industryDelivery(root,runId,beforeWeb,request)
  assert.deepEqual(manifest.files,originals)
  const links = publishDelivery(root,manifest,store,origin)
  assert.deepEqual(links.webLinks?.map(link=>link.name),[page.name])
  const publishedPage = await fetch(links.webLinks[0].url)
  assert.equal(publishedPage.status,200)
  assert.equal(await publishedPage.text(),html)
  const stylesheet = await fetch(new URL('report.css',publishedPage.url))
  assert.equal(stylesheet.status,200)
  assert.equal(await stylesheet.text(),css)
  assert.deepEqual(links.downloads.map(link=>link.name),originals.map(f=>f.name))
  for (const [i, download] of links.downloads.entries()) {
    const response = await fetch(download.url)
    assert.equal(response.status,200)
    assert.deepEqual(Buffer.from(await response.arrayBuffer()),await readFile(join(root,originals[i].path)))
  }
  assert.throws(()=>industryDelivery(root,'20261104-150054-other',beforeWeb,request),/未通过本轮 build/)
  assert.throws(()=>industryDelivery(root,runId,deliveryFingerprint(root),request),/网页/)
  assert.deepEqual(industryDelivery(root,runId,beforeWeb,'把图例改一下').web,[page])
  for (const message of ['只要正文，不要网页版','网页报告的证据足够么','参考网页报告，生成 Markdown']) {
    const filesOnly = industryDelivery(root,runId,beforeWeb,message)
    assert.deepEqual(filesOnly.files,originals)
    assert.equal(filesOnly.web?.length ?? 0,0)
  }
  assert.equal(expectsIndustryBuild('为什么没有生成网页版报告',''),false)
  await writeFile(join(root,'delivery.json'),JSON.stringify({files:originals}))
  assert.throws(()=>industryDelivery(root,runId,beforeWeb,request),/网页/)
  const ordinary = industryDelivery(root,runId,beforeWeb,'生成决策报告')
  assert.deepEqual(ordinary.files,originals)
  assert.equal(ordinary.web?.length ?? 0,0)
  await writeFile(join(root,'delivery.json'),JSON.stringify({web:[{...page,directory:'uploads'}]}))
  assert.throws(()=>publishDelivery(root,industryDelivery(root,runId,beforeWeb,request),store,origin))
})
