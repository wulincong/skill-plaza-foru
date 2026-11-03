// Presentation adapter: consumes talent-result/1 only. No DB configuration or SQL.
import {fileURLToPath} from 'node:url'
export const ADAPTER_VERSION='wechat-adapter/3'
const pct=(a,b)=>b?Number((a/b*100).toFixed(2)):null
export function adaptResult(result,{sections=[],audience='院校与产业研究读者',industryLabel,enumLabels}={}) {
  if(result.schema!=='talent-result/1'||!result.consistency?.completeTransaction)throw new Error('需要完整事务的 talent-result/1 工件')
  if(result.errors?.some(e=>!['NO_VALID_SALARY','NO_VALID_DESCRIPTION'].includes(e.code)))throw new Error('统计存在执行或校验失败，不能生成报告')
  if(!result.quality?.checks?.length||result.quality.checks.some(c=>!c.pass))throw new Error('统计对账未通过')
  const all=result.cohorts.find(c=>c.id==='all')
  if(!all)throw new Error('报告主样本必须命名为 all')
  const metrics=new Map(result.metrics.map(m=>[m.metricId,m]))
  const fieldMetrics={}
  const get=(name,id='all',required=false)=>{
    const m=metrics.get(`${id}/${name}`)
    if(required&&!m)throw new Error(`缺少必需指标 ${id}/${name}`)
    if(m?.status==='failed')throw new Error(`指标失败 ${m.metricId}`)
    return m
  }
  const bind=(field,names,id='all')=>{fieldMetrics[field]=names.map(n=>get(n,id,true).metricId)}
  const total=get('positions.count','all',true).value
  const companies=get('companies.count','all',true).value
  if(!Number.isSafeInteger(total)||!Number.isSafeInteger(companies))throw new Error('岗位/企业基数无效')
  const d={schema:'wechat-report-data/2',meta:{region:all.resolved.region.name??'全国',industry:industryLabel||all.resolved.industries.entities.map(e=>e.name).join('、')||all.filters.title.any.join('、')||'全部岗位',audience,generated_at:result.freshness.dataReadAt,days:null,filters:all.filters,data_mode:result.freshness.mode,source_latest_update_at:all.sourceLatestUpdateAt},total:{positions:total,companies,cities:null},coverage:[],provenance:{source_platform:'优才知路平台的数据库',source_request_id:result.requestId,source_content_hash:result.contentHash,engine:result.engine,generated_at:result.freshness.dataReadAt,checks:result.quality.checks,all_checks_pass:result.quality.checks.every(c=>c.pass)}}
  bind('/total/positions',['positions.count']);bind('/total/companies',['companies.count'])
  d.meta.scope_industry=all.resolved.industries.entities.map(e=>e.name).join('、')||[...all.filters.title.any,...all.filters.title.all].join('、')||'全部岗位'
  if(enumLabels)d.meta.enum_labels=enumLabels
  const quality=get('data_quality.summary')
  if(quality){d.quality_summary=quality.value;bind('/quality_summary',['data_quality.summary'])}
  const distributions={edu:['education.distribution','education'],exp:['experience.distribution','experience'],jobtype:['jobType.distribution','jobType']}
  for(const [field,[name,dimension]] of Object.entries(distributions)) {
    const m=get(name)
    if(m){d[field]=m.rows.map(r=>({name:r.labels[dimension],raw:r[dimension],count:r.count,pct:pct(r.count,total)}));bind('/'+field,[name])}
  }
  const cross=get('education_experience.cross')
  if(cross){d.edu_exp=cross.rows.map(r=>[r.labels.education,r.labels.experience,r.count]);bind('/edu_exp',['education_experience.cross'])}
  const cities=get('city_education.cross')
  if(cities) {
    if(!cities.completeDistribution)throw new Error('城市计数需要完整交叉分布')
    const groups=new Map()
    for(const r of cities.rows)if(r.city&&r.province){const key=JSON.stringify([r.province,r.city]);if(!groups.has(key))groups.set(key,{province:r.province,city:r.city,count:0});groups.get(key).count+=r.count}
    d.city=[...groups.values()].sort((a,b)=>b.count-a.count||a.city.localeCompare(b.city)).map(r=>[all.resolved.region.level==='national'?`${r.province}·${r.city}`:r.city,r.count])
    d.total.cities=groups.size;bind('/city',['city_education.cross']);bind('/total/cities',['city_education.cross'])
  }
  function salaryFor(id){const m=get('salary.summary',id);if(!m)return undefined;return {valid:m.validN,valid_pct:pct(m.validN,m.denominator),...m.value,status:m.status,method:m.method}}
  d.salary=salaryFor('all')
  if(d.salary)bind('/salary',['salary.summary'])
  const hist=get('salary.distribution')
  if(hist){d.salary_hist=hist.rows.map(r=>({name:r.category,count:r.count,pct:pct(r.count,hist.validN)}));bind('/salary_hist',['salary.distribution'])}
  const tracks=get('track.distribution')
  if(tracks){d.subtrack=tracks.rows.map(r=>({name:r.label,key:r.track,count:r.count,pct:pct(r.count,total)}));bind('/subtrack',['track.distribution'])}
  const ts=get('track_salary.summary')
  if(ts){d.salary_by_track=ts.rows.map(r=>({name:r.label,key:r.track,count:r.count,valid:r.validN,...r.summary}));bind('/salary_by_track',['track_salary.summary'])}
  const cs=get('city_salary.summary')
  if(cs&&cities) {
    const groups=new Map()
    for(const row of cities.rows) {
      const key=JSON.stringify([row.province,row.city])
      if(!groups.has(key))groups.set(key,{count:0,bachelorCount:0,higherCount:0})
      const group=groups.get(key);group.count+=row.count
      if(row.education==='BENKE')group.bachelorCount+=row.count
      if(['BENKE','SHUOSHI','BOSHI'].includes(row.education))group.higherCount+=row.count
    }
    d.city_profiles=cs.rows.filter(row=>row.province&&row.city).map(row=>{
      const education=groups.get(JSON.stringify([row.province,row.city]))
      if(!education||education.count!==row.count)throw new Error('城市薪酬与学历样本基数不一致')
      return {name:all.resolved.region.level==='national'?`${row.province}·${row.city}`:row.city,
        province:row.province,city:row.city,count:row.count,valid:row.validN,...row.summary,
        bachelorCount:education.bachelorCount,bachelorShare:pct(education.bachelorCount,row.count),
        higherCount:education.higherCount,higherShare:pct(education.higherCount,row.count)}
    })
    bind('/city_profiles',['city_salary.summary','city_education.cross'])
  }
  const sk=get('skills.distribution')
  if(sk){d.keywords=sk.rows.map(r=>({name:r.skill,count:r.count,pct:pct(r.count,total),described_pct:r.describedShare===null?null:r.describedShare*100}));d.skill_described_n=sk.describedN;bind('/keywords',['skills.distribution']);bind('/skill_described_n',['skills.distribution'])}
  const tsk=get('track_skills.cross')
  if(tsk){d.job_skill_rows=tsk.rows;bind('/job_skill_rows',['track_skills.cross'])}
  const ct=get('city_track.cross')
  if(ct){d.city_track_rows=ct.rows;bind('/city_track_rows',['city_track.cross'])}
  const voc=result.cohorts.find(c=>c.id==='vocational')
  if(voc) {
    const n=get('positions.count',voc.id,true).value
    d.voc_pool={count:n,pct:pct(n,total),salary:salaryFor(voc.id)}
    fieldMetrics['/voc_pool']=[get('positions.count',voc.id,true).metricId,get('positions.count','all',true).metricId]
    for(const [field,name,make] of [
      ['track','track.distribution',m=>m.rows.map(r=>({name:r.label,key:r.track,count:r.count,pct:pct(r.count,n)}))],
      ['keywords','skills.distribution',m=>m.rows.map(r=>({name:r.skill,count:r.count,pct:pct(r.count,n)}))],
      ['city','city.distribution',m=>m.rows.map(r=>[r.city,r.count])],
      ['salary_by_track','track_salary.summary',m=>m.rows.map(r=>({name:r.label,count:r.count,valid:r.validN,...r.summary}))]
    ]){const m=get(name,voc.id);if(m){d.voc_pool[field]=make(m);bind('/voc_pool/'+field,[name],voc.id)}}
    if(d.voc_pool.salary)bind('/voc_pool/salary',['salary.summary'],voc.id)
  } else if(sections.includes('vocational')&&cross) {
    const edu=new Set(['DAZHUAN','GAOZHI','ZHONGZHUAN/ZHONGJI','GAOZHONG','CHUZHONGJIYIXIA','BUXIAN']),exp=new Set(['ON_CAMPUS','GRADUATING','LESS_THAN_1','BUXIAN'])
    const n=cross.rows.filter(r=>edu.has(r.education)&&exp.has(r.experience)).reduce((n,r)=>n+r.count,0)
    if(n!==0)throw new Error('职教子样本缺失，不能从边际比例推算')
    d.voc_pool={count:0,pct:total?0:null};bind('/voc_pool',['education_experience.cross'])
  }
  const deps={overview:['positions.count','companies.count','data_quality.summary'],geography:['city_education.cross'],requirements:['education.distribution','experience.distribution','jobType.distribution','education_experience.cross'],salary:['salary.summary','salary.distribution'],vocational:[],tracks:['track.distribution'],city_tracks:['city_track.cross'],lq:['city_track.cross'],track_salary:['track_salary.summary'],skills:['skills.distribution'],track_skills:['track_skills.cross']}
  for(const section of sections){const ms=(deps[section]??[]).map(n=>get(n));let status=ms.some(m=>!m)?'unsupported':ms.some(m=>m.status==='unavailable')?'unavailable':total===0?'empty':'complete';if(section==='vocational'&&!d.voc_pool)status='unsupported';if(['skills','track_skills'].includes(section)&&sk?.describedN===0&&total>0)status='unavailable';d.coverage.push({section,status})}
  return {data:d,fieldMetrics}
}

// Public file-only adapter entry used by report validators; never connects to DB.
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1]) {
  const {readFile}=await import('node:fs/promises')
  try {console.log(JSON.stringify(adaptResult(JSON.parse(await readFile(process.argv[2],'utf8')),JSON.parse(process.argv[3]??'{}'))))}
  catch(e){console.error(e.message);process.exitCode=1}
}
