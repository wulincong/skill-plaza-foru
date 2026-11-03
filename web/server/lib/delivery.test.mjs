import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync, utimesSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createServer } from 'node:http'
import { deliveryFingerprint, readDeliveryManifest, publishDelivery, handleDelivery } from './delivery.ts'

function setup(t) {
  const root = mkdtempSync(join(tmpdir(), 'plaza-delivery-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const workspace = join(root, 'workspace'), store = join(root, 'deliveries')
  mkdirSync(join(workspace, 'output/public/site/assets'), { recursive: true })
  writeFileSync(join(workspace, 'output/public/site/index.html'), '<!doctype html><img src="assets/a.svg">')
  writeFileSync(join(workspace, 'output/public/site/assets/a.svg'), '<svg xmlns="http://www.w3.org/2000/svg"/>')
  const files = ['pdf', 'png', 'xlsx', 'zip'].map(extension => {
    writeFileSync(join(workspace, `output/public/file.${extension}`), `example ${extension}`)
    return { name: `报告.${extension}`, path: `output/public/file.${extension}` }
  })
  const manifest = { web: [{ name: '报告网页', directory: 'output/public/site', entry: 'index.html' }], files }
  return { root, workspace, store, manifest }
}
async function listen(t, store) {
  const server = createServer((req, res) => { if (!handleDelivery(req, res, store)) { res.writeHead(404); res.end() } })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  t.after(() => new Promise(resolve => server.close(resolve)))
  return { server, base: `http://127.0.0.1:${server.address().port}` }
}

test('published websites and attachments survive workspace removal and a fresh server', async t => {
  const f = setup(t)
  const published = publishDelivery(f.workspace, f.manifest, f.store, 'https://plaza.example.com')
  assert.match(published.webLinks[0].url, /^https:\/\/plaza.example.com\/p\/[a-f0-9]{32}\/0\/$/)
  rmSync(f.workspace, { recursive: true })
  const { base } = await listen(t, f.store)
  const webPath = new URL(published.webLinks[0].url).pathname
  const page = await fetch(base + webPath)
  assert.equal(page.status, 200)
  assert.match(await page.text(), /assets\/a.svg/)
  assert.equal((await fetch(base + webPath + 'assets/a.svg')).status, 200)
  assert.match(page.headers.get('content-security-policy'), /sandbox allow-scripts;/)
  assert.doesNotMatch(page.headers.get('content-security-policy'), /allow-same-origin/)
  for (const item of published.downloads) {
    const response = await fetch(base + new URL(item.url).pathname)
    assert.equal(response.status, 200)
    assert.match(response.headers.get('content-disposition'), /^attachment;/)
    assert.match(response.headers.get('content-disposition'), /filename\*=UTF-8''%E6%8A%A5%E5%91%8A/)
    assert.match(await response.text(), /example/)
  }
  const head = await fetch(base + webPath, { method: 'HEAD' })
  assert.equal(head.status, 200)
  assert.equal(await head.text(), '')
})

test('nested entries redirect to their real location and serve only declared static files', async t => {
  const f = setup(t)
  mkdirSync(join(f.workspace, 'output/public/site/nested'))
  writeFileSync(join(f.workspace, 'output/public/site/nested/start.html'), '<!doctype html><title>nested</title>')
  f.manifest.web[0].entry = 'nested/start.html'
  const links = publishDelivery(f.workspace, f.manifest, f.store, 'https://plaza.example.com')
  const path = new URL(links.webLinks[0].url).pathname
  const { base } = await listen(t, f.store)
  const redirect = await fetch(base + path, { redirect: 'manual' })
  assert.equal(redirect.headers.get('location'), path + 'nested/start.html')
  assert.equal((await fetch(base + path.slice(0, -1), { redirect: 'manual' })).status, 302)
  for (const tail of ['.env', 'metadata.json', 'missing.html', '%2e%2e%2fmetadata.json', '%2Fapi%2Fruns', '%00', '%ZZ']) {
    assert.equal((await fetch(base + path + tail)).status, 404, tail)
  }
  assert.equal((await fetch(base + path, { method: 'POST' })).status, 405)
})

test('missing, hidden, internal, symlink and traversal declarations never publish partial output', t => {
  const f = setup(t)
  mkdirSync(f.store)
  mkdirSync(join(f.workspace, 'output/internal'))
  writeFileSync(join(f.workspace, 'output/internal/evidence.xlsx'), 'private')
  symlinkSync(join(f.workspace, 'output/public/file.pdf'), join(f.workspace, 'output/public/link.pdf'))
  symlinkSync(join(f.workspace, 'output/public/site'), join(f.workspace, 'output/public/link-site'))
  const bad = [
    { files: [{ name: 'bad', path: '../outside' }] },
    { files: [{ name: 'bad', path: '/etc/passwd' }] },
    { files: [{ name: 'bad', path: 'output/internal/evidence.xlsx' }] },
    { files: [{ name: 'bad', path: '.env' }] },
    { files: [{ name: 'bad', path: 'output/public/link.pdf' }] },
    { web: [{ name: 'bad', directory: 'output/public/link-site', entry: 'index.html' }] },
    { web: [{ name: 'bad', directory: 'output/public/site', entry: 'absent.html' }] },
    { web: [{ name: 'bad', directory: '.', entry: 'index.html' }] },
    { ...f.manifest, files: [...f.manifest.files, { name: 'missing', path: 'missing.pdf' }] },
  ]
  for (const manifest of bad) assert.throws(() => publishDelivery(f.workspace, manifest, f.store, 'https://plaza.example.com'))
  symlinkSync('/etc/passwd', join(f.workspace, 'output/public/site/assets/secret'))
  assert.throws(() => publishDelivery(f.workspace, f.manifest, f.store, 'https://plaza.example.com'))
  assert.deepEqual(readdirSync(f.store), [])
})

test('only a new complete manifest is captured on follow-up turns', t => {
  const f = setup(t), file = join(f.workspace, 'delivery.json')
  assert.equal(readDeliveryManifest(f.workspace), undefined)
  writeFileSync(file, JSON.stringify(f.manifest))
  const fingerprint = deliveryFingerprint(f.workspace)
  assert.deepEqual(readDeliveryManifest(f.workspace), f.manifest)
  assert.equal(readDeliveryManifest(f.workspace, fingerprint), undefined)
  utimesSync(file, new Date(), new Date(Date.now() + 2000))
  assert.deepEqual(readDeliveryManifest(f.workspace, fingerprint), f.manifest)
  writeFileSync(file, '{unfinished')
  assert.throws(() => readDeliveryManifest(f.workspace, fingerprint))
  rmSync(file)
  symlinkSync(join(f.workspace, 'output/public/file.pdf'), file)
  assert.throws(() => readDeliveryManifest(f.workspace, fingerprint), /符号链接/)
})
