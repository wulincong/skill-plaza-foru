import { test } from 'node:test'
import assert from 'node:assert/strict'
import { configOf, jobFilters } from './useTaskConfigs.ts'
import { SKILL_PROMPTS, INSTALLED_SKILLS } from '../../server/lib/skills.ts'

test('dropdown labels map to the verified API keys and unspecified filters are omitted',()=>{
 assert.deepEqual(jobFilters({role:'前端开发',city:'广州市',salary:'3-5k',positionType:'实习',industry:'互联网/IT/电子/通信',education:'大专',experience:'1-3年'}),{keyword:'前端开发',city:'广州市',salary:'LESS_THAN_5K',positionType:'SHIXI',industry:'IT',education:'DAZHUAN',experience:'LESS_THAN_3'})
 assert.deepEqual(jobFilters({role:'前端',city:'  '}),{keyword:'前端'})
 assert.deepEqual(jobFilters({role:'前端',city:'广州',salary:'不限',industry:'不限'}),{keyword:'前端',city:'广州'})
 assert.throws(()=>jobFilters({role:'前端',city:'广州',industry:'INVENTED'}))
})
test('graduation maps only when explicit experience was not selected; job skill is registered',()=>{
 assert.equal(jobFilters({role:'前端',city:'广州',graduation:'在校生'}).experience,'ON_CAMPUS')
 assert.equal(jobFilters({role:'前端',city:'广州',graduation:'应届毕业生',experience:'1-3年'}).experience,'LESS_THAN_3')
 assert.deepEqual(configOf('job-matching').sections[0].fields.filter(f=>f.required).map(f=>f.id),['role'])
 assert.ok(INSTALLED_SKILLS.has('job-matching'));assert.ok(SKILL_PROMPTS['job-matching'])
})
