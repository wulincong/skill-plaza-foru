import {test} from 'node:test'
import assert from 'node:assert/strict'
import {configOf,competencyFilters,competencyContext} from './useTaskConfigs.ts'
test('assessment form omits removed inputs and stale values cannot alter the request',()=>{
 const config=configOf('competency-assessment')
 assert.ok(config)
 const fields=config.sections.flatMap(s=>s.fields)
 for(const id of ['city','positionId','education','mode'])assert.equal(fields.some(f=>f.id===id),false)
 assert.deepEqual(competencyFilters({role:'前端',positionType:'实习',education:'本科',city:'广州市'}),{keyword:'前端',positionType:'SHIXI'})
})
test('assessment context keeps personal text separate from JD scope and preserves newlines',()=>{
 const parts=competencyContext({role:'前端',mode:'具体岗位',positionId:'123',projects:'项目一\n项目二',resume:'学历\n项目与技能'})
 assert.deepEqual(JSON.parse(parts[3]),{mode:'direction',positionId:''})
 assert.equal(JSON.parse(parts[5]).education,undefined)
 assert.equal(JSON.parse(parts[5]).projects,'项目一\n项目二')
 assert.equal(JSON.parse(parts[5]).resume,'学历\n项目与技能')
 assert.equal(JSON.parse(parts[5]).role,undefined)
})
