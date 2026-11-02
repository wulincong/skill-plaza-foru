import { METRICS, ENUMS, VERSION, hash, fail, semanticRequest, now } from './core.mjs'
import { cityCode, provinceEntity, normalizeGeography } from './entities.mjs'

const round=(value,places=6)=>Number(value.toFixed(places))
const count=value=>{
  const n=Number(value)
  if(value===null || !Number.isSafeInteger(n)||n<0)fail('INVALID_DB_VALUE','计数不为可安全表示的非负整数')
  return n
}
const sum=rows=>rows.reduce((total,row)=>total+count(row.count),0)
const label=(dimension,value)=>value===null?'缺失':ENUMS[dimension]?.[value]??(ENUMS[dimension]?`未知枚举（${value}）`:value)

function aggregate(rows,dimensions) {
  const groups=new Map()
  for(const row of rows) {
    const values=Object.fromEntries(dimensions.map(d=>[d,row[d]??null]))
    const key=JSON.stringify(values)
    if(!groups.has(key))groups.set(key,{...values,count:0})
    groups.get(key).count+=count(row.count)
  }
  return [...groups.values()].sort((a,b)=>b.count-a.count||JSON.stringify(a).localeCompare(JSON.stringify(b)))
}
function distributionRows(rows,dimensions,total) {
  return rows.map(row=>({
    ...row,labels:Object.fromEntries(dimensions.map(d=>[d,label(d,row[d])])),count:count(row.count),share:total?round(row.count/total,10):null,
    ...(dimensions.includes('city')?{code:cityCode(row.province,row.city)}:dimensions.includes('province')?{code:provinceEntity(row.province)?.code??null}:{})
  }))
}
export function salaryStatistics(rows) {
  const frequencies=[],reasons={},validStatuses=new Set(['valid','missing','non_numeric','non_positive','reversed','above_cap'])
  for(const row of rows) {
    if(!validStatuses.has(row.status))fail('INVALID_DB_VALUE','未知薪资有效性分类')
    const n=count(row.count)
    if(row.status==='valid') {
      const mid=Number(row.mid)
      if(!Number.isFinite(mid)||mid<=0||mid>100)fail('INVALID_DB_VALUE','有效薪资中点越界')
      frequencies.push({mid,count:n})
    } else reasons[row.status]=(reasons[row.status]??0)+n
  }
  frequencies.sort((a,b)=>a.mid-b.mid)
  const validN=sum(frequencies),excludedN=Object.values(reasons).reduce((a,b)=>a+b,0)
  const at=rank=>{
    let cumulative=0
    for(const row of frequencies){cumulative+=row.count;if(rank<cumulative)return row.mid}
    fail('INVALID_DB_VALUE','薪资频数秩越界')
  }
  const quantile=p=>{
    if(!validN)return null
    const h=(validN-1)*p,low=Math.floor(h),high=Math.ceil(h)
    return round(at(low)+(at(high)-at(low))*(h-low))
  }
  const bins=[{label:'<3K',from:0,to:3},{label:'3–6K',from:3,to:6},{label:'6–10K',from:6,to:10},{label:'10–15K',from:10,to:15},{label:'15–25K',from:15,to:25},{label:'25K+',from:25,to:Infinity}]
  const distribution=bins.map(bin=>({category:bin.label,from:bin.from,to:Number.isFinite(bin.to)?bin.to:null,count:frequencies.filter(row=>row.mid>=bin.from&&row.mid<bin.to).reduce((n,row)=>n+row.count,0)}))
  // Integer micro-K arithmetic for the weighted mean; rounding occurs only at presentation.
  const weighted=frequencies.reduce((total,row)=>total+BigInt(Math.round(row.mid*1e7))*BigInt(row.count),0n)
  return {validN,excludedN,reasons,summary:{mean:validN?round(Number(weighted)/validN/1e7):null,p25:quantile(.25),median:quantile(.5),p75:quantile(.75),p90:quantile(.9)},distribution:distribution.map(row=>({...row,share:validN?round(row.count/validN,10):null}))}
}

export function buildResult(request,plan,execution) {
  const metrics=[],checks=[],errors=[],cohorts=[]
  const logs=new Map(execution.logs.filter(log=>log.completed).map(log=>[log.id,log]))
  const bases=new Map(plan.cohorts.map(c=>[c.id,logs.get(`${c.id}:base`)]))
  for(const job of plan.jobs.filter(j=>j.kind==='cohort-counts')) {
    const log=logs.get(job.id)
    if(!log)continue
    const values=log.rows.length===1?log.rows[0].counts:null
    if(!values||typeof values!=='object'||Object.keys(values).length!==job.cohortIds.length||job.cohortIds.some(id=>!Object.hasOwn(values,id)))fail('INVALID_DB_VALUE','合并计数缺少完整样本组')
    for(const id of job.cohortIds)bases.set(id,{...log,rows:[{count:count(values[id])}]})
  }
  for(const cohort of plan.cohorts) {
    const id=cohort.id,baseLog=bases.get(id),cubeLog=logs.get(`${id}:cube`),salaryLog=logs.get(`${id}:salary`)
    let base=baseLog?.rows[0],total=null,cubeValid=false,salary=null
    if(baseLog && baseLog.rows.length!==1)fail('INVALID_DB_VALUE','基础统计返回行数错误')
    if(base) {
      total=count(base.count)
      const expected=plan.jobs.find(job=>job.id===baseLog.id)?.fields??['count']
      if(expected.some(field=>base[field]===undefined))fail('INVALID_DB_VALUE','基础统计缺少请求字段')
      for(const field of ['missingCompany','missingAddress','missing_city','missing_province','missing_title','missing_source']) {
        if(base[field]!==undefined&&count(base[field])>total) fail('INVALID_DB_VALUE','缺失量超过样本基数')
      }
      if(base.companies!==undefined&&count(base.companies)>total-count(base.missingCompany))fail('INVALID_DB_VALUE','企业数超过有效记录数')
      checks.push({id:`${id}:base`,pass:true,description:'基础计数及按需返回的缺失量非负、范围有效'})
    }
    if(cubeLog&&base) {
      cubeValid=sum(cubeLog.rows)===total
      checks.push({id:`${id}:cube-total`,pass:cubeValid,expected:total,actual:sum(cubeLog.rows)})
    }
    if(salaryLog&&base) {
      salary=salaryStatistics(salaryLog.rows)
      const ok=salary.validN+salary.excludedN===total
      checks.push({id:`${id}:salary-total`,pass:ok,expected:total,actual:salary.validN+salary.excludedN})
      if(!ok)salary=null
    }
    cohorts.push({...cohort,unit:'job_records',positions:total,sourceLatestUpdateAt:base?.latestUpdate??null,addressBasis:'企业关联地址，未核验为真实工作地',missingAddressN:base?.missingAddress!==undefined?count(base.missingAddress):null})
    for(const name of request.metrics) {
      const def=METRICS[name]
      const metric={metricId:`${id}/${name}`,name,metricVersion:1,cohortId:id,cohortFingerprint:cohort.fingerprint,kind:def.kind,unit:def.unit,status:'failed',denominator:total,denominatorDefinition:'当前样本组内在招且未删除的去重岗位记录数',method:'cohort-policy/1; category-policy/1',evidenceIds:baseLog?[baseLog.id]:[]}
      let available=false
      if(base&&name==='positions.count') {Object.assign(metric,{value:total,numerator:total,missingN:0});available=true}
      if(base&&name==='companies.count') {Object.assign(metric,{value:count(base.companies),missingN:count(base.missingCompany),method:'不同非空有效企业 ID 的去重数；不等同岗位数'});available=true}
      if(base&&name==='data_quality.summary') {
        const fields=['missingCompany','missingAddress','missing_city','missing_province','missing_title','missing_source']
        if(fields.every(field=>base[field]!==undefined)&&Object.hasOwn(base,'latestUpdate')) {
          Object.assign(metric,{value:Object.fromEntries(fields.map(field=>[field,count(base[field])])),sourceLatestUpdateAt:base.latestUpdate,method:'显式请求的字段完整性统计；地址无法关联时省市字段计为缺失，缺失项可能重叠'})
          available=true
        }
      }
      if((def.dimensions || ['education','experience','jobType'].includes(def.dimension))&&cubeValid) {
        const dimensions=def.dimensions??[def.dimension]
        const contextDimensions=dimensions.includes('city')?[...new Set([...dimensions,'province'])]:dimensions
        const rows=aggregate(cubeLog.rows.map(row=>normalizeGeography(row,cohort.resolved.region)),contextDimensions)
        const missingN=rows.filter(row=>dimensions.some(d=>row[d]===null)).reduce((n,row)=>n+row.count,0)
        Object.assign(metric,{dimensions,rows:distributionRows(rows,contextDimensions,total),totalCount:total,otherCount:0,missingN,completeDistribution:true,evidenceIds:[baseLog.id,cubeLog.id]})
        available=true
      }
      if(def.dimension&&['source','city','province','title'].includes(def.dimension)) {
        const d=def.dimension
        const log=plan.jobs.some(j=>j.id===`${id}:${d}`)?logs.get(`${id}:${d}`):cubeLog
        if(log&&base&&(![cubeLog].includes(log)||cubeValid)) {
          const dimensions=d==='city'?['city','province']:[d]
          const fullRows=aggregate(log.rows.map(row=>normalizeGeography(row,cohort.resolved.region)),dimensions).filter(row=>row[d]!==null)
          let rows=fullRows
          const missingN=count(base[`missing_${d}`])
          const fullReturned=sum(rows)
          const complete=fullReturned+missingN===total
          const valid=d==='title'?fullReturned+missingN<=total:complete
          checks.push({id:`${id}:${d}-bounds`,pass:valid,expected:total,actual:fullReturned+missingN})
          if(valid) {
            rows=rows.slice(0,request.output.topN)
            Object.assign(metric,{dimensions,rows:distributionRows(rows,dimensions,total),totalCount:total,displayedCount:sum(rows),otherCount:total-missingN-sum(rows),missingN,completeDistribution:complete&&rows.length===fullRows.length,evidenceIds:[baseLog.id,log.id]})
            available=true
          }
        }
      }
      if(name.startsWith('salary.')&&salary) {
        Object.assign(metric,{validN:salary.validN,missingN:salary.reasons.missing??0,excludedN:salary.excludedN,exclusions:salary.reasons,validRate:total?round(salary.validN/total,10):null,method:'salary-policy/1; 严格数值(最多6位小数); 0<min<=max<=100 K/月; 区间中点; 加权线性插值 h=(n-1)*p',evidenceIds:[baseLog.id,salaryLog.id]})
        if(name==='salary.summary')metric.value=salary.summary
        else Object.assign(metric,{rows:salary.distribution,denominator:salary.validN,denominatorDefinition:'当前样本组中满足 salary-policy/1 的有效薪资记录数',totalCount:salary.validN,otherCount:0,completeDistribution:true})
        available=true
      }
      metric.status=available?(total===0?'empty':name.startsWith('salary.')&&!salary.validN?'unavailable':'complete'):'failed'
      if(metric.status==='failed'||metric.status==='unavailable')errors.push({code:metric.status==='unavailable'?'NO_VALID_SALARY':execution.error?.code??'VALIDATION_FAILED',metricIds:[metric.metricId],message:metric.status==='unavailable'?'样本有岗位但没有有效薪资':execution.error?.message??'指标结果缺失或校验未通过',retryable:false})
      metrics.push(metric)
    }
  }
  const failed=metrics.filter(m=>['failed','unavailable'].includes(m.status))
  const allEmpty=cohorts.every(c=>c.positions===0)
  const status=failed.length?(metrics.some(m=>m.status==='complete'||m.status==='empty')?'partial':'failed'):execution.error?'partial':allEmpty?'empty':'complete'
  if(execution.error&&!errors.some(e=>e.code===execution.error.code))errors.push({...execution.error,metricIds:[],message:execution.error.message})
  const comparisons=[]
  if(cohorts.length===2) {
    for(const name of request.metrics) {
      const [a,b]=cohorts.map(c=>metrics.find(m=>m.cohortId===c.id&&m.name===name))
      if(name==='positions.count'||name==='companies.count') {
        if([a,b].every(m=>['complete','empty'].includes(m.status)))comparisons.push({metricIds:[a.metricId,b.metricId],operation:'second-minus-first',value:b.value-a.value,unit:a.unit})
        continue
      }
      if(a.status!=='complete'||b.status!=='complete')continue
      if(name==='salary.summary') comparisons.push({metricIds:[a.metricId,b.metricId],operation:'second-minus-first-median',value:round(b.value.median-a.value.median),unit:a.unit})
      if(['education.distribution','experience.distribution','jobType.distribution'].includes(name)) {
        const d=METRICS[name].dimension
        const keys=new Set([...a.rows,...b.rows].map(r=>r[d]))
        for(const key of keys) comparisons.push({metricIds:[a.metricId,b.metricId],operation:'second-minus-first-share',category:key,label:label(d,key),value:round(((b.rows.find(r=>r[d]===key)?.share??0)-(a.rows.find(r=>r[d]===key)?.share??0))*100),unit:'percentage_points'})
      }
    }
  }
  const result={schema:'talent-result/1',engine:VERSION,status,request,cohorts,metrics,comparisons,quality:{checks,allPass:checks.length>0&&checks.every(c=>c.pass)&&!failed.length&&!execution.error},freshness:{executedAt:execution.startedAt,dataReadAt:execution.dataReadAt,servedAt:now(),mode:'live',cacheAgeMs:0,sourceReadTime:execution.sourceReadTime,sourceLatestUpdateAt:cohorts.map(c=>c.sourceLatestUpdateAt).filter(Boolean).sort().at(-1)??null,sourceTimestampMeaning:'当前样本内平台记录更新时间最大值；源时区未换算；非职位发布时间'},consistency:{level:'repeatable-read-read-only',singleConnection:true,sourceReadTime:execution.sourceReadTime,completeTransaction:!execution.error},execution:{queryCount:execution.logs.length,sqlBatchMs:execution.elapsedMs,returnedBytes:execution.returnedBytes},errors}
  result.quality.dataQualityEvaluated=request.metrics.includes('data_quality.summary')&&metrics.filter(m=>m.name==='data_quality.summary').every(m=>['complete','empty'].includes(m.status))
  result.execution.logicalCohortCount=plan.cohorts.length
  if(!request.metrics.includes('data_quality.summary'))result.freshness.sourceTimestampMeaning='本次未请求平台最大更新时间统计；dataReadAt 为统计读取时间，不是职位发布时间'
  result.contentHash=resultContentHash(result)
  return result
}
export function resultContentHash(result) {
  return hash({schema:result.schema,engine:result.engine,status:result.status,request:semanticRequest(result.request,result.engine),cohorts:result.cohorts,metrics:result.metrics,comparisons:result.comparisons,quality:result.quality})
}
export function summaryMarkdown(result) {
  const lines=['# 人才数据库查询结果','',`状态：${result.status}；统计读取时间：${result.freshness.dataReadAt??'未完成'}；数据模式：${result.freshness.mode}。`,'','统计对象为平台岗位记录；地域按企业关联地址；平台更新时间不等于职位发布时间。','']
  for(const cohort of result.cohorts) {
    lines.push(`## ${cohort.id} · ${cohort.resolved.region.name}`,'',`岗位名称条件：${JSON.stringify(cohort.filters.title)}；产业：${cohort.resolved.industries.entities.map(e=>e.name).join('、')||'未限制'}；岗位类型：${cohort.resolved.roles.entities.map(e=>e.name).join('、')||'未限制'}。`,'')
    for(const m of result.metrics.filter(m=>m.cohortId===cohort.id))lines.push(`- ${m.metricId}：${m.status}；${m.value!==undefined?JSON.stringify(m.value):`${m.rows?.length??0} 个分组，分母 ${m.denominator??'未知'}`}；单位 ${m.unit}。`)
    lines.push('')
  }
  if(result.errors.length)lines.push('未完成指标：',...result.errors.map(e=>`- ${e.metricIds.join('、')}：${e.message}`),'')
  return lines.join('\n')+'\n'
}
