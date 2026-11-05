// Shared chart/publication boundary, independent of any business report schema.
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { checkReportWebEntry } from '../../../../web/server/lib/reportWeb.ts'
import { publishDelivery } from '../../../../web/server/lib/delivery.ts'

const embed = fileURLToPath(new URL('./embed_chart.py', import.meta.url))
const figure = fileURLToPath(new URL('../../chart-visualization/scripts/figure.py', import.meta.url))

test('a report embeds the verified shared chart and the published entry renders without a nested document', async t => {
  const root = await mkdtemp(join(tmpdir(), 'shared-report-chart-'))
  t.after(() => rm(root, {recursive:true, force:true}))
  const run = (...args) => spawnSync('python3', args, {cwd:root,encoding:'utf8'})
  const success = (...args) => {
    const result = run(...args)
    assert.equal(result.status,0,result.stderr + result.stdout)
  }
  const manifest = {}
  const denominator = 4
  const groups = [{label:'本科',count:3},{label:'大专',count:1}]
  const spec = {schema:'figure/1',id:'EDU',lang:'zh',title:'学历要求',caption:`分母 ${denominator} 条`,source:'D1 / edu',
    datasets:{edu:groups.map(g => ({label:g.label,count:g.count}))},
    panels:[{kind:'barh',title:'学历要求',data:'edu',fields:{category:'label',value:'count'},x_label:'岗位记录数 (条)',y_label:'学历'}]}
  await writeFile(join(root,'spec.json'),JSON.stringify(spec))
  success(figure,'render','spec.json','--out','chart')
  const site = 'output/public/site', entry = join(site,'index.html')
  await mkdir(join(root,site),{recursive:true})
  manifest.web = [{name:'报告',directory:site,entry:'index.html'}]
  const publish = () => publishDelivery(root,manifest,join(root,'publications'),'https://example.invalid',checkReportWebEntry)
  const template = '<html><body><!-- chart:EDU --></body></html>'
  await writeFile(join(root,entry),'<html><body><figure><img alt="实训室布局"><figcaption>校方提供的平面图</figcaption></figure></body></html>')
  assert.equal(publish().webLinks.length,1)
  for (const bad of ['<object data="chart/figure.svg"></object>','<figure><svg class="chart"></svg></figure>',
    '<div><svg role="img"><text>本科</text></svg></div>','<img src="chart/figure.svg">',template]) {
    await writeFile(join(root,entry),bad)
    assert.throws(publish,/embed_chart.py/)
  }
  success(embed,'spec.json','chart',entry)
  success(embed,'spec.json','chart',entry)
  const block = (await readFile(join(root,'chart/figure.html'),'utf8')).match(/<figure\b[\s\S]*?<\/figure>/)[0]
  const embeddedPage = await readFile(join(root,entry),'utf8')
  assert.equal(embeddedPage.split(block).length,2)
  assert.ok(!embeddedPage.includes('<!-- chart:EDU -->'))
  const links = publish()
  assert.equal(links.webLinks.length,1)
  const id = new URL(links.webLinks[0].url).pathname.split('/')[2]
  assert.ok((await readFile(join(root,'publications',id,'web/0/index.html'),'utf8')).includes(block))
  await writeFile(join(root,entry),template)
  await writeFile(join(root,'chart/figure.svg'),'<svg/>')
  assert.notEqual(run(embed,'spec.json','chart',entry).status,0)
  assert.equal(await readFile(join(root,entry),'utf8'),template)
})
