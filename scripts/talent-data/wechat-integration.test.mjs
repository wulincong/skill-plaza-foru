import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtemp,readFile,writeFile,mkdir,cp,rm,stat} from 'node:fs/promises'
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
// Synthetic analysis tests the protocol, not the quality of real research prose.
async function analyze(f) {
  run(f.cwd,'report_analysis.py')
  const root=join(f.cwd,'output/analysis')
  const draft=JSON.parse(await readFile(join(root,'analysis_draft.json')))
  const pack=JSON.parse(await readFile(join(root,'analysis_evidence.json')))
  const domains=[...new Set(pack.findings.map(x=>x.section))]
  const executive=domains.slice(0,3).map(key=>pack.findings.find(x=>x.section===key).id)
  draft.executive={findingIds:executive,synthesis:'合成夹具仅检验分析与指标之间的绑定关系，类别分布与交叉结果应分别解释，不能推断真实产业发展情况。'}
  for(const s of draft.sections) {
    s.findingIds=pack.findings.filter(x=>x.section===s.key).slice(0,5).map(x=>x.id)
    s.title=`合成样本的${s.key.replaceAll('_',' ')}结构需复核`
    s.interpretation=`对${s.key}合成分布的解释仅限已声明的统计对象，样本差异需要与总体规模和字段覆盖一起考察。`
    s.action=`围绕${s.key}配置独立的岗位复核任务，将样本条件交给合作企业确认后再形成课程案例。`
    s.validation=`核查${s.key}相关记录的统计口径与企业实际岗位条件，保存访谈结果并记录未能解释的差异。`
  }
  draft.limitations=['该数据为合成测试夹具，仅验证分析协议与报告生成，不能作为真实产业或院校培养结论。']
  await writeFile(join(f.cwd,'report_analysis.json'),JSON.stringify(draft))
  return {draft,pack}
}
async function outline(f) {await analyze(f);return run(f.cwd,'gen_outline.py')}
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
  await outline(f)
  run(f.cwd,'verify_data.py',['--stage','data'])
  run(f.cwd,'evidence_sheet.py')
  const check=spawnSync(python,['-c','from openpyxl import load_workbook; import sys; w=load_workbook(sys.argv[1]); print(w["实际查询"].max_row)',join(f.cwd,'output/internal/evidence_核查表.xlsx')],{cwd:f.cwd,encoding:'utf8'})
  assert.equal(check.status,0,check.stderr)
  assert.equal(Number(check.stdout),f.plan.queryCount+1)
})
test('wrong city/post claims and wrong chart values fail their specific projections',async t=>{
  const f=await setup(t);adapt(f);await outline(f)
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
test('empty samples stop research reports; unavailable salary remains an explicit coverage gap',async t=>{
  for(const option of [{empty:true},{noSalary:true}]) {
    const f=await setup(t,{},option);adapt(f)
    const d=JSON.parse(await readFile(join(f.cwd,'report_data.json')))
    if(option.noSalary){await outline(f);run(f.cwd,'verify_data.py');assert.equal(d.coverage.find(c=>c.section==='salary').status,'unavailable')}
    else {assert.equal(d.total.positions,0);run(f.cwd,'report_analysis.py',[],1);run(f.cwd,'gen_outline.py',[],1)}
  }
})
test('missing render files cannot pass final acceptance',async t=>{
  const f=await setup(t);adapt(f);await outline(f)
  run(f.cwd,'verify_data.py',['--stage','final'],1)
})

test('public delivery contains a standalone website and ZIP, excluding internal evidence',async t=>{
  const f=await setup(t);adapt(f);await outline(f)
  const outlineBytes=await readFile(join(f.cwd,'output/outline/report_outline.json'))
  const reportOutline=JSON.parse(outlineBytes)
  await mkdir(join(f.cwd,'output/report/pages'),{recursive:true})
  const pages=[]
  for(let i=0;i<reportOutline.screens.length;i++) {
    const file=`pages/page_${i}.png`
    pages.push({index:i,file,name:reportOutline.screens[i].title})
  }
  const generated=spawnSync(python,['-c',
    'from PIL import Image\nimport sys\nfor i, path in enumerate(sys.argv[1:]): Image.new("RGB",(8,12),(i,0,0)).save(path)',
    ...pages.map(p=>join(f.cwd,'output/report',p.file))],{encoding:'utf8'})
  assert.equal(generated.status,0,generated.stderr)
  for(const page of pages) page.sha256=createHash('sha256').update(await readFile(join(f.cwd,'output/report',page.file))).digest('hex')
  const manifestPath=join(f.cwd,'output/report/manifest.json')
  const manifest={pages,outline_sha256:createHash('sha256').update(outlineBytes).digest('hex')}
  await writeFile(manifestPath,JSON.stringify(manifest))
  await mkdir(join(f.cwd,'output/internal'),{recursive:true})
  await writeFile(join(f.cwd,'output/internal/evidence.xlsx'),'PRIVATE SQL')
  run(f.cwd,'build_article.py')
  run(f.cwd,'pack_delivery.py',['--workspace',f.cwd],1) // No final quality receipt: refuse delivery.
  // Protocol fixture only, not a visual-quality or renderer test.
  await writeFile(join(f.cwd,'output/report/quality.json'),JSON.stringify({schema:'wechat-quality/1',all_pass:true,outline_sha256:manifest.outline_sha256,manifest_sha256:createHash('sha256').update(await readFile(manifestPath)).digest('hex')}))
  run(f.cwd,'pack_delivery.py',['--workspace',f.cwd])
  const delivery=JSON.parse(await readFile(join(f.cwd,'delivery.json')))
  assert.equal(delivery.web[0].entry,'index.html')
  assert.equal(delivery.files.length,1)
  const site=join(f.cwd,delivery.web[0].directory)
  assert.equal((await stat(join(f.cwd,'delivery.json'))).mode & 0o777,0o640)
  assert.equal((await stat(site)).mode & 0o050,0o050)
  const html=await readFile(join(site,'index.html'),'utf8')
  assert.match(html,/<meta name="viewport"/)
  const references=[...html.matchAll(/src="([^"]+)"/g)].map(m=>m[1])
  assert.equal(references.length,reportOutline.screens.length)
  for(const asset of references) assert((await readFile(join(site,asset))).length>0)
  assert.doesNotMatch(html,/file:\/\/|PRIVATE SQL|report_binding/)
  assert.match(html,/<main>(?:<img [^>]+>)+<\/main>/)
  assert.doesNotMatch(html,/<(?:p|section|h[1-6])\b/)
  assert.deepEqual(references,pages.map((_,i)=>`assets/page_${String(i+1).padStart(2,'0')}.png`))
  const zip=spawnSync(python,['-c',[
    'import sys,zipfile,pathlib',
    'z=zipfile.ZipFile(sys.argv[1]); files=sys.argv[2:]; names=z.namelist()',
    'assert [pathlib.Path(n).name for n in names] == [pathlib.Path(f).name for f in files]',
    'assert all(z.read(n)==pathlib.Path(f).read_bytes() for n,f in zip(names,files))'
  ].join('\n'),join(f.cwd,delivery.files[0].path),...references.map(p=>join(site,p))],{encoding:'utf8'})
  assert.equal(zip.status,0,zip.stderr)
  await writeFile(manifestPath,JSON.stringify({...manifest,pages:[...pages].reverse()}))
  run(f.cwd,'pack_delivery.py',['--workspace',f.cwd],1)
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
  await outline(f);run(f.cwd,'verify_data.py')
})
test('claim subject bindings reject a company count passed as a job count',async t=>{
  const f=await setup(t);adapt(f);await outline(f)
  const path=join(f.cwd,'output/outline/report_outline.json')
  const ol=JSON.parse(await readFile(path))
  const spec=ol.bindings['/screens/1/paragraphs/0']
  spec.inputs['0'].path='/total/companies'
  ol.screens[1].paragraphs[0]='本次样本覆盖 2 条在招岗位记录，关联 2 家企业。'
  await writeFile(path,JSON.stringify(ol))
  run(f.cwd,'verify_data.py',[],1)
})
test('no description coverage does not produce a fictitious empty skill chart',async t=>{
  const f=await setup(t,{}, {noDescription:true});adapt(f);await outline(f);run(f.cwd,'verify_data.py')
  const d=JSON.parse(await readFile(join(f.cwd,'report_data.json')))
  assert.equal(d.coverage.find(c=>c.section==='skills').status,'unavailable')
  const ol=JSON.parse(await readFile(join(f.cwd,'output/outline/report_outline.json')))
  assert(!ol.screens.some(s=>s.analysis_key==='skills'))
})

test('report cannot be generated or delivered by skipping analysis',async t=>{
  const f=await setup(t);adapt(f)
  run(f.cwd,'gen_outline.py',[],1)
  run(f.cwd,'report_analysis.py')
  await cp(join(f.cwd,'output/analysis/analysis_draft.json'),join(f.cwd,'report_analysis.json'))
  run(f.cwd,'gen_outline.py',[],1)
  await outline(f)
  const path=join(f.cwd,'output/outline/report_outline.json')
  const ol=JSON.parse(await readFile(path));delete ol.analysis
  await writeFile(path,JSON.stringify(ol))
  run(f.cwd,'verify_data.py',[],1)
  run(f.cwd,'render_report.py',[],1)
  run(f.cwd,'build_article.py',[],1)
  run(f.cwd,'pack_delivery.py',['--workspace',f.cwd],1)
})

test('analysis rejects stale evidence, irrelevant comparisons, missing dimensions and repeated advice',async t=>{
  const f=await setup(t);adapt(f)
  const {draft}=await analyze(f)
  const file=join(f.cwd,'report_analysis.json')
  for(const mutate of [
    a=>{a.sourceContentHash='stale'},
    a=>{a.evidenceHash='tampered'},
    a=>{a.executive.findingIds=['salary.quantiles','salary.coverage','salary.modal_band']},
    a=>{a.sections.pop()},
    a=>{a.coverageGaps=[];a.coverageGaps.push({section:'invented',status:'complete'})},
    a=>{a.sections[0].findingIds=['salary.quantiles','salary.coverage']},
    a=>{a.sections[1].action=a.sections[0].action},
    a=>{a.sections[0].interpretation='需求增长最快且提升了99%，应扩大培养规模。'},
  ]) {
    const a=structuredClone(draft);mutate(a);await writeFile(file,JSON.stringify(a))
    run(f.cwd,'gen_outline.py',[],1)
  }
})

test('derived facts preserve conditional denominators and omissions cannot masquerade as analysis',async t=>{
  const f=await setup(t);adapt(f)
  const {pack}=await analyze(f)
  const d=JSON.parse(await readFile(join(f.cwd,'report_data.json')))
  const fact=pack.findings.find(x=>x.id==='access.conditional')
  const top=[...d.edu_exp].sort((a,b)=>b[2]-a[2]||a[0].localeCompare(b[0]))[0]
  assert.equal(fact.denominator,d.edu_exp.filter(x=>x[0]===top[0]).reduce((n,x)=>n+x[2],0))
  assert.equal(fact.numerator,top[2])
  run(f.cwd,'gen_outline.py')
  const path=join(f.cwd,'output/outline/report_outline.json')
  const ol=JSON.parse(await readFile(path))
  ol.screens.find(s=>s.analysis_key==='education').paragraphs.pop()
  await writeFile(path,JSON.stringify(ol));run(f.cwd,'verify_data.py',[],1)
})

test('observed skill labels may contain digits while invented numeric assertions remain blocked',async t=>{
  const f=await setup(t);adapt(f)
  const {draft}=await analyze(f)
  const section=draft.sections.find(s=>s.key==='skills')
  section.action='根据实际词表核实ROS2提及对应的岗位职责，记录企业需要的任务证据，再决定是否设计相关实训。'
  const path=join(f.cwd,'report_analysis.json')
  await writeFile(path,JSON.stringify(draft));run(f.cwd,'gen_outline.py');run(f.cwd,'verify_data.py')
  section.action+='预计可提高20%的就业率。'
  await writeFile(path,JSON.stringify(draft));run(f.cwd,'gen_outline.py',[],1)
})

test('a count-only query cannot be relabeled as a completed research report',async t=>{
  const f=await setup(t,{metrics:['positions.count','companies.count','data_quality.summary']});adapt(f)
  await analyze(f)
  run(f.cwd,'gen_outline.py',[],1)
})
