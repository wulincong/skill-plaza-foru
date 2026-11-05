import { spawn } from 'node:child_process'
import { mysqlBinCandidates, isAuthPluginError } from '../mysql-client.mjs'
import { QueryError, LIMITS, sqlString, now } from './core.mjs'

function databaseError(stderr, timedOut, clipped) {
  const number = /ERROR\s+(\d+)/.exec(stderr)?.[1]
  const code = clipped ? 'RESULT_LIMIT' : timedOut || number==='3024' ? 'QUERY_TIMEOUT' : 'DATABASE_ERROR'
  return { code, message: clipped ? '数据库返回数据超过上限，未作为完整统计使用' : code==='QUERY_TIMEOUT' ? '数据库查询超出预算' : `数据库查询失败${number ? `（MySQL ${number}）` : ''}`, retryable:false }
}
export function framedSql(jobs, timeoutMs, consistent) {
  const lines = ['SET NAMES utf8mb4 COLLATE utf8mb4_general_ci;']
  if(consistent) lines.push('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;', 'START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;')
  lines.push(`SELECT JSON_OBJECT('_talent','snapshot','sourceReadTime',DATE_FORMAT(NOW(6),'%Y-%m-%d %H:%i:%s.%f'));`)
  for(const job of jobs) lines.push(`SET SESSION max_execution_time=${timeoutMs};`, 'SET @talent_started_at=NOW(6);', `SELECT JSON_OBJECT('_talent','begin','id',${sqlString(job.id)},'sourceStartedAt',DATE_FORMAT(@talent_started_at,'%Y-%m-%d %H:%i:%s.%f'));`, `${job.sql};`, `SELECT JSON_OBJECT('_talent','end','id',${sqlString(job.id)},'serverElapsedMs',TIMESTAMPDIFF(MICROSECOND,@talent_started_at,NOW(6))/1000);`)
  if(consistent) lines.push('COMMIT;')
  lines.push("SELECT JSON_OBJECT('_talent','finished');")
  return lines.join('\n')
}

export class MysqlAdapter {
  constructor(cfg,{signal}={}) { this.cfg=cfg; this.bin=null; this.signal=signal }
  async run(jobs, {deadlineAt, timeoutMs=120000, consistent=true,onSpawn}={}) {
    const candidates=this.bin ? [this.bin] : mysqlBinCandidates()
    let answer
    for(const bin of candidates) {
      answer=await this.spawn(bin,jobs,{deadlineAt,timeoutMs,consistent,onSpawn})
      // Only retry an incompatible/missing client, before any statement was observed.
      if(!answer.started && (answer.missingClient || isAuthPluginError(answer.clientError)) && bin!==candidates.at(-1)) continue
      if(!answer.error) this.bin=bin
      break
    }
    delete answer.clientError
    delete answer.missingClient
    return answer
  }
  spawn(bin,jobs,{deadlineAt,timeoutMs,consistent,onSpawn}) {
    return new Promise(resolve => {
      if(this.signal?.aborted)return resolve({logs:[],error:{code:'QUERY_ABORTED',message:'查询已取消',retryable:false},elapsedMs:0,started:false})
      const remaining=deadlineAt-Date.now()
      if(remaining<=0) return resolve({logs:[],error:{code:'DEADLINE_EXCEEDED',message:'查询任务预算已用尽',retryable:false},elapsedMs:0,started:false})
      const startedAt=Date.now(), cfg=this.cfg
      const child=spawn(bin,['--no-defaults','--connect-timeout=5','-h',cfg.MYSQL_HOST,'-P',String(cfg.MYSQL_PORT||3306),'-u',cfg.MYSQL_USER,'--default-character-set=utf8mb4','-D',cfg.MYSQL_DATABASE,'--batch','--raw','--skip-column-names'],{env:{...process.env,MYSQL_PWD:cfg.MYSQL_PASSWORD},stdio:['pipe','pipe','pipe']})
      const result={logs:[],started:false,dataReadAt:null,sourceReadTime:null,elapsedMs:0}
      let pending='',stderr='',bytes=0,active=null,finished=false,timedOut=false,clipped=false,parseError=false,settled=false
      const completed=new Set()
      const byId=new Map(jobs.map(job=>[job.id,job]))
      const abort=()=>{child.kill('SIGTERM'); killTimer=setTimeout(()=>child.kill('SIGKILL'),1000);killTimer.unref()}
      let killTimer,cancelled=false
      const cancel=()=>{cancelled=true;abort()}
      this.signal?.addEventListener('abort',cancel,{once:true})
      const timer=setTimeout(()=>{timedOut=true;abort()},remaining)
      function consume(line) {
        if(!line || parseError) return
        try {
          const frame=JSON.parse(line)
          if(frame._talent==='snapshot') {result.started=true;result.dataReadAt=now();result.sourceReadTime=frame.sourceReadTime;return}
          if(frame._talent==='begin') {
            if(active || !byId.has(frame.id) || completed.has(frame.id)) throw new Error('Invalid frame')
            active={id:frame.id,sql:byId.get(frame.id).sql,rows:[],startedAt:now(),sourceStartedAt:frame.sourceStartedAt??null,serverElapsedMs:null,_start:Date.now()};return
          }
          if(frame._talent==='end') {
            if(!active || active.id!==frame.id) throw new Error('Invalid frame')
            result.logs.push({...active,elapsedMs:Date.now()-active._start,serverElapsedMs:typeof frame.serverElapsedMs==='number'&&frame.serverElapsedMs>=0?frame.serverElapsedMs:null,completed:true,finishedAt:now()})
            delete result.logs.at(-1)._start
            completed.add(frame.id);active=null;return
          }
          if(frame._talent==='finished') {finished=true;return}
          if(!active || typeof frame!=='object' || frame===null || !Object.hasOwn(frame,'row')) throw new Error('Invalid row')
          active.rows.push(frame.row)
          if(active.rows.length>LIMITS.resultRows) {clipped=true;abort()}
        } catch {parseError=true;abort()}
      }
      child.stdout.on('data',chunk=>{
        bytes+=Buffer.byteLength(chunk,'utf8')
        if(bytes>LIMITS.bytes) {clipped=true;abort();return}
        pending+=chunk.toString('utf8')
        const lines=pending.split('\n');pending=lines.pop()
        for(const line of lines) consume(line)
      })
      // Avoid breaking a UTF-8 code point at chunk boundaries.
      child.stdout.setEncoding('utf8')
      child.stderr.setEncoding('utf8')
      child.stderr.on('data',chunk=>{if(stderr.length<65536) stderr+=chunk})
      child.stdin.on('error',()=>{})
      const settle=extra=>{
        if(settled)return
        settled=true;clearTimeout(timer);clearTimeout(killTimer)
        this.signal?.removeEventListener('abort',cancel)
        if(pending.trim())consume(pending.trim())
        if(active) {result.logs.push({...active,rows:[],elapsedMs:Date.now()-active._start,completed:false,finishedAt:now()});delete result.logs.at(-1)._start}
        result.elapsedMs=Date.now()-startedAt;result.returnedBytes=bytes
        Object.assign(result,extra)
        if(cancelled) result.error={code:'QUERY_ABORTED',message:'查询已取消',retryable:false}
        else if(parseError) result.error={code:'INVALID_DB_OUTPUT',message:'数据库结果帧不完整或无法解析',retryable:false}
        else if(!finished || completed.size!==jobs.length || result.error) result.error=result.error??databaseError(stderr,timedOut,clipped)
        result.clientError=stderr
        resolve(result)
      }
      child.on('error',error=>settle({error:{code:'CLIENT_UNAVAILABLE',message:'MySQL 客户端无法启动',retryable:false},missingClient:error.code==='ENOENT'}))
      child.on('close',code=>settle(code===0?{}:{error:databaseError(stderr,timedOut,clipped)}))
      if(child.pid) {
        try{onSpawn?.(child)}catch{parseError=true;abort();return}
      }
      child.stdin.end(framedSql(jobs,Math.max(1,Math.min(timeoutMs,remaining)),consistent))
    })
  }
}

export async function assertReadCapability(adapter,deadlineAt,onSpawn) {
  const sql="SELECT JSON_OBJECT('row',JSON_OBJECT('name',TABLE_NAME,'engine',ENGINE)) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('c_company_position','c_company_address','c_position_chain')"
  const result=await adapter.run([{id:'capability',sql}],{deadlineAt,timeoutMs:5000,consistent:false,onSpawn})
  if(result.error) throw new QueryError(result.error.code,result.error.message)
  const rows=result.logs[0]?.rows??[]
  if(rows.length!==3 || rows.some(row=>row.engine!=='InnoDB')) throw new QueryError('UNSUPPORTED_SOURCE','一致性读取需要已核验的三张 InnoDB 数据表')
  return rows
}
