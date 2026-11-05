import { mkdir, writeFile, readFile, rename, rm, stat, chmod, link } from 'node:fs/promises'
import { join } from 'node:path'
import { hostname } from 'node:os'
import { randomUUID } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { hash, fail, canonical } from './core.mjs'

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
function processIdentity(pid) {
  try {
    const value=readFileSync(`/proc/${pid}/stat`,'utf8')
    return value.slice(value.lastIndexOf(')')+2).split(' ')[19]
  } catch {return null}
}
function alive(pid) {
  try {
    process.kill(pid,0)
    try {
      const value=readFileSync(`/proc/${pid}/stat`,'utf8')
      if(value.slice(value.lastIndexOf(')')+2).startsWith('Z '))return false
    }catch{/* Non-Linux callers still use kill(0). */}
    return true
  }catch(error){return error.code!=='ESRCH'}
}
export class StateStore {
  constructor(root) { this.root = root }
  async init() {
    await mkdir(this.root, { recursive: true, mode: 0o2770 })
    try { await chmod(this.root, 0o2770) } catch { /* existing deployment-owned directory */ }
    for (const name of ['cache', 'snapshots', 'locks', 'dictionaries']) {
      await mkdir(join(this.root,name), {recursive:true,mode:0o2770})
      try{await chmod(join(this.root,name),0o2770)}catch{/* deployment-owned, group-writable */}
    }
  }
  async read(area, key, maxAgeMs = Infinity) {
    if (!/^[a-f0-9]{64}$/.test(key)) return null
    try {
      const file = join(this.root, area, `${key}.json`)
      if ((await stat(file)).size > 40*1024*1024) return null
      const envelope = JSON.parse(await readFile(file, 'utf8'))
      if (envelope.key !== key || !Number.isFinite(envelope.writtenAt) || Date.now()-envelope.writtenAt < 0 || Date.now()-envelope.writtenAt > maxAgeMs || hash(envelope.payload) !== envelope.sha256) return null
      return envelope
    } catch { return null }
  }
  async write(area, key, payload) {
    const file = join(this.root,area,`${key}.json`)
    const temporary = `${file}.${randomUUID()}.tmp`
    const envelope = {key,writtenAt:Date.now(),sha256:hash(payload),payload}
    try {
      await writeFile(temporary,canonical(envelope), {mode:0o660,flag:'wx'})
      await chmod(temporary,0o660)
      if(area==='snapshots') {
        try{await link(temporary,file)}catch(error){
          if(error.code!=='EEXIST')throw error
          const existing=await this.read(area,key)
          if(!existing||existing.sha256!==envelope.sha256)fail('INVALID_ARTIFACT','不可变快照已存在且内容不同')
          return existing
        }
      } else await rename(temporary,file)
    } finally { await rm(temporary,{force:true}) }
    return envelope
  }
  async lock(name, deadlineAt, work, signal) {
    const directory = join(this.root,'locks',hash(name))
    let waited = false
    while (true) {
      if(signal?.aborted)fail('QUERY_ABORTED','查询已取消')
      if (Date.now() >= deadlineAt) fail('DEADLINE_EXCEEDED','等待查询队列超出任务预算')
      try {
        await mkdir(directory,{mode:0o2770})
        await chmod(directory,0o2770)
        break
      } catch (error) {
        if (error.code !== 'EEXIST') throw error
        waited = true
        await this.reclaim(directory)
        await sleep(Math.min(100,Math.max(1,deadlineAt-Date.now())))
      }
    }
    const owner = {pid:process.pid,identity:processIdentity(process.pid),host:hostname(),token:randomUUID(),children:[]}
    try {
      await writeFile(join(directory,'owner.json'),JSON.stringify(owner),{mode:0o660})
      const onSpawn=child=>{
        owner.children.push({pid:child.pid,identity:processIdentity(child.pid)})
        writeFileSync(join(directory,'owner.json'),JSON.stringify(owner),{mode:0o660})
      }
      return await work({waited,onSpawn})
    } finally {
      try {
        const actual=JSON.parse(await readFile(join(directory,'owner.json'),'utf8'))
        if(actual.token===owner.token) await rm(directory,{recursive:true,force:true})
      } catch { /* owner process terminated before metadata was written */ }
    }
  }
  async reclaim(directory) {
    // Serialize reclaimers so a second waiter cannot delete a newly acquired lock.
    const reaper=`${directory}.reaper`
    try {await mkdir(reaper,{mode:0o2770})}catch(error){if(error.code==='EEXIST')return;throw error}
    try {
      let owner
      try{owner=JSON.parse(await readFile(join(directory,'owner.json'),'utf8'))}catch{
        try{if(Date.now()-(await stat(directory)).mtimeMs>30000)await rm(directory,{recursive:true,force:true})}catch{/* another waiter acquired the lock */}
        return
      }
      if(owner.host!==hostname())return
      if(alive(owner.pid)&&(!owner.identity||processIdentity(owner.pid)===owner.identity))return
      // If the owning Node process died, first stop its verified orphan mysql clients.
      let running=false
      for(const child of owner.children??[]) {
        if(child.identity&&processIdentity(child.pid)===child.identity&&alive(child.pid)) {
          try{process.kill(child.pid,'SIGTERM')}catch{/* another OS user may own the child */}
          running=true
        }
      }
      if(!running)await rm(directory,{recursive:true,force:true})
    } finally {await rm(reaper,{recursive:true,force:true})}
  }
}
