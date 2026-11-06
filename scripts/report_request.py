"""Report intent and exact geographic scope, shared by intake and catalog guards."""
import json,re
from pathlib import Path

REGIONS=json.loads((Path(__file__).parent/'data/report-regions.json').read_text('utf-8'))['regions']
INDUSTRIES=['人工智能','智能制造','机器人','低空经济','新能源汽车','新一代信息技术','智能网联汽车','跨境电商','智能硬件','直播电商','半导体','纺织服装','生物医药','新能源']
ALIASES={'AI':'人工智能','智能网联车':'智能网联汽车'}

def normalize(text):
    for alias,name in ALIASES.items():
        text=re.sub(r'(?<![A-Za-z])'+re.escape(alias)+r'(?![A-Za-z])',name,text,flags=re.I) if alias=='AI' else text.replace(alias,name)
    return text

def negated_region_prefix(text,start):
    prefix=re.split(r'[,，。；;\n]',text[:start])[-1]
    return bool(re.search(r'(?:不要|不用|不需要|别|无需|不能|不许|不是|并非|排除|不含|不包括)[^，,。；;\n]{0,12}$',prefix)) and not re.search(r'(?:而是|只要|改用|而要|请用|仅用)[^，,。；;\n]{0,4}$',prefix)


def region_request(text):
    # The latest explicit scope change supersedes earlier places in this turn.
    changes=[m for m in re.finditer(r'改为|改成|换成|改看|只看',text) if not negated_region_prefix(text,m.start())]
    if changes:
        tail=text[changes[-1].end():]
        if any(alias in tail for x in REGIONS for alias in [x['name'],*x.get('aliases',[])]):text=tail
    hits=[]
    for region in REGIONS:
        for alias in {region['name'],*region.get('aliases',[])}:
            if len(alias)<2:continue
            for match in re.finditer(re.escape(alias),text):
                if not negated_region_prefix(text,match.start()):hits.append((match.start(),match.end(),region))
    hits=[h for h in hits if not any(a<=h[0] and b>=h[1] and b-a>h[1]-h[0] for a,b,_ in hits)]
    unique={(x['level'],x.get('province',''),x['name']):x for _,_,x in hits}
    cities=[x for x in unique.values() if x['level']=='city'];provinces=[x for x in unique.values() if x['level']=='province']
    rest=text
    for a,b,_ in sorted(hits,reverse=True,key=lambda h:h[0]):rest=rest[:a]+' '*(b-a)+rest[b:]
    if re.search(r'[\u4e00-\u9fff]{2,8}(?:区|县|街道)(?!块|域|分|别|间)',rest.replace('地区','')):
        return {'status':'unsupported','message':'目前支持全国、省和城市范围，请明确要分析的城市；不会自行扩大到所在省。'}
    if any(a==c and b==d and x['level']!=y['level'] for a,b,x in hits for c,d,y in hits):return {'status':'ambiguous','message':'这个名称同时是省名和市名，请明确使用省或市全称。'}
    if len(cities)==1 and all(x['name']==cities[0]['province'] for x in provinces):
        x=cities[0];return {'status':'ready','region':{k:x[k] for k in ('level','province','name')}}
    if not cities and len(provinces)==1:
        x=provinces[0];return {'status':'ready','region':{'level':'province','name':x['name']}}
    if not unique and re.search(r'全国|中国(?:范围|各地|各省)',text):return {'status':'ready','region':{'level':'national','name':'全国'}}
    if unique:return {'status':'ambiguous','message':'检测到多个或有歧义的地区，请明确这次要分析的一个省或城市。'}
    return {'status':'missing'}

def scope_matches(actual,text):
    expected=region_request(text)
    if expected['status'] in ('ambiguous','unsupported'):return False
    if expected['status']=='missing':return True
    value=expected['region'];level=actual.get('level')
    if level!=value['level']:return False
    if level=='national':return True
    known=region_request(actual.get('name',''))
    if known.get('region',{}).get('name')!=value['name']:return False
    return level!='city' or not actual.get('province') or region_request(actual['province']).get('region',{}).get('name')==value['province']

def classify(text):
    text=normalize(text.strip())
    if text.startswith('/') and text!='/报告生成':return {'intent':'none'}
    region=region_request(text)
    if re.search(r'报告.*(?:怎么|如何|怎样).*(?:生成|制作|获取|使用)',text) and region['status']=='missing':return {'intent':'help'}
    if re.search(r'(?:怎么|如何|怎样).{0,6}(?:生成|制作|获取|使用).{0,12}(?:报告|简报)|报告.{0,6}(?:怎么|如何|多久|多长|几分钟).*生成|生成.{0,10}(?:多久|多长|几分钟)',text):return {'intent':'help'}
    sectors=[x for x in INDUSTRIES if x in text];sectors=[x for x in sectors if not any(x!=y and x in y for y in sectors)]
    if re.search(r'(?:不要|不用|不需要|别)(?:再|帮我)?(?:生成|制作|写|做)?.{0,12}(?:报告|简报|研报)',text):return {'intent':'none'}
    if not region.get('region') and not sectors and re.search(r'(?:能|可以|会|支持).{0,6}(?:做|写|生成|制作).{0,6}(?:什么|哪些|哪种)?报告',text):return {'intent':'help'}
    if re.search(r'(?:怎么|如何|怎样|能不能|可以).{0,6}(?:生成|制作|使用|获得|获取).{0,6}报告',text) and not region.get('region') and not sectors:return {'intent':'help'}
    if text in ('报告','报告帮助','报告用法','使用报告','报告指南','/报告生成'):return {'intent':'help'}
    artifact=bool(re.search(r'(?:一份|一篇|一版|一张|份|篇).{0,35}(?:分析|研究|调研|调查|观察|画像|概览)|(?:分析|研究|调研|调查|观察|画像|概览).{0,20}(?:一份|一篇|一版|一张)',text))
    subject=bool(re.search(r'报告|简报|研报|人才需求|人才供需|岗位需求|招聘需求|招聘(?:情况|格局|分析)|用人需求',text))
    desire=bool(re.search(r'生成|制作|整理|写|做|给|来|出|要|想|需要|希望|麻烦|请|看看|了解|分析|调研',text))
    if not (artifact and desire or subject and (desire or (region['status']!='missing' and sectors)) or region.get('region') and sectors and re.search(r'(?:做|写|出|给|来|整理|需要|想要|希望).{0,30}(?:分析|研究|调研)|分析一下|调研一下|招人情况|人才情况|就业情况|岗位需求|招聘需求',text)):
        return {'intent':'none'}
    missing=[]
    if region['status']=='missing':missing.append('地区（省或城市）')
    if not sectors:
        rest=re.sub(r'(?:只看|仅看|限定|筛选)[^\n，;；。]*','',text)
        rest=re.sub(r'用户补充(?:（[^）]*）)?[:：]?','',rest)
        for x in REGIONS:
            for alias in sorted({x['name'],*x.get('aliases',[])},key=len,reverse=True):rest=rest.replace(alias,'')
        for word in sorted(['微信公众号','人才需求观察报告','人才需求报告','人才需求','行业分析报告','产业分析报告','生成','制作','整理','分析','研究','调研','调查','观察','画像','概览','做份','报告','简报','研报','产业链','行业','产业','帮我','想要','我想','需要','一份','一篇','一版','一张','一个','这份','那份','给我','请','帮忙','麻烦','的','做','写','要','我','来','出'],key=len,reverse=True):rest=rest.replace(word,'')
        if not re.sub(r'[\s，。！？、：:,.!?]+','',rest):missing.append('产业，例如人工智能、机器人或半导体')
    if region['status'] in ('ambiguous','unsupported'):return {'intent':'report','status':region['status'],'message':region['message'],'text':text}
    if len(sectors)>1:return {'intent':'report','status':'ambiguous','message':'这次涉及多个产业，请先选一个产业，或明确要比较的范围。','text':text}
    return {'intent':'report','status':'clarify' if missing else 'ready','missing':missing,'region':region.get('region'),'industry':sectors[0] if sectors else None,'text':text}

def filter_intent_problems(filters,text):
    issues=[];full_scope=region_request(text)['status']=='ready';labels=[('博士','BOSHI'),('硕士','SHUOSHI'),('本科','BENKE'),('大专','DAZHUAN'),('高职','GAOZHI'),('中专','ZHONGZHUAN/ZHONGJI'),('高中','GAOZHONG'),('初中','CHUZHONGJIYIXIA')]
    mentioned=[code for label,code in labels if label in text]
    if full_scope and filters.get('education') and not mentioned and not re.search('学历不限|专科',text):issues.append('新增了未要求的学历筛选')
    if re.search('(?:只看|仅看|仅限|限定|筛选)(?:学历要求为|学历为|学历是)?(?:博士|硕士|本科|大专|高职|中专|高中|初中)|学历(?:为|是)(?:博士|硕士|本科|大专|高职|中专|高中|初中)',text) and len(mentioned)==1 and not re.search('以上|以下|至少',text) and sorted(filters.get('education',[]))!=sorted(mentioned):issues.append('学历筛选没有保留用户要求')
    if full_scope and filters.get('experience') and not re.search(r'(?:工作|从业|任职|经验).{0,10}[一二三四五六七八九十两0-9]+\s*年|[一二三四五六七八九十两0-9]+\s*年(?:以内|以下|以上|工作经验|相关经验|经验)|应届|在校|经验不限|无经验',text):issues.append('新增了未要求的工作年限筛选')
    if full_scope and filters.get('jobType') and not re.search('校招|社招|社会招聘|校园招聘|实习|兼职|全职',text):issues.append('新增了未要求的招聘类型筛选')
    return issues
