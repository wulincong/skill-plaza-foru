import test from 'node:test'
import assert from 'node:assert/strict'
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync,unlinkSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createHash} from 'node:crypto'
import {readWechatDelivery} from './wechatDelivery.ts'
import {publishDelivery,deliveryFingerprint} from './delivery.ts'

test('built report survives overwritten or missing model declaration and publishes the actual image site',()=>{
 const root=mkdtempSync(join(tmpdir(),'wechat-delivery-'))
 try {
  const workspace=join(root,'workspace'),report=join(workspace,'wechat-report/output/report')
  const site=join(workspace,'wechat-report/output/public/site')
  mkdirSync(report,{recursive:true});mkdirSync(site,{recursive:true})
  writeFileSync(join(site,'index.html'),'<html><img src="page.png"></html>')
  writeFileSync(join(site,'page.png'),'image fixture')
  writeFileSync(join(site,'../report.zip'),'zip fixture')
  const manifest={pages:[{file:'page.png'}]}
  writeFileSync(join(report,'manifest.json'),JSON.stringify(manifest))
  const sha=createHash('sha256').update(JSON.stringify(manifest)).digest('hex')
  writeFileSync(join(report,'quality.json'),JSON.stringify({all_pass:true,manifest_sha256:sha}))
  const delivery={web:[{name:'广东省机器人人才需求报告',directory:'wechat-report/output/public/site',entry:'index.html'}],
    files:[{name:'报告图片',path:'wechat-report/output/public/report.zip'}]}
  const startedAt=Date.now()-1000
  const receipt={schema:'wechat-build/1',startedAt:new Date().toISOString(),manifestSha256:sha,deliveryManifest:delivery}
  writeFileSync(join(report,'build_receipt.json'),JSON.stringify(receipt))
  writeFileSync(join(workspace,'delivery.json'),JSON.stringify({web:[{name:'wrong',directory:'wechat-report/output/article',entry:'index.html'}]}))
  const recovered=readWechatDelivery(workspace,startedAt)
  assert.deepEqual(recovered,delivery)
  const store=join(root,'store'),links=publishDelivery(workspace,recovered,store,'http://localhost')
  assert.equal(links.webLinks.length,1);assert.equal(links.downloads.length,1)
  const id=links.webLinks[0].url.split('/')[4]
  assert.equal(readFileSync(join(store,id,'web/0/index.html'),'utf8'),'<html><img src="page.png"></html>')
  unlinkSync(join(workspace,'delivery.json'))
  assert.deepEqual(readWechatDelivery(workspace,startedAt),delivery)
  writeFileSync(join(report,'manifest.json'),'changed')
  assert.throws(()=>readWechatDelivery(workspace,startedAt),/质检不一致/)
  writeFileSync(join(report,'manifest.json'),JSON.stringify(manifest))
  writeFileSync(join(report,'build_receipt.json'),JSON.stringify({...receipt,deliveryManifest:{...delivery,web:[{...delivery.web[0],directory:'private'}]}}))
  assert.throws(()=>readWechatDelivery(workspace,startedAt),/交付目录/)
  writeFileSync(join(report,'build_receipt.json'),JSON.stringify({...receipt,startedAt:'2000-01-01'}))
  assert.equal(readWechatDelivery(workspace,startedAt),undefined)
  writeFileSync(join(workspace,'delivery.json'),JSON.stringify(delivery))
  assert.throws(()=>readWechatDelivery(workspace,startedAt),/旧成品/)
  assert.equal(readWechatDelivery(workspace,startedAt,deliveryFingerprint(workspace)),undefined)
 } finally {rmSync(root,{recursive:true,force:true})}
})
