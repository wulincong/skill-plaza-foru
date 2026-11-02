import { DIMENSIONS, METRICS, sqlString, likeTerm } from './core.mjs'

export function cohortWhere(cohort) {
  const {filters:f,resolved:r}=cohort
  const parts=["p.publish_state='PUBLISHING'",'p.deleted=0']
  const region=r.region
  if(region.level==='province')parts.push(`a.province IN (${region.aliases.map(sqlString).join(',')})`)
  if(region.level==='city')parts.push(`a.province IN (${region.provinceAliases.map(sqlString).join(',')})`,`a.city IN (${region.aliases.map(sqlString).join(',')})`)
  if(f.title.any.length)parts.push(`(${f.title.any.map(term=>`p.name LIKE ${likeTerm(term)} ESCAPE '!'`).join(' OR ')})`)
  if(f.title.all.length)parts.push(...f.title.all.map(term=>`p.name LIKE ${likeTerm(term)} ESCAPE '!'`))
  if(f.title.exclude.length)parts.push(...f.title.exclude.map(term=>`COALESCE(p.name,'') NOT LIKE ${likeTerm(term)} ESCAPE '!'`))
  for(const field of ['education','experience','jobType'])if(f[field].length)parts.push(`${DIMENSIONS[field]} IN (${f[field].map(sqlString).join(',')})`)
  if(f.updatedAt?.from)parts.push(`p.update_time >= ${sqlString(f.updatedAt.from)}`)
  if(f.updatedAt?.to)parts.push(`p.update_time < ${sqlString(f.updatedAt.to)}`)
  if(r.industries.ids.length)parts.push(`EXISTS (SELECT 1 FROM c_position_chain pc WHERE pc.position_id=p.id AND pc.deleted=0 AND pc.industry_chain_id IN (${r.industries.ids.join(',')}))`)
  if(r.roles.ids.length)parts.push(`(${r.roles.ids.map(id=>`CONCAT(',',TRIM(BOTH ',' FROM COALESCE(p.position_type,'')),',') LIKE '%,${id},%'`).join(' OR ')})`)
  return `FROM c_company_position p LEFT JOIN c_company_address a ON a.id=p.company_address_id WHERE ${parts.join(' AND ')}`
}
const jsonRow=fields=>`JSON_OBJECT('row',JSON_OBJECT(${Object.entries(fields).map(([name,sql])=>`${sqlString(name)},${sql}`).join(',')}))`
const clean=sql=>`NULLIF(TRIM(${sql}),'')`
export function salaryParts() {
  const lo="CAST(TRIM(p.min_salary) AS DECIMAL(18,6))",hi="CAST(TRIM(p.max_salary) AS DECIMAL(18,6))"
  const numeric="TRIM(p.min_salary) REGEXP '^-?[0-9]+([.][0-9]{1,6})?$' AND TRIM(p.max_salary) REGEXP '^-?[0-9]+([.][0-9]{1,6})?$'"
  const status=`CASE WHEN ${clean('p.min_salary')} IS NULL OR ${clean('p.max_salary')} IS NULL THEN 'missing' WHEN NOT (${numeric}) THEN 'non_numeric' WHEN ${lo}<=0 OR ${hi}<=0 THEN 'non_positive' WHEN ${lo}>${hi} THEN 'reversed' WHEN ${hi}>100 THEN 'above_cap' ELSE 'valid' END`
  return {status,mid:`(${lo}+${hi})/2`}
}
export function buildPlan(request,cohorts) {
  const jobs=[]
  for(const cohort of cohorts) {
    const base=cohortWhere(cohort), prefix=cohort.id
    const fields={count:'COUNT(*)',latestUpdate:'MAX(p.update_time)',missingCompany:"COALESCE(SUM(p.company_archive_id IS NULL OR CAST(p.company_archive_id AS CHAR) IN ('','0')),0)",missingAddress:'COALESCE(SUM(a.id IS NULL),0)'}
    for(const field of ['city','province','title','source'])fields[`missing_${field}`]=`COALESCE(SUM(${clean(DIMENSIONS[field])} IS NULL),0)`
    if(request.metrics.includes('companies.count'))fields.companies="COUNT(DISTINCT CASE WHEN p.company_archive_id IS NOT NULL AND CAST(p.company_archive_id AS CHAR) NOT IN ('','0') THEN p.company_archive_id END)"
    jobs.push({id:`${prefix}:base`,cohortId:prefix,kind:'base',sql:`SELECT ${jsonRow(fields)} ${base}`})
    const dimensions=[...new Set(request.metrics.flatMap(m=>METRICS[m].dimensions??(METRICS[m].dimension&&['education','experience','jobType'].includes(METRICS[m].dimension)?[METRICS[m].dimension]:[])))].sort()
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
    if(request.metrics.some(m=>m.startsWith('salary.'))) {
      const {status,mid}=salaryParts()
      jobs.push({id:`${prefix}:salary`,cohortId:prefix,kind:'salary',sql:`SELECT ${jsonRow({status,mid:`CASE WHEN (${status})='valid' THEN ${mid} ELSE NULL END`,count:'COUNT(*)'})} ${base} GROUP BY ${status},CASE WHEN (${status})='valid' THEN ${mid} ELSE NULL END LIMIT 40001`})
    }
  }
  return {jobs,cohorts,description:'同连接 REPEATABLE READ 一致性只读事务；低基数联合分组复用边际分布；未读取岗位描述',cost:jobs.some(j=>/LIKE|EXISTS/.test(j.sql))?'heavy-filter':'aggregate',queryCount:jobs.length}
}
