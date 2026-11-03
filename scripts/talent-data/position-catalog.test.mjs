import test from 'node:test'
import assert from 'node:assert/strict'
import {execFileSync} from 'node:child_process'
import {fileURLToPath} from 'node:url'

const cli=fileURLToPath(new URL('../../.agents/skills/talent-data-query/scripts/query.mjs',import.meta.url))
function catalog(...args) {
  const env={...process.env, MYSQL_HOST:'127.0.0.1', MYSQL_PORT:'1', MYSQL_BIN:'/nonexistent-mysql'}
  return JSON.parse(execFileSync(process.execPath,[cli,'catalog',...args],{env,encoding:'utf8'}))
}

test('an exact catalog name keeps different industries and multiple original nodes in one industry',()=>{
  const result=catalog('--job','质量检验员','--match','exact')
  assert.equal(result.matchedJobs,1)
  const [job]=result.jobs
  assert.equal(job.name,'质量检验员')
  assert.deepEqual(Object.keys(job.nodes).sort(),result.industries.map(r=>r.id).sort())
  assert.ok(result.industries.length>1)
  const ids=Object.values(job.nodes).flat()
  assert.ok(ids.length>result.industries.length)
  assert.equal(new Set(ids).size,ids.length)
  assert.ok(ids.every(id=>typeof id==='string' && /^\d+$/.test(id)))
  assert.equal(catalog('--job','不存在的目录岗位Z8A').matchedJobs,0)
})

test('industry pagination counts distinct names and combined filters keep only matching links',()=>{
  const industry='15', names=[]
  let offset=0, total
  do {
    const page=catalog('--industry',industry,'--offset',String(offset))
    assert.equal(page.industries.length,1)
    assert.equal(page.industries[0].id,industry)
    for (const row of page.jobs) {
      assert.deepEqual(Object.keys(row.nodes),[industry])
      names.push(row.name)
    }
    total=page.matchedJobs
    offset=page.nextOffset
  } while(offset!==null)
  assert.equal(names.length,total)
  assert.equal(new Set(names).size,total)
  const tests=catalog('--industry',industry,'--job','测试')
  assert.equal(tests.matchedJobs,names.filter(name=>name.includes('测试')).length)
})
