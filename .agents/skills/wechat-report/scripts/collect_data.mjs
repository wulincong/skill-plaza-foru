#!/usr/bin/env node
// Only the public talent-data-query CLI is a dependency. Works from a session cwd.
import {readFile,writeFile,mkdir,realpath,access} from 'node:fs/promises'
import {resolve,dirname,join,relative} from 'node:path'
import {fileURLToPath} from 'node:url'
import {execFile} from 'node:child_process'
import {promisify} from 'node:util'
import {createHash,randomUUID} from 'node:crypto'
import {performance} from 'node:perf_hooks'
import {adaptResult,ADAPTER_VERSION} from './adapt_query_result.mjs'
const exec=promisify(execFile),sha=x=>createHash('sha256').update(x).digest('hex')
export const SECTION_METRICS={overview:['positions.count','companies.count','data_quality.summary'],geography:['city_education.cross','city_salary.summary'],requirements:['education.distribution','experience.distribution','jobType.distribution','education_experience.cross'],salary:['salary.summary','salary.distribution'],vocational:['education_experience.cross','city.distribution','salary.summary','salary.distribution'],tracks:['track.distribution'],city_tracks:['city_track.cross'],lq:['city_track.cross'],track_salary:['track.distribution','track_salary.summary'],skills:['skills.distribution'],track_skills:['track.distribution','skills.distribution','track_skills.cross']}
const VOC_EDU=['DAZHUAN','GAOZHI','ZHONGZHUAN/ZHONGJI','GAOZHONG','CHUZHONGJIYIXIA','BUXIAN'],VOC_EXP=['ON_CAMPUS','GRADUATING','LESS_THAN_1','BUXIAN']
export function applyProfile(plan,profile) {
  if(plan.industryLabel&&plan.industryLabel!==profile.name)throw new Error('报告产业标签与所选分析规则不一致')
  if(plan.analysis&&JSON.stringify(plan.analysis)!==JSON.stringify(profile.analysis))throw new Error('不能同时提交不同的analysis与profile')
  return {...plan,industryLabel:profile.name,sections:plan.sections??profile.sections,audience:plan.audience??profile.audience,analysis:profile.analysis}
}
export function validateProfileScope(plan,profile,candidates) {
  const roots=candidates.filter(row=>row.level===0&&row.name===profile.name)
  const selected=plan.filters?.industries??[]
  if(roots.length!==1||selected.length!==1||selected[0].id!==roots[0].id||selected[0].includeDescendants===false)throw new Error('使用产业规则须显式选择已解析的唯一对应根产业ID及其子树；不能自动增删产业条件')
}
export function reportSections(plan) {
  const requested=plan.sections??['overview','geography','requirements','salary','vocational']
  if(!Array.isArray(requested)||!requested.length||requested.some(s=>!Object.hasOwn(SECTION_METRICS,s)))throw new Error('报告章节不支持')
  // This is an additional same-filter statistic, never a wider cohort. Include
  // it before the first query so prose cannot finish before city data is ready.
  return [...new Set(['overview','geography',...requested])]
}
export function buildRequest(plan) {
  if(plan.schema!=='wechat-report-plan/1'||!plan.filters?.region)throw new Error('需要 wechat-report-plan/1 和明确 filters.region')
  const allowed=['schema','filters','sections','analysis','audience','industryLabel','execution']
  if(Object.keys(plan).some(k=>!allowed.includes(k)))throw new Error('报告计划包含不支持的字段')
  const sections=reportSections(plan)
  const metrics=[...new Set(['positions.count','companies.count','data_quality.summary',...sections.flatMap(s=>SECTION_METRICS[s])])]
  const cohorts=[{id:'all',filters:plan.filters}]
  if(sections.includes('vocational')) {
    const intersection=(supplied,allowed)=>supplied?.length?allowed.filter(v=>supplied.includes(v)):allowed
    const education=intersection(plan.filters.education,VOC_EDU),experience=intersection(plan.filters.experience,VOC_EXP)
    if(education.length&&experience.length)cohorts.push({id:'vocational',filters:{...plan.filters,education,experience}})
  }
  return {schema:'talent-query/1',sourceId:'talent-main',cohorts,metrics,...(plan.analysis?{analysis:plan.analysis}:{}),execution:plan.execution??{freshness:'cache-ok',deadlineMs:360000},output:{topN:100,previewRows:0,exports:[]}}
}
function options(argv){const out={};for(let i=0;i<argv.length;i+=2){if(!['--plan','--result','--query-cli','--out','--profile'].includes(argv[i])||!argv[i+1]||out[argv[i].slice(2)])throw new Error('参数：--plan plan.json 或 --result result.json，可选 --profile 产业名 --query-cli /path/query.mjs --out report_data.json');out[argv[i].slice(2)]=argv[i+1]}return out}
async function inside(file,root=process.cwd()) {const path=await realpath(resolve(root,file)),rel=relative(await realpath(root),path);if(rel==='..'||rel.startsWith('../')||resolve(root,rel)!==path)throw new Error('输入必须位于当前会话工作区');return path}
export async function collect(opts) {
  if(Boolean(opts.plan)===Boolean(opts.result))throw new Error('plan/result 必须二选一')
  const cli=resolve(opts['query-cli']??process.env.TALENT_DATA_QUERY_CLI??fileURLToPath(new URL('../../talent-data-query/scripts/query.mjs',import.meta.url)))
  await access(cli)
  const call=async args=>{try{return JSON.parse((await exec(process.execPath,[cli,...args],{cwd:process.cwd(),maxBuffer:8*1024*1024,timeout:380000})).stdout)}catch(e){if(e.stdout){try{const output=JSON.parse(e.stdout);if(output.artifacts?.result)return output;throw new Error(JSON.stringify(output.errors??output))}catch(parse){throw parse}}throw new Error('共享查询工具执行失败：'+e.message)}}
  const started=performance.now();let plan,preview,source,selectedProfile
  if(opts.plan) {
    plan=JSON.parse(await readFile(await inside(opts.plan),'utf8'))
    if(opts.profile) {
      const registry=JSON.parse(await readFile(new URL('../assets/industry_profiles.json',import.meta.url),'utf8'))
      selectedProfile=registry.profiles[opts.profile]
      if(!selectedProfile)throw new Error('没有该产业的已声明规则，请提供适合该主题的显式analysis，不能回退AI规则')
      const resolved=await call(['resolve','--kind','industry','--name',selectedProfile.name])
      validateProfileScope(plan,selectedProfile,resolved.candidates??[])
      plan=applyProfile(plan,selectedProfile)
    }
    const request=buildRequest(plan),caps=await call(['capabilities'])
    if(request.metrics.some(m=>!caps.metrics[m]))throw new Error('共享工具版本缺少所需指标')
    const rel=join('data',`wechat-request-${randomUUID()}.json`)
    await mkdir('data',{recursive:true});await writeFile(rel,JSON.stringify(request,null,2)+'\n')
    preview=await call(['query','--request',rel])
    if(!preview.artifacts?.result)throw new Error('查询没有返回结果工件')
    source=await inside(preview.artifacts.result)
  } else {
    if(opts.profile)throw new Error('已有结果只能按其原始规则适配，profile仅用于首次plan取数')
    source=await inside(opts.result)
  }
  await call(['inspect','--result',relative(process.cwd(),source)])
  const result=JSON.parse(await readFile(source,'utf8'))
  const sections=plan?reportSections(plan):Object.keys(SECTION_METRICS).filter(s=>(s!=='vocational'||result.cohorts.some(c=>c.id==='vocational'))&&SECTION_METRICS[s].every(n=>result.metrics.some(m=>m.cohortId==='all'&&m.name===n)))
  const enumLabels=(await call(['capabilities'])).enums
  const {data,fieldMetrics}=adaptResult(result,{sections,audience:plan?.audience,industryLabel:plan?.industryLabel,enumLabels})
  const out=resolve(opts.out??'report_data.json'),outRoot=await realpath(dirname(out))
  if(relative(await realpath(process.cwd()),outRoot).split('/').includes('..'))throw new Error('输出必须位于当前会话工作区')
  const bindingFile=join(dirname(out),out===resolve(dirname(out),'report_data.json')?'report_binding.json':`${out.split('/').at(-1)}.binding.json`)
  const manifest=join(dirname(source),'manifest.json')
  const dataText=JSON.stringify(data,null,2)+'\n'
  const binding={schema:'wechat-report-binding/1',adapterVersion:ADAPTER_VERSION,source:{result:relative(dirname(out),source),manifest:relative(dirname(out),manifest),manifestSha256:sha(await readFile(manifest)),contentHash:result.contentHash,requestId:result.requestId,dataReadAt:result.freshness.dataReadAt},reportDataSha256:sha(dataText),fields:fieldMetrics,coverage:data.coverage,options:{sections,audience:plan?.audience,industryLabel:plan?.industryLabel,enumLabels},collectionMs:Math.round(performance.now()-started)}
  if(selectedProfile)binding.collectionProfile={name:selectedProfile.name,version:selectedProfile.version,sha256:sha(JSON.stringify(selectedProfile))}
  // A failure leaves no new report data; a data/binding mismatch is rejected by consumers.
  await writeFile(bindingFile,JSON.stringify(binding,null,2)+'\n');await writeFile(out,dataText)
  return {status:result.status,data:relative(process.cwd(),out),binding:relative(process.cwd(),bindingFile),positions:data.total.positions,coverage:data.coverage,collectionMs:binding.collectionMs,execution:result.execution}
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))try{console.log(JSON.stringify(await collect(options(process.argv.slice(2)))))}catch(e){console.error(JSON.stringify({status:'failed',message:e.message}));process.exitCode=1}
