import { DIMENSIONS, METRICS, sqlString, likeTerm, canonical, hash } from './core.mjs'
import {trackExpression,skillFields} from './analysis.mjs'

function localPredicates(cohort) {
  const {filters:f,resolved:r}=cohort
  const parts=[],region=r.region
  if(region.level==='province')parts.push(`a.province IN (${region.aliases.map(sqlString).join(',')})`)
  if(region.level==='city')parts.push(`a.province IN (${region.provinceAliases.map(sqlString).join(',')})`,`a.city IN (${region.aliases.map(sqlString).join(',')})`)
  for(const field of ['education','experience','jobType'])if(f[field].length)parts.push(`${DIMENSIONS[field]} IN (${f[field].map(sqlString).join(',')})`)
  return parts
}
function useIndustryCandidates(cohort) {
  // Keep time-selective requests eligible for the existing update_time access path.
  return cohort.resolved.industries.ids.length>0 && !cohort.filters.updatedAt
}
export function cohortWhere(cohort,{needsAddress=true,industryFirst=false}={}) {
  const {filters:f,resolved:r}=cohort
  const parts=["p.publish_state='PUBLISHING'",'p.deleted=0']
  parts.push(...localPredicates(cohort))
  if(f.title.any.length)parts.push(`(${f.title.any.map(term=>`p.name LIKE ${likeTerm(term)} ESCAPE '!'`).join(' OR ')})`)
  if(f.title.all.length)parts.push(...f.title.all.map(term=>`p.name LIKE ${likeTerm(term)} ESCAPE '!'`))
  if(f.title.exclude.length)parts.push(...f.title.exclude.map(term=>`COALESCE(p.name,'') NOT LIKE ${likeTerm(term)} ESCAPE '!'`))
  if(f.updatedAt?.from)parts.push(`p.update_time >= ${sqlString(f.updatedAt.from)}`)
  if(f.updatedAt?.to)parts.push(`p.update_time < ${sqlString(f.updatedAt.to)}`)
  if(r.industries.ids.length&&!industryFirst)parts.push(`EXISTS (SELECT 1 FROM c_position_chain pc WHERE pc.position_id=p.id AND pc.deleted=0 AND pc.industry_chain_id IN (${r.industries.ids.join(',')}))`)
  if(r.roles.ids.length)parts.push(`(${r.roles.ids.map(id=>`CONCAT(',',TRIM(BOTH ',' FROM COALESCE(p.position_type,'')),',') LIKE '%,${id},%'`).join(' OR ')})`)
  const from=industryFirst&&r.industries.ids.length
    ? `FROM (SELECT DISTINCT pc.position_id FROM c_position_chain pc WHERE pc.deleted=0 AND pc.industry_chain_id IN (${r.industries.ids.join(',')})) industry_candidates JOIN c_company_position p ON p.id=industry_candidates.position_id`
    : 'FROM c_company_position p'
  const address=needsAddress||r.region.level!=='national'?' LEFT JOIN c_company_address a ON a.id=p.company_address_id':''
  return `${from}${address} WHERE ${parts.join(' AND ')}`
}
const jsonRow=fields=>`JSON_OBJECT('row',JSON_OBJECT(${Object.entries(fields).map(([name,sql])=>`${sqlString(name)},${sql}`).join(',')}))`
const clean=sql=>`NULLIF(TRIM(${sql}),'')`
export function salaryParts() {
  const lo="CAST(TRIM(p.min_salary) AS DECIMAL(18,6))",hi="CAST(TRIM(p.max_salary) AS DECIMAL(18,6))"
  const numeric="TRIM(p.min_salary) REGEXP '^-?[0-9]+([.][0-9]{1,6})?$' AND TRIM(p.max_salary) REGEXP '^-?[0-9]+([.][0-9]{1,6})?$'"
  const status=`CASE WHEN ${clean('p.min_salary')} IS NULL OR ${clean('p.max_salary')} IS NULL THEN 'missing' WHEN NOT (${numeric}) THEN 'non_numeric' WHEN ${lo}<=0 OR ${hi}<=0 THEN 'non_positive' WHEN ${lo}>${hi} THEN 'reversed' WHEN ${hi}>100 THEN 'above_cap' ELSE 'valid' END`
  return {status,mid:`(${lo}+${hi})/2`}
}
function baseFields(request) {
  const fields={count:'COUNT(*)'}
  const quality=request.metrics.includes('data_quality.summary')
  if(quality) {
    fields.latestUpdate='MAX(p.update_time)'
    fields.missingAddress='COALESCE(SUM(a.id IS NULL),0)'
  }
  if(quality||request.metrics.includes('companies.count'))fields.missingCompany="COALESCE(SUM(p.company_archive_id IS NULL OR CAST(p.company_archive_id AS CHAR) IN ('','0')),0)"
  for(const field of ['city','province','title','source']) {
    if(quality||request.metrics.some(m=>METRICS[m].dimension===field))fields[`missing_${field}`]=`COALESCE(SUM(${clean(DIMENSIONS[field])} IS NULL),0)`
  }
  if(request.metrics.includes('companies.count'))fields.companies="COUNT(DISTINCT CASE WHEN p.company_archive_id IS NOT NULL AND CAST(p.company_archive_id AS CHAR) NOT IN ('','0') THEN p.company_archive_id END)"
  return fields
}
function needsAddress(request,cohort) {
  return cohort.resolved.region.level!=='national'||request.metrics.includes('data_quality.summary')||request.metrics.some(m=>[...(METRICS[m].dimensions??[]),METRICS[m].dimension].some(d=>d==='city'||d==='province'))
}
function countGroups(cohorts) {
  const groups=new Map()
  for(const cohort of cohorts) {
    const f=cohort.filters,r=cohort.resolved
    const key=canonical({industries:r.industries.ids,roles:r.roles.ids,title:f.title,updatedAt:f.updatedAt??null,state:f.state})
    if(!groups.has(key))groups.set(key,[])
    groups.get(key).push(cohort)
  }
  return [...groups.values()]
}
function fusedCountJob(group) {
  const first=group[0]
  const common={...first,filters:{...first.filters,region:{level:'national'},education:[],experience:[],jobType:[]},resolved:{...first.resolved,region:{level:'national'}}}
  const branches=group.map(c=>localPredicates(c).join(' AND '))
  const branchFields=Object.fromEntries(group.map((c,i)=>[c.id,`COALESCE(SUM(CASE WHEN ${branches[i]||'1=1'} THEN 1 ELSE 0 END),0)`]))
  const counts=`JSON_OBJECT(${Object.entries(branchFields).map(([id,sql])=>`${sqlString(id)},${sql}`).join(',')})`
  const from=cohortWhere(common,{needsAddress:group.some(c=>c.resolved.region.level!=='national'),industryFirst:useIndustryCandidates(common)})
  // Preserve a restrictive WHERE for groups containing only cities or other narrow branches.
  const union=branches.every(Boolean)?` AND (${branches.map(p=>`(${p})`).join(' OR ')})`:''
  return {id:`counts:${hash(group.map(c=>c.id)).slice(0,12)}`,kind:'cohort-counts',cohortIds:group.map(c=>c.id),sql:`SELECT ${jsonRow({counts})} ${from}${union}`}
}
export function buildPlan(request,cohorts) {
  const jobs=[]
  const fused=new Set()
  if(request.metrics.length===1&&request.metrics[0]==='positions.count') {
    for(const group of countGroups(cohorts))if(group.length>1) {
      jobs.push(fusedCountJob(group))
      group.forEach(c=>fused.add(c.id))
    }
  }
  for(const cohort of cohorts) {
    if(fused.has(cohort.id))continue
    const base=cohortWhere(cohort,{needsAddress:needsAddress(request,cohort),industryFirst:useIndustryCandidates(cohort)}),prefix=cohort.id
    jobs.push({id:`${prefix}:base`,cohortId:prefix,kind:'base',fields:Object.keys(baseFields(request)),sql:`SELECT ${jsonRow(baseFields(request))} ${base}`})
    const dimensions=[...new Set(request.metrics.filter(m=>!METRICS[m].analysis).flatMap(m=>METRICS[m].dimensions??(METRICS[m].dimension&&['education','experience','jobType'].includes(METRICS[m].dimension)?[METRICS[m].dimension]:[])))].sort()
    if(dimensions.includes('city')&&!dimensions.includes('province'))dimensions.push('province')
    if(dimensions.length) {
      const columns=Object.fromEntries(dimensions.map(d=>[d,clean(DIMENSIONS[d])]))
      jobs.push({id:`${prefix}:cube`,cohortId:prefix,kind:'cube',dimensions,sql:`SELECT ${jsonRow({...columns,count:'COUNT(*)'})} ${base} GROUP BY ${dimensions.map(d=>clean(DIMENSIONS[d])).join(',')} LIMIT 40001`})
    }
    for(const dimension of ['source','city','province','title']) {
      if(!request.metrics.some(m=>METRICS[m].dimension===dimension))continue
      if(dimensions.includes(dimension))continue
      const expression=clean(DIMENSIONS[dimension])
      // Geography is normalized before TOP N so province/city aliases cannot split the ranking.
      const limit=dimension==='title'?request.output.topN:40001
      const fields={[dimension]:expression,...(dimension==='city'?{province:clean('a.province')}:{})}
      const grouping=Object.values(fields).join(',')
      jobs.push({id:`${prefix}:${dimension}`,cohortId:prefix,kind:'dimension',dimension,sql:`SELECT ${jsonRow({...fields,count:'COUNT(*)'})} ${base} AND ${expression} IS NOT NULL GROUP BY ${grouping} ORDER BY COUNT(*) DESC,${grouping} ASC LIMIT ${limit}`})
    }
    if(request.metrics.some(m=>['track.distribution','city_track.cross'].includes(m))) {
      const fields={track:trackExpression(request),...(request.metrics.includes('city_track.cross')?{province:clean('a.province'),city:clean('a.city')}:{})}
      jobs.push({id:`${prefix}:tracks`,cohortId:prefix,kind:'tracks',sql:`SELECT ${jsonRow({...fields,count:'COUNT(*)'})} ${base} GROUP BY ${Object.values(fields).join(',')} LIMIT 40001`})
    }
    if(request.metrics.some(m=>['skills.distribution','track_skills.cross'].includes(m))) {
      const track=request.metrics.includes('track_skills.cross')?trackExpression(request):sqlString('__other__')
      const hits=`JSON_OBJECT(${Object.entries(skillFields(request)).map(([w,s])=>`${sqlString(w)},${s}`).join(',')})`
      jobs.push({id:`${prefix}:skills`,cohortId:prefix,kind:'skills',sql:`SELECT ${jsonRow({track,count:'COUNT(*)',describedN:"COALESCE(SUM(NULLIF(TRIM(p.description),'') IS NOT NULL),0)",hits})} ${base} GROUP BY ${track}`})
    }
    if(request.metrics.some(m=>m.startsWith('salary.')||m==='track_salary.summary')) {
      const {status,mid}=salaryParts()
      const track=request.metrics.includes('track_salary.summary')?{track:trackExpression(request)}:{}
      jobs.push({id:`${prefix}:salary`,cohortId:prefix,kind:'salary',sql:`SELECT ${jsonRow({...track,status,mid:`CASE WHEN (${status})='valid' THEN ${mid} ELSE NULL END`,count:'COUNT(*)'})} ${base} GROUP BY ${Object.values(track).map(v=>v+',').join('')}${status},CASE WHEN (${status})='valid' THEN ${mid} ELSE NULL END LIMIT 40001`})
    }
  }
  return {jobs,cohorts,description:'同连接一致性只读统计；按需字段与地址关联；无更新时间窗口时产业候选优先；同产业纯计数组条件聚合',cost:jobs.some(j=>/LIKE|EXISTS|industry_candidates/.test(j.sql))?'heavy-filter':'aggregate',queryCount:jobs.length,logicalCohortCount:cohorts.length}
}
