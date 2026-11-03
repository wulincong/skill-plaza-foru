// Shared analytical aggregates. No report formatting or industry-specific defaults.
import {sqlString,likeTerm,fail,hash} from './core.mjs'
import {normalizeGeography} from './entities.mjs'

export function trackExpression(request) {
  const groups=request.analysis?.tracks??[]
  if(!groups.length)return sqlString('__other__')
  return `CASE ${groups.map(g=>{
    const matches=[...g.titleAny.map(t=>`p.name LIKE ${likeTerm(t)} ESCAPE '!'`),...g.roleIds.map(id=>`CONCAT(',',TRIM(BOTH ',' FROM COALESCE(p.position_type,'')),',') LIKE '%,${id},%'`)]
    return `WHEN (${matches.join(' OR ')}) THEN ${sqlString(g.key)}`
  }).join(' ')} ELSE ${sqlString('__other__')} END`
}
export function skillFields(request) {
  return Object.fromEntries(request.analysis.skills.map(word=>[word,`COALESCE(SUM(LOCATE(LOWER(${sqlString(word)}),LOWER(COALESCE(p.description,'')))>0),0)`]))
}
const count=v=>{if(v===null||!Number.isSafeInteger(Number(v))||Number(v)<0)fail('INVALID_DB_VALUE','分析计数无效');return Number(v)}
const sum=rows=>rows.reduce((n,r)=>n+count(r.count),0)
const ratio=(a,b)=>b?Number((a/b).toFixed(10)):null

export function analysisMetrics(request,cohort,logs,total,salaryStatistics,checks) {
  const values=new Map(),id=cohort.id
  const names=new Map([...(request.analysis?.tracks??[]).map(g=>[g.key,g.label]),['__other__','未分类']])
  const method=`track-policy/1; 有序规则首个命中，名称包含或完整岗位类型ID; analysis=${hash(request.analysis??{})}`
  const checkTrack=r=>{if(!names.has(r.track))fail('INVALID_DB_VALUE','返回了未声明的方向');return r.track}
  const tracks=logs.get(`${id}:tracks`)
  let trackCounts
  if(tracks&&total!==null) {
    const merged=new Map()
    for(const raw of tracks.rows) {
      const r={...normalizeGeography(raw,cohort.resolved.region),track:checkTrack(raw),count:count(raw.count)}
      const key=JSON.stringify([r.province??null,r.city??null,r.track])
      if(!merged.has(key))merged.set(key,{...r,count:0})
      merged.get(key).count+=r.count
    }
    const rows=[...merged.values()]
    const ok=sum(rows)===total
    checks.push({id:`${id}:track-total`,pass:ok,expected:total,actual:sum(rows)})
    if(ok) {
      const grouped=new Map()
      for(const r of rows)grouped.set(r.track,(grouped.get(r.track)??0)+r.count)
      trackCounts=grouped
      values.set('track.distribution',{rows:[...grouped].map(([track,n])=>({track,label:names.get(track),count:n,share:ratio(n,total)})).sort((a,b)=>b.count-a.count),totalCount:total,completeDistribution:true,otherCount:0,missingN:0,method,evidenceIds:[tracks.id]})
      if(request.metrics.includes('city_track.cross'))values.set('city_track.cross',{rows:rows.map(r=>({...r,label:names.get(r.track),share:ratio(r.count,total)})),totalCount:total,completeDistribution:true,otherCount:0,missingN:sum(rows.filter(r=>!r.city||!r.province)),method,evidenceIds:[tracks.id]})
    }
  }
  const salary=logs.get(`${id}:salary`)
  if(salary&&total!==null&&request.metrics.includes('city_salary.summary')) {
    const grouped=new Map()
    for(const raw of salary.rows) {
      const geography=normalizeGeography(raw,cohort.resolved.region)
      const key=JSON.stringify([geography.province??null,geography.city??null])
      if(!grouped.has(key))grouped.set(key,{province:geography.province??null,city:geography.city??null,rows:[]})
      grouped.get(key).rows.push(raw)
    }
    const cube=logs.get(`${id}:cube`)
    const cityCounts=new Map()
    if(cube?.rows.length&&cube.rows.every(row=>Object.hasOwn(row,'city'))) {
      for(const raw of cube.rows) {
        const geography=normalizeGeography(raw,cohort.resolved.region)
        const key=JSON.stringify([geography.province??null,geography.city??null])
        cityCounts.set(key,(cityCounts.get(key)??0)+count(raw.count))
      }
    }
    const groupConsistent=!cityCounts.size||[...new Set([...cityCounts.keys(),...grouped.keys()])].every(key=>(cityCounts.get(key)??0)===sum(grouped.get(key)?.rows??[]))
    const ok=sum(salary.rows)===total&&groupConsistent
    checks.push({id:`${id}:city-salary-total`,pass:ok,expected:total,actual:sum(salary.rows)})
    if(ok) {
      const rows=[...grouped.values()].map(group=>{
        const s=salaryStatistics(group.rows)
        return {province:group.province,city:group.city,count:sum(group.rows),validN:s.validN,excludedN:s.excludedN,summary:s.summary}
      }).sort((a,b)=>b.count-a.count||JSON.stringify([a.province,a.city]).localeCompare(JSON.stringify([b.province,b.city])))
      values.set('city_salary.summary',{rows,totalCount:total,completeDistribution:true,
        missingN:rows.filter(row=>!row.province||!row.city).reduce((n,row)=>n+row.count,0),
        method:'city-salary-policy/1; 企业关联地址，非已核验工作地；salary-policy/1；同事务完整频数加权分位，不是实际到手收入',evidenceIds:[salary.id]})
    }
  }
  if(salary&&total!==null&&request.metrics.includes('track_salary.summary')) {
    const grouped=new Map()
    for(const r of salary.rows){checkTrack(r);if(!grouped.has(r.track))grouped.set(r.track,[]);grouped.get(r.track).push(r)}
    const groupConsistent=!trackCounts||[...new Set([...trackCounts.keys(),...grouped.keys()])].every(key=>(trackCounts.get(key)??0)===sum(grouped.get(key)??[]))
    const ok=sum(salary.rows)===total&&groupConsistent
    checks.push({id:`${id}:track-salary-total`,pass:ok,expected:total,actual:sum(salary.rows)})
    if(ok)values.set('track_salary.summary',{rows:[...grouped].map(([track,rows])=>{const s=salaryStatistics(rows);return {track,label:names.get(track),count:sum(rows),validN:s.validN,excludedN:s.excludedN,summary:s.summary}}),completeDistribution:true,method:`${method}; salary-policy/1`,evidenceIds:[salary.id]})
  }
  const skills=logs.get(`${id}:skills`)
  if(skills&&total!==null) {
    const groups=skills.rows.map(r=>{
      checkTrack(r)
      const n=count(r.count),describedN=count(r.describedN)
      if(describedN>n||!r.hits||typeof r.hits!=='object'||Object.keys(r.hits).length!==request.analysis.skills.length)fail('INVALID_DB_VALUE','技能统计字段不完整')
      const hits=Object.fromEntries(request.analysis.skills.map(w=>{const v=count(r.hits[w]);if(r.hits[w]===undefined||v>describedN)fail('INVALID_DB_VALUE','技能提及数超过有效描述数');return [w,v]}))
      return {track:r.track,count:n,describedN,hits}
    })
    if(new Set(groups.map(g=>g.track)).size!==groups.length)fail('INVALID_DB_VALUE','技能方向分组重复')
    const groupConsistent=!trackCounts||!request.metrics.includes('track_skills.cross')||[...new Set([...trackCounts.keys(),...groups.map(g=>g.track)])].every(key=>(trackCounts.get(key)??0)===(groups.find(g=>g.track===key)?.count??0))
    const ok=sum(groups)===total&&groupConsistent,describedN=groups.reduce((n,g)=>n+g.describedN,0)
    checks.push({id:`${id}:skills-total`,pass:ok,expected:total,actual:sum(groups)})
    if(ok) {
      const skillMethod=`skills-policy/1; 描述LOWER子串匹配；每岗位每词至多一次；多词可重叠；analysis=${hash(request.analysis)}`
      const rows=request.analysis.skills.map(skill=>{const n=groups.reduce((v,g)=>v+g.hits[skill],0);return {skill,count:n,share:ratio(n,total),describedShare:ratio(n,describedN)}}).sort((a,b)=>b.count-a.count)
      values.set('skills.distribution',{rows,describedN,missingN:total-describedN,completeDistribution:true,method:skillMethod,evidenceIds:[skills.id]})
      values.set('track_skills.cross',{rows:groups.flatMap(g=>request.analysis.skills.map(skill=>({track:g.track,label:names.get(g.track),skill,count:g.hits[skill],positions:g.count,describedN:g.describedN,share:ratio(g.hits[skill],g.count),describedShare:ratio(g.hits[skill],g.describedN)}))),describedN,missingN:total-describedN,completeDistribution:true,method:`${method}; ${skillMethod}`,evidenceIds:[skills.id]})
    }
  }
  return values
}
