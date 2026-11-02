#!/usr/bin/env node
// Offline test protocol peer. All counts are synthetic; this never connects to a database.
import { appendFileSync } from 'node:fs'
let input=''
for await(const chunk of process.stdin)input+=chunk
const jobs=[...input.matchAll(/'_talent','begin','id',CONVERT\(X'([0-9a-f]+)'/g)].map(m=>Buffer.from(m[1],'hex').toString('utf8'))
const statistical=jobs.some(id=>id.endsWith(':base'))
const event=kind=>{if(statistical&&process.env.TALENT_FIXTURE_LOG)appendFileSync(process.env.TALENT_FIXTURE_LOG,JSON.stringify({kind,pid:process.pid,at:Date.now()})+'\n')}
const emit=value=>process.stdout.write(JSON.stringify(value)+'\n')
event('start')
emit({_talent:'snapshot',sourceReadTime:'2026-11-02 00:00:00'})
for(const id of jobs) {
  emit({_talent:'begin',id})
  if(statistical)await new Promise(resolve=>setTimeout(resolve,100))
  if(process.env.TALENT_FIXTURE_FAIL===id) {
    process.stderr.write('ERROR 3024 (HY000): fixture timeout\n')
    process.exit(1)
  }
  const rows=id==='capability'?['c_company_position','c_company_address','c_position_chain'].map(name=>({name,engine:'InnoDB'}))
    :id.endsWith(':base')?[{count:4,companies:2,latestUpdate:'2026-10-31 12:00:00',missingCompany:0,missingAddress:0,missing_city:0,missing_province:0,missing_title:0,missing_source:0}]
    :id.endsWith(':cube')?[{education:'BENKE',experience:'LESS_THAN_3',jobType:'SHEZHAO',count:4}]
    :[{status:'valid',mid:6.5,count:4}]
  for(const row of rows)emit({row})
  emit({_talent:'end',id})
}
event('end')
emit({_talent:'finished'})
