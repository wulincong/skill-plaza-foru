import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ExecutionTracker } from './execution.ts'
import { executionTimes } from '../../shared/execution.ts'
import registerToolPurpose from '../pi/tool-purpose.js'

test('model requests ask for an independent purpose on each built-in tool', () => {
  let annotate
  registerToolPurpose({ on(event, handler) {
    assert.equal(event, 'context_with_system')
    annotate = handler
  } })
  const toolsAdded = ['read', 'bash', 'write', 'edit'].map(name => ({
    name, parameters: { properties: { original: { type: 'string' } }, required: ['original'] },
  }))
  const messages = [{ role: 'system', toolsAdded }, { role: 'assistant', content: [] }]
  annotate({ messages })
  annotate({ messages })
  for (const { parameters } of toolsAdded) {
    assert.equal(parameters.properties.purpose.type, 'string')
    assert.deepEqual(parameters.required, ['original', 'purpose'])
  }
})

test('correlate public notes, reasoning spans and actual execution across interleaved parallel calls', () => {
  const run = new ExecutionTracker()
  const start = () => run.accept({ type: 'message_start', message: { role: 'assistant' } }, 0)
  const delta = (type, at) => run.accept({ type: 'message_update', assistantMessageEvent: { type, delta: 'private reasoning' } }, at)
  const calls = (note, ids) => run.accept({ type: 'message_end', message: { role: 'assistant', content: [
    { type: 'text', text: note }, ...ids.map(id => ({ type: 'toolCall', id, arguments: { secret: 'private args' } })),
  ] } }, 0)
  const tool = (phase, id, at, isError = false, purpose) => run.accept({
    type: 'tool_execution_' + phase, toolCallId: id, toolName: 'read', isError,
    ...(phase === 'start' ? { args: { path: '/private/file', purpose } } : {}),
  }, at)

  start()
  delta('thinking_start', 10); delta('thinking_delta', 15); delta('thinking_end', 20)
  delta('toolcall_start', 23); delta('toolcall_end', 26)
  calls('先读取两份资料', ['a', 'b'])
  tool('start', 'a', 30, false, '核对岗位数量'); tool('start', 'b', 40, false, '核对地区分布')
  assert.equal(run.steps[0].tools[1].purpose, '核对地区分布')
  start(); calls('再次核验', ['c'])
  tool('end', 'b', 60, true); tool('end', 'a', 80)
  tool('start', 'c', 90, false, '查看 /private/file'); tool('end', 'c', 100)
  assert.deepEqual(run.steps.map(step => [step.note, step.tools.map(t => t.id)]), [
    ['先读取两份资料', ['a', 'b']], ['再次核验', ['c']],
  ])
  assert.equal(run.steps[0].tools[1].state, 'failed')
  assert.deepEqual(run.steps.flatMap(s => s.tools.map(t => t.purpose)), ['核对岗位数量', '核对地区分布', undefined])
  assert.deepEqual(executionTimes(run.steps, 120), { toolMs: 60, thinkingMs: 10, otherMs: 50 })
  assert.doesNotMatch(JSON.stringify(run.steps), /private/)
})

test('unknown boundaries stay unknown and reasoning without tools forms its own step', () => {
  const run = new ExecutionTracker()
  run.accept({ type: 'message_update', assistantMessageEvent: { type: 'thinking_delta', delta: 'private' } }, 100)
  assert.deepEqual(run.steps, [{ thinking: [{ startedAt: 100 }], tools: [] }])
  assert.equal(executionTimes(run.steps, 400), undefined)
  assert.deepEqual(executionTimes([], 400), { toolMs: 0, thinkingMs: 0, otherMs: 400 })
})
