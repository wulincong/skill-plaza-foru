import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { hash, fail, sqlString, LIMITS, textValue } from './core.mjs'

const PROVINCE_ROWS = [
  ['11','北京市','北京'],['12','天津市','天津'],['13','河北省','河北'],['14','山西省','山西'],['15','内蒙古自治区','内蒙古'],
  ['21','辽宁省','辽宁'],['22','吉林省','吉林'],['23','黑龙江省','黑龙江'],['31','上海市','上海'],['32','江苏省','江苏'],['33','浙江省','浙江'],['34','安徽省','安徽'],['35','福建省','福建'],['36','江西省','江西'],['37','山东省','山东'],
  ['41','河南省','河南'],['42','湖北省','湖北'],['43','湖南省','湖南'],['44','广东省','广东'],['45','广西壮族自治区','广西'],['46','海南省','海南'],['50','重庆市','重庆'],
  ['51','四川省','四川'],['52','贵州省','贵州'],['53','云南省','云南'],['54','西藏自治区','西藏'],['61','陕西省','陕西'],['62','甘肃省','甘肃'],['63','青海省','青海'],['64','宁夏回族自治区','宁夏'],['65','新疆维吾尔自治区','新疆'],['71','台湾省','台湾'],['81','香港特别行政区','香港'],['82','澳门特别行政区','澳门'],
]
export function provinceEntity(name) {
  const match=PROVINCE_ROWS.find(row=>row.slice(1).includes(name))
  return match ? {name:match[1],code:`${match[0]}0000`,aliases:match.slice(1)} : null
}
const cityCodes=new Map()
const standardCities=new Map()
for(const province of ['guangdong','zhejiang']) {
  const file=fileURLToPath(new URL(`../../.agents/skills/chart-visualization/resources/administrative-codes/${province}-city-codes.json`,import.meta.url))
  try {
    const data=JSON.parse(readFileSync(file,'utf8'))
    for(const [name,code] of Object.entries(data.cityNameToCode)) cityCodes.set(`${data.scope.province}/${name}`,code)
    for(const city of data.cities)for(const alias of [city.name,...city.aliases])standardCities.set(`${data.scope.province}/${alias}`,city.name)
  } catch { /* geography queries also work without optional map resources */ }
}
export const cityCode=(province,city)=>cityCodes.get(`${provinceEntity(province)?.name??province}/${city}`)??null
export function normalizeGeography(row,region) {
  const output={...row}
  if(Object.hasOwn(row,'province'))output.province=provinceEntity(row.province)?.name??row.province
  if(Object.hasOwn(row,'city')&&row.city!==null) {
    output.city=region.level==='city'&&region.aliases.includes(row.city)?region.name:standardCities.get(`${output.province}/${row.city}`)??row.city
  }
  return output
}

export class EntityResolver {
  constructor({adapter,state,sourceKey,deadlineAt,signal}) {Object.assign(this,{adapter,state,sourceKey,deadlineAt,signal});this.evidence=[]}
  async light(jobs) {
    // One shared metadata slot; heavy statistical work uses a separate single slot.
    return this.state.lock(`light:${this.sourceKey}`,this.deadlineAt,async({onSpawn})=>{
      const r=await this.adapter.run(jobs,{deadlineAt:this.deadlineAt,timeoutMs:5000,consistent:false,onSpawn})
      this.evidence.push(...r.logs)
      if(r.error) fail(r.error.code,r.error.message)
      return r.logs
    },this.signal)
  }
  async dictionary(kind) {
    const table={industry:'c_industry_chain_info',role:'c_position_type'}[kind]
    if(!table) fail('UNSUPPORTED','实体类型支持 region/industry/role；专业关联尚未开放')
    const key=hash({source:this.sourceKey,kind,version:1})
    let saved=await this.state.read('dictionaries',key,86400000)
    if(!saved) saved=await this.state.lock(`dictionary:${key}`,this.deadlineAt,async()=>{
      const existing=await this.state.read('dictionaries',key,86400000)
      if(existing)return existing
      const [log]=await this.light([{id:`dictionary-${kind}`,sql:`SELECT JSON_OBJECT('row',JSON_OBJECT('id',CAST(id AS CHAR),'name',name,'pid',CAST(pid AS CHAR),'level',level)) FROM ${table} ORDER BY id LIMIT 40001`}])
      if(log.rows.length>40000) fail('RESULT_LIMIT','字典超过行数上限')
      if(log.rows.some(row=>!/^\d+$/.test(row.id)||row.pid!==null&&!/^-?\d+$/.test(row.pid)||typeof row.name!=='string'))fail('INVALID_DB_VALUE','字典 ID/父级/名称类型不正确')
      return this.state.write('dictionaries',key,{kind,rows:log.rows,version:hash(log.rows),readAt:log.finishedAt,evidence:log})
    },this.signal)
    this.evidence.push({kind:'dictionary-cache',dictionary:kind,version:saved.payload.version,dataReadAt:saved.payload.readAt,originalQuery:saved.payload.evidence})
    return saved.payload
  }
  async region(region) {
    if(region.level==='national')return {level:'national',name:'中国',country:'中国',version:'cn-provinces/1'}
    if(region.level==='province') {
      const province=provinceEntity(region.name)
      if(!province) fail('NEEDS_CLARIFICATION','未识别省级地域，不扩大为全国',{entity:region.name,candidates:[]})
      return {level:'province',...province,version:'cn-provinces/1'}
    }
    const province=region.province ? provinceEntity(region.province):null
    if(region.province && !province) fail('NEEDS_CLARIFICATION','未识别 region.province',{entity:region.province,candidates:[]})
    if(/[区县]$/.test(region.name)) fail('UNSUPPORTED','首期不解析区县，请指定市级地域')
    const aliases=[region.name,...(!region.name.endsWith('市') ? [`${region.name}市`]:[region.name.slice(0,-1)])]
    const key=hash({source:this.sourceKey,region,version:1})
    const cached=await this.state.read('dictionaries',key,86400000)
    let rows=cached?.payload.rows
    if(!rows) {
      const [log]=await this.light([{id:'resolve-region',sql:`SELECT DISTINCT JSON_OBJECT('row',JSON_OBJECT('province',province,'city',city)) FROM c_company_address WHERE city IN (${aliases.map(sqlString).join(',')}) ${province?`AND province IN (${province.aliases.map(sqlString).join(',')})`:''} LIMIT 21`}])
      rows=log.rows
      await this.state.write('dictionaries',key,{rows})
    }
    const candidates=new Map()
    for(const row of rows) {
      const p=provinceEntity(row.province)
      if(!p)continue
      const name=/(市|州|地区|盟)$/.test(row.city)?row.city:`${row.city}市`
      candidates.set(`${p.name}/${name}`,{level:'city',name,province:p.name,provinceAliases:p.aliases,aliases:name.endsWith('市')?[name,name.slice(0,-1)]:[name],code:cityCode(p.name,name),version:hash(rows)})
    }
    if(candidates.size!==1 || rows.length===21) fail('NEEDS_CLARIFICATION',candidates.size?'地域有多个候选，请补充省份':'在地址数据中未识别该城市，不扩大查询范围',{entity:region,candidates:[...candidates.values()]})
    return [...candidates.values()][0]
  }
  async select(kind, selectors) {
    if(!selectors.length)return {ids:[],entities:[],version:null}
    const dict=await this.dictionary(kind)
    const selected=new Set(), entities=[]
    for(const selector of selectors) {
      const rows=dict.rows.filter(row=>selector.id!==undefined ? row.id===selector.id : row.name===selector.name)
      if(rows.length!==1) fail('NEEDS_CLARIFICATION',`未唯一识别${kind==='industry'?'产业':'岗位类型'}`,{entity:selector,candidates:rows.slice(0,20)})
      const root=rows[0], ids=new Set([root.id])
      if(selector.includeDescendants) {
        let changed=true
        while(changed) {changed=false;for(const row of dict.rows) if(ids.has(row.pid)&&!ids.has(row.id)){ids.add(row.id);changed=true}}
      }
      ids.forEach(id=>selected.add(id))
      entities.push({...root,includeDescendants:selector.includeDescendants,descendantCount:ids.size-1})
    }
    if(selected.size>LIMITS.dictionaryIds)fail('QUERY_TOO_BROAD',`${kind} 子树超过 ${LIMITS.dictionaryIds} 项，请缩小分类范围`)
    return {ids:[...selected].sort((a,b)=>Number(a)-Number(b)),entities,version:dict.version}
  }
  async cohorts(cohorts) {
    const resolved=[]
    for(const cohort of cohorts) {
      const region=await this.region(cohort.filters.region)
      const industries=await this.select('industry',cohort.filters.industries)
      const roles=await this.select('role',cohort.filters.roles)
      resolved.push({...cohort,resolved:{region,industries,roles},fingerprint:hash({filters:cohort.filters,region,industries,roles,policy:'cohort-policy/1'})})
    }
    return resolved
  }
  async search(kind,name) {
    textValue(name,80,'name')
    if(kind==='region') {
      const province=provinceEntity(name)
      return {candidates:province?[{level:'province',...province}]:[await this.region({level:'city',name})]}
    }
    const dict=await this.dictionary(kind)
    const exact=dict.rows.filter(row=>row.name===name)
    const candidates=exact.length?exact:dict.rows.filter(row=>row.name.toLowerCase().includes(name.toLowerCase())).slice(0,20)
    return {kind,candidates,match:exact.length?'exact':'contains-candidates',dictionaryVersion:dict.version}
  }
}
