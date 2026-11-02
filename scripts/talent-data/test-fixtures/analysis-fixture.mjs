import {spawnSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'
import {validateRequest,hash} from '../core.mjs'
import {buildPlan} from '../compile.mjs'
import {buildResult} from '../metrics.mjs'
export const foundation=['positions.count','companies.count','data_quality.summary','city.distribution','city_education.cross','education.distribution','experience.distribution','jobType.distribution','education_experience.cross','salary.summary','salary.distribution']
export const extended=['track.distribution','city_track.cross','track_salary.summary','skills.distribution','track_skills.cross']
export const analysis={tracks:[{key:'algo',label:'算法研发',titleAny:['算法']},{key:'control',label:'控制调试',titleAny:['调试'],roleIds:['42']}],skills:['Python','ROS','ROS2','C++']}
export function request(extra={}) {
  return validateRequest({schema:'talent-query/1',cohorts:[{id:'all',filters:{region:{level:'national'}}}],metrics:[...foundation,...extended],analysis,...extra})
}
export function resolved(r) {
  return r.cohorts.map(c=>({...c,fingerprint:hash(c.filters),resolved:{region:{level:'national',name:'中国'},industries:{ids:[],entities:[],version:null},roles:{ids:[],entities:[],version:null}}}))
}
export function execute(plan,{empty=false,noSalary=false,noDescription=false}={}) {
  const jobs=plan.jobs.map(j=>({...j,sql:j.sql.replace(/CONVERT\(X'([0-9a-f]*)' USING utf8mb4\)/g,(_,h)=>"'"+Buffer.from(h,'hex').toString().replaceAll("'","''")+"'").replaceAll("TRIM(BOTH ',' FROM COALESCE(p.position_type,''))","TRIM(COALESCE(p.position_type,''),',')")}))
  const p=spawnSync('python3',[fileURLToPath(new URL('analysis-fixture.py',import.meta.url))],{input:JSON.stringify({jobs,empty,noSalary,noDescription}),encoding:'utf8',maxBuffer:16*1024*1024})
  if(p.status!==0)throw new Error(p.stderr)
  return {logs:JSON.parse(p.stdout),startedAt:'2026-11-02T00:00:00Z',dataReadAt:'2026-11-02T00:00:01Z',sourceReadTime:'2026-11-02 00:00:00',elapsedMs:10,returnedBytes:1000}
}
export function result(extra={},options={}) {
  const r=request(extra),p=buildPlan(r,resolved(r)),execution=execute(p,options)
  return {request:r,plan:p,execution,result:buildResult(r,p,execution)}
}
