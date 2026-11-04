import {dataRefreshRequested} from '../../../.agents/skills/wechat-report/scripts/refresh_policy.mjs'
export {dataRefreshRequested}
import { readFileSync,existsSync,statSync } from 'node:fs'
import { join } from 'node:path'
import { createHash } from 'node:crypto'

export function reportTask(workspace) {
  try {
    const value=JSON.parse(readFileSync(join(workspace,'report-turn.json'),'utf8'))
    return value.schema==='plaza-report-turn/1' && value.enabled===true ? value : undefined
  } catch {return undefined}
}

const provinces=['北京市','天津市','河北省','山西省','内蒙古自治区','辽宁省','吉林省','黑龙江省','上海市','江苏省','浙江省','安徽省','福建省','江西省','山东省','河南省','湖北省','湖南省','广东省','广西壮族自治区','海南省','重庆市','四川省','贵州省','云南省','西藏自治区','陕西省','甘肃省','青海省','宁夏回族自治区','新疆维吾尔自治区']
const industries=['人工智能','智能制造','机器人','低空经济','新能源汽车','新一代信息技术','纺织服装','生物医药','新能源']
const shortRegion=value=>value.replace(/(?:壮族|回族|维吾尔)?自治区$|[省市]$/,'')

export function reportScopeMatches(meta,text) {
 const regions=provinces.filter(name=>text.includes(name)||text.includes(shortRegion(name)))
 if(regions.length>1||regions.length===1&&shortRegion(regions[0])!==shortRegion(meta.region??''))return false
 const sectors=industries.filter(name=>text.includes(name)).filter(name=>!industries.some(other=>other!==name&&other.includes(name)&&text.includes(other)))
 if(sectors.length>1||sectors.length===1&&sectors[0]!==meta.industry)return false
 return true
}


export function reportDataReady(workspace) {
 try {
  const task=reportTask(workspace)
  if(!task)return false
  const file=join(workspace,'wechat-report/report_data.json')
  const data=JSON.parse(readFileSync(file,'utf8'))
  const text=task.requestText??''
  if(!data.meta?.region||!data.meta?.industry||!Array.isArray(data.city_profiles)||!reportScopeMatches(data.meta,text))return false
  // New collection during this turn is authoritative. Saved data is reused only
  // for an explicit same-scope revision/resume or a plain default-scope request.
  if(statSync(file).mtimeMs>=task.startedAt)return true
  if(dataRefreshRequested(text))return false
  if(/(?:只看|筛选|限定|改为|换成|改成|变更).*(?:学历|经验|本科|专科|大专|硕士|博士|岗位|地区|行业)|(?:近|过去|最近)[一二三四五六七八九十两\d]+(?:年|月|天)/.test(text))return false
  if(task.revision||/^(?:请)?继续(?:生成|完成)?[。！!\s]*$/.test(text.trim())||/本会话(?:已保存的|真实)数据|数据已准备好/.test(text))return true
  if(!text.includes(shortRegion(data.meta.region))||!text.includes(data.meta.industry))return false
  let rest=text.replaceAll(data.meta.region,'').replaceAll(shortRegion(data.meta.region),'').replaceAll(data.meta.industry,'')
  const fillers=['微信公众号','人才需求观察报告','人才需求分析报告','人才需求报告','人才需求','观察报告','分析报告','产业链','帮我','帮忙','我想要','想看','请您','麻烦','提供','生成','制作','针对','关于','一份','一篇','公众号','行业','产业','报告','全省','地区','给我','请','的','来','做','需要','我','想','要']
  for(const word of fillers.sort((a,b)=>b.length-a.length))rest=rest.replaceAll(word,'')
  return !rest.replace(/[\s，。！？、：:,.!?]+/g,'')
 } catch {return false}
}

export function reportBuildReady(workspace,task) {
  try {
    const root=join(workspace,'wechat-report/output/report')
    const receipt=JSON.parse(readFileSync(join(root,'build_receipt.json'),'utf8'))
    const quality=JSON.parse(readFileSync(join(root,'quality.json'),'utf8'))
    const manifest=readFileSync(join(root,'manifest.json'))
    return Date.parse(receipt.startedAt)>=task.startedAt && statSync(join(workspace,'delivery.json')).mtimeMs>=task.startedAt &&
      quality.all_pass===true && quality.manifest_sha256===createHash('sha256').update(manifest).digest('hex') &&
      receipt.manifestSha256===quality.manifest_sha256
  } catch {return false}
}
