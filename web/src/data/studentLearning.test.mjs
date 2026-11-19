import assert from 'node:assert/strict'
import { test } from 'node:test'
import { configOf } from './useTaskConfigs.ts'
import { SKILLS } from './skills.ts'
import { SKILL_PROMPTS, INSTALLED_SKILLS, SKILL_DATA_DEPENDENCIES } from '../../server/lib/skills.ts'

test('student form offers four basic inputs and optional notes and requires only target role; registered skill is runnable',()=>{
  const config=configOf('student-learning')
  const fields=config.sections.flatMap(s=>s.fields)
  assert.deepEqual(fields.map(f=>f.id),['role','goal','foundation','availability','notes'])
  assert.equal(fields.find(f=>f.id==='notes').type,'textarea')
  assert.deepEqual(fields.filter(f=>f.required).map(f=>f.id),['role'])
  assert.equal(config.knowledge.length,0)
  assert.ok(SKILLS.find(s=>s.slug==='student-learning'))
  assert.ok(INSTALLED_SKILLS.has('student-learning'))
  assert.ok(SKILL_PROMPTS['student-learning'])
  assert.equal(SKILL_DATA_DEPENDENCIES['student-learning'],'weknora-retrieval')
})
