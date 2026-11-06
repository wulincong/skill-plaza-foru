import {readFileSync} from 'node:fs'
const regions=JSON.parse(readFileSync(new URL('./data/report-regions.json',import.meta.url),'utf8')).regions
function negatedRegionPrefix(text,start) {
 const prefix=text.slice(0,start).split(/[,，。；;\n]/).at(-1)
 return /(?:不要|不用|不需要|别|无需|不能|不许|不是|并非|排除|不含|不包括)[^，,。；;\n]{0,12}$/.test(prefix)&&!/(?:而是|只要|改用|而要|请用|仅用)[^，,。；;\n]{0,4}$/.test(prefix)
}
export function requestedRegion(text='') {
 const changes=[...text.matchAll(/改为|改成|换成|改看|只看/g)].filter(m=>!negatedRegionPrefix(text,m.index))
 if(changes.length){const last=changes.at(-1),tail=text.slice(last.index+last[0].length);if(regions.some(r=>[r.name,...r.aliases??[]].some(a=>tail.includes(a))))text=tail}
 const hits=[]
 for(const region of regions)for(const alias of new Set([region.name,...region.aliases??[]])) {
  if(alias.length<2)continue
  let start=text.indexOf(alias)
  while(start>=0){if(!negatedRegionPrefix(text,start))hits.push({start,end:start+alias.length,region});start=text.indexOf(alias,start+1)}
 }
 const chosen=hits.filter(h=>!hits.some(v=>v.start<=h.start&&v.end>=h.end&&v.end-v.start>h.end-h.start))
 const unique=[...new Map(chosen.map(h=>[[h.region.level,h.region.province,h.region.name].join('|'),h.region])).values()]
 const cities=unique.filter(r=>r.level==='city'),provinces=unique.filter(r=>r.level==='province')
 let rest=text
 for(const h of [...chosen].sort((a,b)=>b.start-a.start))rest=rest.slice(0,h.start)+' '.repeat(h.end-h.start)+rest.slice(h.end)
 if(/[\u4e00-\u9fff]{2,8}(?:区|县|街道)(?!块|域|分|别|间)/.test(rest.replaceAll('地区','')))return {status:'unsupported'}
 if(chosen.some(a=>chosen.some(b=>a.start===b.start&&a.end===b.end&&a.region.level!==b.region.level)))return {status:'ambiguous'}
 if(cities.length===1&&provinces.every(r=>r.name===cities[0].province))return {status:'ready',region:{level:'city',province:cities[0].province,name:cities[0].name}}
 if(!cities.length&&provinces.length===1)return {status:'ready',region:{level:'province',name:provinces[0].name}}
 if(!unique.length&&/全国|中国(?:范围|各地|各省)/.test(text))return {status:'ready',region:{level:'national',name:'全国'}}
 return {status:unique.length?'ambiguous':'missing'}
}
export function exactRegionMatches(actual,text) {
 const expected=requestedRegion(text)
 if(['ambiguous','unsupported'].includes(expected.status))return false
 if(expected.status==='missing')return true
 const region=expected.region
 if(actual?.level!==region.level)return false
 if(region.level==='national')return true
 if(requestedRegion(actual.name).region?.name!==region.name)return false
 return region.level!=='city'||!actual.province||requestedRegion(actual.province).region?.name===region.province
}
export function turnRegionText(turn={}) {
 return requestedRegion(turn.requestText).status!=='missing'?turn.requestText:turn.originRequestText??turn.requestText??''
}

export function isReportRequest(value='') {
 const text=value.replace(/(?<![A-Za-z])AI(?![A-Za-z])/gi,'人工智能')
 if(/(?:不要|不用|不需要|别)(?:再|帮我)?(?:生成|制作|写|做)?.{0,12}(?:报告|简报|研报)/.test(text))return false
 if(/^(?:请问)?(?:什么是|如何|怎么|为什么|介绍|解释)|报告.*(?:怎么|如何|怎样).*(?:生成|制作|获取|使用)/.test(text.trim()))return false
 if(/(?:怎么|如何|怎样).{0,6}(?:生成|制作|获取|使用).{0,12}(?:报告|简报)|报告.{0,6}(?:怎么|如何|多久|多长|几分钟).*生成|生成.{0,10}(?:多久|多长|几分钟)/.test(text))return false
 const region=requestedRegion(text)
 const sector=/人工智能|智能制造|机器人|低空经济|新能源汽车|新一代信息技术|智能网联汽车|跨境电商|智能硬件|直播电商|半导体|纺织服装|生物医药|新能源/.test(text)
 const artifact=/(?:一份|一篇|一版|一张|份|篇).{0,35}(?:分析|研究|调研|调查|观察|画像|概览)|(?:分析|研究|调研|调查|观察|画像|概览).{0,20}(?:一份|一篇|一版|一张)/.test(text)
 const subject=/报告|简报|研报|人才需求|人才供需|岗位需求|招聘需求|招聘(?:情况|格局|分析)|用人需求/.test(text)
 return artifact&&/生成|制作|整理|写|做|给|来|出|要|想|需要|希望|麻烦|请/.test(text)||subject&&(/生成|制作|整理|写|做|给|来|出|要|想|需要|希望|麻烦|请|看看|了解|分析|调研|完成|交付|修改|重新|继续|优化|加强|调整/.test(text)||region.status!=='missing'&&sector)||region.status!=='missing'&&sector&&/(?:做|写|出|给|来|整理|需要|想要|希望).{0,30}(?:分析|研究|调研)|分析一下|调研一下|招人情况|人才情况|就业情况|岗位需求|招聘需求/.test(text)
}

export function filterIntentProblems(filters={},text='') {
 const issues=[],fullScope=requestedRegion(text).status==='ready'
 const labels=[['博士','BOSHI'],['硕士','SHUOSHI'],['本科','BENKE'],['大专','DAZHUAN'],['高职','GAOZHI'],['中专','ZHONGZHUAN/ZHONGJI'],['高中','GAOZHONG'],['初中','CHUZHONGJIYIXIA']]
 const mentioned=labels.filter(([label])=>text.includes(label)).map(([,code])=>code)
 if(fullScope&&filters.education?.length&&!mentioned.length&&!/学历不限|专科/.test(text))issues.push('用户没有限定学历，不得新增education筛选')
 if(/(?:只看|仅看|仅限|限定|筛选)(?:学历要求为|学历为|学历是)?(?:博士|硕士|本科|大专|高职|中专|高中|初中)|学历(?:为|是)(?:博士|硕士|本科|大专|高职|中专|高中|初中)/.test(text)&&mentioned.length===1&&!/以上|以下|及以上|及以下|至少/.test(text)&&JSON.stringify([...(filters.education??[])].sort())!==JSON.stringify([...mentioned].sort()))issues.push('学历筛选必须严格使用用户指定的'+mentioned[0])
 if(fullScope&&filters.experience?.length&&!/(?:工作|从业|任职|经验).{0,10}[一二三四五六七八九十两0-9]+\s*年|[一二三四五六七八九十两0-9]+\s*年(?:以内|以下|以上|工作经验|相关经验|经验)|应届|在校|经验不限|无经验/.test(text))issues.push('用户没有限定工作年限，不得新增experience筛选；章节需要分析经验分布不等于只查某种经验')
 if(fullScope&&filters.jobType?.length&&!/校招|社招|社会招聘|校园招聘|实习|兼职|全职/.test(text))issues.push('用户没有限定招聘类型，不得新增jobType筛选')
 return issues
}
