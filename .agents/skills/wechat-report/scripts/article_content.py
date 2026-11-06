"""Short evidence-bound introduction, shared by preview and real drafts."""
import hashlib
import html
import json
from pathlib import Path
import re

POLICY='wechat-article-lead/2'
GUIDE=Path(__file__).resolve().parent.parent/'references/article-styles.md'

def style_guide():
    raw=GUIDE.read_bytes()
    match=re.search(r'```json\s*(\{.*?\})\s*```',raw.decode('utf-8'),re.S)
    if not match:raise ValueError('公众号开篇参考缺少可执行样式规则')
    guide=json.loads(match[1])
    if guide.get('schema')!='wechat-article-styles/1':raise ValueError('公众号开篇参考版本错误')
    return guide,hashlib.sha256(raw).hexdigest()

def first_sentences(text,limit=120):
    result=''
    for sentence in re.findall(r'[^。！？]+[。！？]?',text):
        if result and len(result)+len(sentence)>limit:break
        result+=sentence
    return result.strip()

def build_lead(data,analysis,style=None):
    from editorial_prose import number,percent,ordered_cities,ordered_tracks,scope_label
    from report_analysis import derive_findings
    guide,guide_hash=style_guide();meta=data['meta'];total=data['total']
    values={'region':meta['region'],'industry':meta['industry'],'positions':number(total['positions']),
            'companies':number(total.get('companies',0))}
    eligible=guide['defaultStyles']
    selected=style or eligible[int(hashlib.sha256((values['region']+values['industry']).encode()).hexdigest()[:8],16)%len(eligible)]
    if selected not in guide['styles']:raise ValueError('未知公众号开篇样式')
    settings=guide['styles'][selected]
    cities=ordered_cities(data);tracks=ordered_tracks(data);signals=[]
    if len(cities)>=2:
        cities_text='、'.join(row['name'] for row in cities[:2])
        signals.append({'title':'机会集中，选择仍需细分','text':cities_text+'合计占本次岗位样本'+percent(sum(row['count'] for row in cities[:2]),total['positions'])+'%。城市排名帮助定位机会，方向与申请条件则帮助缩小清单，地域规模与个人选择需要分开判断。'})
    else:
        signals.append({'title':'从产业名称走向具体岗位','text':values['region']+'的'+values['positions']+'条岗位记录，连接着不同职责与申请条件。先明确希望从事的工作，再阅读条件和能力要求，产业观察才更容易落到具体选择。'})
    salary=data.get('salary') or {};entry=(data.get('voc_pool') or {}).get('salary') or {}
    if salary.get('median') is not None:
        text='总体有效报价的中位数为'+number(salary['median'])+'K/月'
        if entry.get('valid',0)>=30 and entry.get('median') is not None:text+='，入门条件样本为'+number(entry['median'])+'K/月'
        signals.append({'title':'谈薪酬，先找相近的岗位','text':text+'。同一产业里的报价还受岗位组合影响，阅读薪酬时应把职责与申请条件放在一起，不用统一的行业印象代替具体参照。'})
    else:signals.append({'title':'把条件与职责放在一起看','text':'岗位入口由学历、经验和职责共同界定。报告保留原定范围，帮助读者在有依据的岗位组之间比较，不以其他人群的数据替代当前对象。'})
    if len(tracks)>=2:
        text=tracks[0]['name']+'与'+tracks[1]['name']+'位于本次已识别方向前列。'
        text+='把工作任务、工具和进入条件连起来看，更容易发现共同基础与方向差别，为求职准备、课程设计或企业合作提供具体切入点。'
    else:text='岗位条件与能力要求需要对应到工作任务。报告从可以观察的岗位组出发，把产业概念拆成更具体的工作路径，帮助读者选择接下来要深入研究的问题。'
    signals.append({'title':'同一产业，不止一条工作路径','text':text})
    return {'policy':POLICY,'style':selected,'styleLabel':settings['label'],'reference':'references/article-styles.md',
       'referenceSha256':guide_hash,'eyebrow':'产业观察 · 人才需求',
       'hook':settings['hook'].format(**values),'opening':(('本次报告限定'+scope_label(data)+'，以下岗位量、份额和薪酬均在该范围内比较。') if scope_label(data) else '')+settings['opening'].format(**values),
       'signals':signals,'value':'这份报告将招聘格局、岗位方向、学历经验和薪酬放在一起看，帮助读者辨认本地机会、比较岗位条件，并找到人才培养与企业需求的连接点。',
       'guide':'下滑查看完整图片报告：先看摘要和招聘格局，再读岗位门槛、薪酬与交叉分析。',
       'source':'数据来源：优才知路平台数据库。数据读取日期：'+meta['generated_at'][:10]+'。统计范围与研究边界见报告末页。'}

def lead_for(report):
    lead=report.get('articleLead')
    if lead and lead.get('policy')==POLICY:return lead
    return {'eyebrow':'产业观察 · 人才需求','hook':report.get('region','')+report.get('industry','')+'：岗位机会与进入条件',
       'opening':'从招聘格局、岗位结构和薪酬条件，观察本地产业的人才需求。',
       'signals':[], 'value':'以下为完整图片报告，可按章节查看相关数据与分析。',
       'guide':'完整图片报告如下。','source':'数据来源：优才知路平台数据库。研究范围与参考资料见报告。'}

def prose_blocks(report):
    lead=lead_for(report)
    yield 'heading',lead['hook'];yield 'paragraph',lead['opening']
    for row in lead['signals']:
        yield 'subheading',row['title'];yield 'paragraph',row['text']
    for key in ('value','guide','source'):yield 'paragraph',lead[key]

def html_prose(report):
    lead=lead_for(report);esc=lambda value:html.escape(value,quote=True)
    pieces=['<section style="padding:8px 12px 28px;font-size:16px;line-height:1.85;letter-spacing:.4px;color:#334155;overflow-wrap:break-word">',
      '<p style="font-size:12px;letter-spacing:2px;color:#64748b;margin:8px 0 16px">'+esc(lead['eyebrow'])+'</p>',
      '<h2 style="font-size:23px;line-height:1.5;color:#163668;margin:0 0 18px;font-weight:700">'+esc(lead['hook'])+'</h2>',
      '<p style="margin:0 0 24px">'+esc(lead['opening'])+'</p>',
      '<p style="font-size:13px;color:#d27725;letter-spacing:2px;margin:0 0 16px">值得关注的三个信号</p>' if lead['signals'] else '']
    for index,row in enumerate(lead['signals']):
        pieces.extend(['<section style="border-left:3px solid #d78a35;padding:2px 0 2px 14px;margin:0 0 22px">',
          '<h3 style="font-size:17px;line-height:1.65;margin:0 0 8px;color:#163668">'+str(index+1).zfill(2)+' / '+esc(row['title'])+'</h3>',
          '<p style="margin:0">'+esc(row['text'])+'</p></section>'])
    pieces.extend(['<p style="padding:16px 18px;background:#f3f6fa;border-radius:8px;margin:28px 0 20px">'+esc(lead['value'])+'</p>',
      '<p style="font-size:14px;color:#475569;margin:20px 0 10px">'+esc(lead['guide'])+'</p>',
      '<p style="font-size:12px;line-height:1.8;color:#94a3b8;margin:0 0 22px">'+esc(lead['source'])+'</p>',
      '<p style="text-align:center;letter-spacing:3px;font-size:12px;color:#94a3b8;margin:24px 0 0">— 完整报告 —</p></section>'])
    return ''.join(pieces)

def card_fields(report,url):
    from urllib.parse import urljoin
    from editorial_prose import scope_label
    title=report['region']+report['industry']+'产业人才需求报告'
    lead=lead_for(report)
    description=f"{report.get('positions',0):,}条岗位｜{report.get('companies',0):,}家企业。招聘格局、岗位门槛与薪酬分析。"
    if scope_label(report):description=f"{report.get('positions',0):,}条岗位｜{report.get('companies',0):,}家企业。筛选：{scope_label(report)}。"
    while len(description.encode())>120:description=description[:-1]
    return {'title':title,'description':description,'url':url,'imageUrl':urljoin(url,'assets/share-cover.png')}
