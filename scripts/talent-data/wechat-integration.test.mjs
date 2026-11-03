import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,readFile,writeFile,mkdir,cp,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {fileURLToPath} from 'node:url'
import {spawnSync} from 'node:child_process'
import {createHash} from 'node:crypto'
import {result,analysis} from './test-fixtures/analysis-fixture.mjs'
import {persistResult} from './artifacts.mjs'
import {buildRequest} from '../../.agents/skills/wechat-report/scripts/collect_data.mjs'

const installed=fileURLToPath(new URL('../../.agents/skills/wechat-report/',import.meta.url))
const queryCli=fileURLToPath(new URL('../talent-data-query.mjs',import.meta.url))
const python=join(installed,'.venv/bin/python')
async function setup(t,extra={},options={}) {
  const cwd=await mkdtemp(join(tmpdir(),'wechat query integration-'))
  t.after(()=>rm(cwd,{recursive:true,force:true}))
  await cp(join(installed,'scripts'),join(cwd,'scripts'),{recursive:true})
  await mkdir(join(cwd,'assets'))
  for(const name of ['brand.json','themes.json','echarts.min.js'])await cp(join(installed,'assets',name),join(cwd,'assets',name))
  const f=result(extra,options)
  await persistResult(f.result,{schema:'talent-evidence/1',queries:f.execution.logs},cwd,[])
  return {...f,cwd}
}
function run(cwd,name,args=[],expected=0,env={}) {
  const proc=spawnSync(name.endsWith('.mjs')?process.execPath:python,[name.endsWith('.mjs')?name:join(cwd,'scripts',name),...args],{cwd,encoding:'utf8',timeout:15000,env:{...process.env,...env},maxBuffer:4*1024*1024})
  assert.equal(proc.status,expected,proc.stderr+proc.stdout)
  return proc
}
function adapt(f) {
  return run(f.cwd,join(installed,'scripts/collect_data.mjs'),['--result',f.result.artifacts.result,'--query-cli',queryCli])
}
test('report request preserves scope, intersects vocational filters, and never adds an implicit time window',()=>{
  const plan={schema:'wechat-report-plan/1',filters:{region:{level:'national'},education:['BENKE']}}
  const r=buildRequest(plan)
  assert.equal(r.cohorts.length,1)
  assert(!r.cohorts[0].filters.updatedAt)
  assert(!r.cohorts[0].filters.industries)
  const two=buildRequest({...plan,filters:{...plan.filters,education:['BENKE','DAZHUAN'],experience:['GRADUATING','LESS_THAN_5']}})
  assert.deepEqual(two.cohorts[1].filters.education,['DAZHUAN'])
  assert.deepEqual(two.cohorts[1].filters.experience,['GRADUATING'])
  assert.throws(()=>buildRequest({...plan,sections:['made-up']}))
})
test('saved shared results generate an outline, article inputs and actual audit workbook without querying',async t=>{
  const f=await setup(t);adapt(f)
  const d=JSON.parse(await readFile(join(f.cwd,'report_data.json')))
  assert.equal(d.total.positions,4);assert.equal(d.total.cities,2)
  assert.equal(d.salary.median,10.5)
  run(f.cwd,'gen_outline.py')
  run(f.cwd,'verify_data.py',['--stage','data'])
  run(f.cwd,'evidence_sheet.py')
  const check=spawnSync(python,['-c','from openpyxl import load_workbook; import sys; w=load_workbook(sys.argv[1]); print(w["实际查询"].max_row)',join(f.cwd,'output/internal/evidence_核查表.xlsx')],{cwd:f.cwd,encoding:'utf8'})
  assert.equal(check.status,0,check.stderr)
  assert.equal(Number(check.stdout),f.plan.queryCount+1)
})
test('wrong city/post claims and wrong chart values fail their specific projections',async t=>{
  const f=await setup(t);adapt(f);run(f.cwd,'gen_outline.py')
  const path=join(f.cwd,'output/outline/report_outline.json')
  const original=JSON.parse(await readFile(path))
  const changed=structuredClone(original)
  changed.screens[1].paragraphs[0]='本次样本覆盖 2 条在招岗位记录，关联 2 家企业。'
  await writeFile(path,JSON.stringify(changed))
  run(f.cwd,'verify_data.py',[],1)
  const graph=structuredClone(original)
  graph.screens.find(s=>s.chart?.data?.length).chart.data[0][1]=999
  await writeFile(path,JSON.stringify(graph))
  run(f.cwd,'verify_data.py',[],1)
})
test('tampered report data or original aggregate artifacts cannot be used',async t=>{
  const f=await setup(t);adapt(f)
  const path=join(f.cwd,'report_data.json'),original=await readFile(path)
  const d=JSON.parse(original);d.total.positions=999;await writeFile(path,JSON.stringify(d))
  run(f.cwd,'gen_outline.py',[],1)
  await writeFile(path,original)
  const source=join(f.cwd,f.result.artifacts.result)
  const r=JSON.parse(await readFile(source));r.metrics[0].value=999;await writeFile(source,JSON.stringify(r))
  run(f.cwd,'gen_outline.py',[],1)
})
test('empty data and unavailable salaries remain usable with explicit report coverage',async t=>{
  for(const option of [{empty:true},{noSalary:true}]) {
    const f=await setup(t,{},option);adapt(f);run(f.cwd,'gen_outline.py');run(f.cwd,'verify_data.py',[],0)
    const d=JSON.parse(await readFile(join(f.cwd,'report_data.json')))
    if(option.noSalary)assert.equal(d.coverage.find(c=>c.section==='salary').status,'unavailable')
    else assert.equal(d.total.positions,0)
  }
})
test('missing render files cannot pass final acceptance',async t=>{
  const f=await setup(t);adapt(f);run(f.cwd,'gen_outline.py')
  run(f.cwd,'verify_data.py',['--stage','final'],1)
})

test('public delivery contains a standalone website and ZIP, excluding internal evidence',async t=>{
  const f=await setup(t);adapt(f);run(f.cwd,'gen_outline.py')
  const outlineBytes=await readFile(join(f.cwd,'output/outline/report_outline.json'))
  const outline=JSON.parse(outlineBytes)
  await mkdir(join(f.cwd,'output/report/pages'),{recursive:true})
  const pages=[]
  for(let i=0;i<outline.screens.length;i++) {
    const file=`pages/page_${i}.png`
    await writeFile(join(f.cwd,'output/report',file),Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jf1kAAAAASUVORK5CYII=','base64'))
    pages.push({index:i,file,name:outline.screens[i].title})
  }
  await writeFile(join(f.cwd,'output/report/manifest.json'),JSON.stringify({pages,outline_sha256:createHash('sha256').update(outlineBytes).digest('hex')}))
  await mkdir(join(f.cwd,'output/internal'),{recursive:true})
  await writeFile(join(f.cwd,'output/internal/evidence.xlsx'),'PRIVATE SQL')
  run(f.cwd,'build_article.py')
  run(f.cwd,'pack_delivery.py',['--workspace',f.cwd])
  const delivery=JSON.parse(await readFile(join(f.cwd,'delivery.json')))
  assert.equal(delivery.web[0].entry,'index.html')
  assert.equal(delivery.files.length,1)
  const site=join(f.cwd,delivery.web[0].directory)
  const html=await readFile(join(site,'index.html'),'utf8')
  assert.match(html,/<meta name="viewport"/)
  const references=[...html.matchAll(/src="([^"]+)"/g)].map(m=>m[1])
  assert.equal(references.length,outline.screens.length)
  for(const asset of references) assert((await readFile(join(site,asset))).length>0)
  assert.doesNotMatch(html,/file:\/\/|PRIVATE SQL|report_binding/)
  const zip=spawnSync(python,['-c','import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print("\\n".join(z.namelist())); assert all("internal" not in x and "binding" not in x and "evidence" not in x for x in z.namelist())',join(f.cwd,delivery.files[0].path)],{encoding:'utf8'})
  assert.equal(zip.status,0,zip.stderr)
  assert.match(zip.stdout,/article\/article.html/)
})
test('collector plan executes only the public shared CLI, including its framed adapter and evidence',async t=>{
  const plan={schema:'wechat-report-plan/1',filters:{region:{level:'national'}},sections:['overview','geography','requirements','salary','vocational','tracks','city_tracks','track_salary','skills','track_skills'],analysis,execution:{freshness:'live'}}
  const request=buildRequest(plan)
  const f=await setup(t,request)
  const response=Object.fromEntries(f.execution.logs.map(j=>[j.id,j.rows]))
  response.capability=['c_company_position','c_company_address','c_position_chain'].map(name=>({name,engine:'InnoDB'}))
  await writeFile(join(f.cwd,'responses.json'),JSON.stringify(response))
  const peer=join(f.cwd,'mysql-peer.mjs')
  const source=[
    '#!/usr/bin/env node',
    "import {readFileSync} from 'node:fs'",
    "let text='';for await(const chunk of process.stdin)text+=chunk",
    "const ids=[...text.matchAll(/'_talent','begin','id',CONVERT\\(X'([0-9a-f]+)'/g)].map(m=>Buffer.from(m[1],'hex').toString())",
    "const responses=JSON.parse(readFileSync(process.env.WECHAT_RESPONSES,'utf8'))",
    "const emit=x=>process.stdout.write(JSON.stringify(x)+'\\n')",
    "emit({_talent:'snapshot',sourceReadTime:'2026-11-02 00:00:00'})",
    "for(const id of ids){emit({_talent:'begin',id});if(!responses[id])process.exit(2);for(const row of responses[id])emit({row});emit({_talent:'end',id})}",
    "emit({_talent:'finished'})"
  ].join('\n')
  await writeFile(peer,source,{mode:0o700})
  await writeFile(join(f.cwd,'plan.json'),JSON.stringify(plan))
  run(f.cwd,join(installed,'scripts/collect_data.mjs'),['--plan','plan.json','--query-cli',queryCli],0,{MYSQL_HOST:'fixture',MYSQL_USER:'fixture',MYSQL_PASSWORD:'fixture',MYSQL_DATABASE:'fixture',MYSQL_BIN:peer,TALENT_QUERY_STATE_DIR:join(f.cwd,'state'),WECHAT_RESPONSES:join(f.cwd,'responses.json')})
  const d=JSON.parse(await readFile(join(f.cwd,'report_data.json')))
  assert.equal(d.total.positions,4);assert.equal(d.voc_pool.count,2)
  run(f.cwd,'gen_outline.py');run(f.cwd,'verify_data.py')
})
test('claim subject bindings reject a company count passed as a job count',async t=>{
  const f=await setup(t);adapt(f);run(f.cwd,'gen_outline.py')
  const path=join(f.cwd,'output/outline/report_outline.json')
  const ol=JSON.parse(await readFile(path))
  const spec=ol.bindings['/screens/1/paragraphs/0']
  spec.inputs.n.path='/total/companies'
  ol.screens[1].paragraphs[0]='本次样本覆盖 2 条在招岗位记录，关联 2 家企业。'
  await writeFile(path,JSON.stringify(ol))
  run(f.cwd,'verify_data.py',[],1)
})
test('no description coverage does not produce a fictitious empty skill chart',async t=>{
  const f=await setup(t,{}, {noDescription:true});adapt(f);run(f.cwd,'gen_outline.py');run(f.cwd,'verify_data.py')
  const d=JSON.parse(await readFile(join(f.cwd,'report_data.json')))
  assert.equal(d.coverage.find(c=>c.section==='skills').status,'unavailable')
  const ol=JSON.parse(await readFile(join(f.cwd,'output/outline/report_outline.json')))
  assert(!ol.screens.some(s=>s.title==='人才能力关键词'))
})
