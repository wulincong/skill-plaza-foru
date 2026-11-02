import { mkdir, writeFile, readFile, rename, rm, realpath, lstat } from 'node:fs/promises'
import { resolve, join, relative, sep } from 'node:path'
import { randomUUID } from 'node:crypto'
import { hash, fail } from './core.mjs'
import { resultContentHash, summaryMarkdown } from './metrics.mjs'

export async function withinWorkspace(file,workspace) {
  const root=await realpath(workspace),actual=await realpath(resolve(workspace,file))
  if(actual!==root&&!actual.startsWith(root+sep))fail('INVALID_PATH','文件必须位于当前会话工作区内')
  return actual
}
async function dataDirectory(workspace) {
  const root=await realpath(workspace),data=join(root,'data')
  await mkdir(data,{recursive:true,mode:0o2770})
  if((await lstat(data)).isSymbolicLink()||await realpath(data)!==data)fail('INVALID_PATH','data 目录不得为符号链接')
  return data
}
function csvCell(value) {
  let s=value===null||value===undefined?'':typeof value==='object'?JSON.stringify(value):String(value)
  if(typeof value==='string'&&/^[=+\-@\t\r]/.test(s))s="'"+s
  return '"'+s.replaceAll('"','""')+'"'
}
export function exportContent(result,format) {
  if(format==='markdown')return summaryMarkdown(result)
  const publicResult={schema:result.schema,requestId:result.requestId,status:result.status,cohorts:result.cohorts,metrics:result.metrics,comparisons:result.comparisons,quality:result.quality,freshness:result.freshness,contentHash:result.contentHash}
  if(format==='json')return JSON.stringify(publicResult,null,2)+'\n'
  const lines=[['metricId','cohortId','status','unit','denominator','dimensions','value','count','share']]
  for(const m of result.metrics) {
    if(m.rows?.length)for(const row of m.rows)lines.push([m.metricId,m.cohortId,m.status,m.unit,m.denominator,Object.fromEntries(Object.entries(row).filter(([key])=>!['count','share'].includes(key))),null,row.count,row.share])
    else lines.push([m.metricId,m.cohortId,m.status,m.unit,m.denominator,null,m.value??null,null,null])
  }
  return '\uFEFF'+lines.map(row=>row.map(csvCell).join(',')).join('\r\n')+'\r\n'
}
export async function persistResult(result,evidence,workspace,formats=[]) {
  const data=await dataDirectory(workspace),id=`tq-${randomUUID()}`
  const temp=join(data,`.${id}.tmp`),destination=join(data,id)
  const ext={json:'json',csv:'csv',markdown:'md'}
  await mkdir(temp,{mode:0o2770})
  const names=['result.json','summary.md','evidence.json',...formats.map(f=>`export.${ext[f]}`)]
  result.requestId=id
  result.artifacts={result:`data/${id}/result.json`,summary:`data/${id}/summary.md`,evidence:`data/${id}/evidence.json`,manifest:`data/${id}/manifest.json`,exports:formats.map(f=>`data/${id}/export.${ext[f]}`)}
  const contents={'result.json':JSON.stringify(result,null,2)+'\n','summary.md':summaryMarkdown(result),'evidence.json':JSON.stringify(evidence,null,2)+'\n'}
  for(const f of formats)contents[`export.${ext[f]}`]=exportContent(result,f)
  try {
    for(const name of names)await writeFile(join(temp,name),contents[name],{mode:0o640,flag:'wx'})
    const manifest={schema:'talent-artifacts/1',requestId:id,contentHash:result.contentHash,files:names.map(name=>({name,bytes:Buffer.byteLength(contents[name]),sha256:hash(contents[name]),visibility:name==='evidence.json'?'internal':'data'}))}
    await writeFile(join(temp,'manifest.json'),JSON.stringify(manifest,null,2)+'\n',{mode:0o640,flag:'wx'})
    await rename(temp,destination)
  } catch(error) {await rm(temp,{recursive:true,force:true});throw error}
  return result
}
export async function readResult(file,workspace) {
  const path=await withinWorkspace(file,workspace),directory=resolve(path,'..')
  if(!path.endsWith(`${sep}result.json`))fail('INVALID_PATH','inspect/export 必须指定 result.json')
  const manifest=JSON.parse(await readFile(join(directory,'manifest.json'),'utf8'))
  if(manifest.schema!=='talent-artifacts/1'||!Array.isArray(manifest.files)||manifest.files.length>10)fail('INVALID_ARTIFACT','工件清单不正确')
  for(const required of ['result.json','summary.md','evidence.json'])if(!manifest.files.some(f=>f.name===required))fail('INVALID_ARTIFACT','工件清单缺少必需文件')
  for(const entry of manifest.files) {
    if(!/^[a-z]+\.(json|md|csv)$/.test(entry.name))fail('INVALID_ARTIFACT','清单含不支持的文件名')
    const actual=await withinWorkspace(join(directory,entry.name),workspace)
    if(resolve(actual,'..')!==directory)fail('INVALID_ARTIFACT','工件不能引用其他目录')
    const bytes=await readFile(actual)
    if(bytes.length!==entry.bytes||hash(bytes.toString('utf8'))!==entry.sha256)fail('INVALID_ARTIFACT','工件缺失或内容指纹不一致')
  }
  const result=JSON.parse(await readFile(path,'utf8'))
  if(result.schema!=='talent-result/1'||resultContentHash(result)!==result.contentHash||manifest.contentHash!==result.contentHash)fail('INVALID_ARTIFACT','统计结果内容指纹不一致')
  return result
}
export async function persistExport(result,format,workspace) {
  const data=await dataDirectory(workspace),id=`export-${randomUUID()}`,destination=join(data,id)
  await mkdir(destination,{mode:0o2770})
  const name=`export.${{json:'json',csv:'csv',markdown:'md'}[format]}`,content=exportContent(result,format)
  await writeFile(join(destination,name),content,{mode:0o640,flag:'wx'})
  const manifest={schema:'talent-export/1',sourceRequestId:result.requestId,sourceContentHash:result.contentHash,file:{name,sha256:hash(content),bytes:Buffer.byteLength(content)}}
  await writeFile(join(destination,'manifest.json'),JSON.stringify(manifest,null,2)+'\n',{mode:0o640,flag:'wx'})
  return {file:relative(workspace,join(destination,name)),manifest:relative(workspace,join(destination,'manifest.json')),sourceContentHash:result.contentHash}
}
export function preview(result,maxRows=10) {
  return {schema:'talent-preview/1',requestId:result.requestId,status:result.status,contentHash:result.contentHash,cacheKey:result.cacheKey,snapshotId:result.snapshotId,cohorts:result.cohorts.map(c=>({id:c.id,filters:c.filters,resolved:c.resolved,positions:c.positions,sourceLatestUpdateAt:c.sourceLatestUpdateAt})),freshness:result.freshness,metrics:result.metrics.map(m=>{const {rows,...rest}=m;return {...rest,...(rows?{rows:rows.slice(0,maxRows),totalGroups:rows.length,previewTruncated:rows.length>maxRows}:{})}}),comparisons:result.comparisons.slice(0,20),errors:result.errors,execution:result.execution,artifacts:result.artifacts}
}
