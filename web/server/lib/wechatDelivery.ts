/** A successful report build owns its delivery declaration, not the model's closing text. */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { readDeliveryManifest, type DeliveryManifest } from './delivery.ts'
import { reportBuildReady } from '../pi/reportWorkflowPolicy.mjs'

export function readWechatDelivery(workspace:string,startedAt:number,previous?:string):DeliveryManifest|undefined {
  let receipt:any
  try { receipt=JSON.parse(readFileSync(join(workspace,'wechat-report/output/report/build_receipt.json'),'utf8')) }
  catch(error:any) {
    if(error.code!=='ENOENT') throw new Error('报告构建回执无法读取或格式错误')
  }
  // Older builds retain the old contract; registration still checks their full receipt.
  if(!receipt?.deliveryManifest) return readDeliveryManifest(workspace,previous)
  if(Date.parse(receipt.startedAt)<startedAt) {
    if(readDeliveryManifest(workspace,previous)) throw new Error('本轮尚未通过报告构建，不能重新交付旧成品')
    return undefined
  }
  if(receipt.schema!=='wechat-build/1' || !reportBuildReady(workspace,{startedAt}))
    throw new Error('报告构建回执与当前图片质检不一致')
  const manifest=receipt.deliveryManifest
  if(manifest.web?.length!==1 || manifest.files?.length!==1 ||
    manifest.web[0].directory!=='wechat-report/output/public/site' || manifest.web[0].entry!=='index.html' ||
    manifest.files[0].path!=='wechat-report/output/public/report.zip')
    throw new Error('报告构建回执中的交付目录不符合图片成品约定')
  return manifest
}
