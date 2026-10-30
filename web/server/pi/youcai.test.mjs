import assert from 'node:assert/strict'
import { test } from 'node:test'
import registerYoucai from './youcai.js'

function setup() {
  let provider
  let beforeHeaders
  registerYoucai({
    registerProvider(name, config) { provider = { name, ...config } },
    on(name, handler) {
      assert.equal(name, 'before_provider_headers')
      beforeHeaders = handler
    },
  })
  return { provider, beforeHeaders }
}

test('youcai strips SDK and stored authorization without removing unrelated headers', () => {
  const { beforeHeaders } = setup()
  const headers = { authorization: 'Bearer stored-secret', AUTHORIZATION: 'Bearer other-secret', 'X-Request-ID': 'probe' }
  beforeHeaders({ headers }, { model: { provider: 'youcai' } })
  assert.deepEqual(headers, { authorization: null, AUTHORIZATION: null, Authorization: null, 'X-Request-ID': 'probe' })
})

test('switching away from youcai preserves the selected provider authentication', () => {
  const { beforeHeaders } = setup()
  const headers = { Authorization: 'Bearer other-provider-key' }
  beforeHeaders({ headers }, { model: { provider: 'deepseek' } })
  assert.equal(headers.Authorization, 'Bearer other-provider-key')
  beforeHeaders({ headers }, {})
  assert.equal(headers.Authorization, 'Bearer other-provider-key')
})

test('service migration can override the endpoint without changing model routing', () => {
  const previous = process.env.YOUCAI_BASE_URL
  try {
    process.env.YOUCAI_BASE_URL = ' https://example.test/v1 '
    const { provider } = setup()
    assert.equal(provider.baseUrl, 'https://example.test/v1')
    assert.equal(provider.name, '优才自部署模型')
    assert.deepEqual(provider.models.map(model => model.id), ['youcai'])
  } finally {
    if (previous === undefined) delete process.env.YOUCAI_BASE_URL
    else process.env.YOUCAI_BASE_URL = previous
  }
})
