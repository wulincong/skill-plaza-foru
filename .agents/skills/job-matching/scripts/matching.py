"""Read-only job candidates and evidence-checked matching report."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import uuid
import unicodedata
import zipfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DICTIONARIES = json.loads((ROOT/'references/dictionaries.json').read_text())
ENDPOINT = 'https://job.foru-ai.com/api/business/front/lookForWork/queryListForPage'
FIELDS = {'industry':'INDUSTRY','education':'EDUCATION','salary':'SALARY','experience':'EXPERIENCE','positionType':'POSITION_TYPE'}
WEIGHTS = {'skills':40,'experience':30,'direction':20,'preferences':10}


def require(condition, message):
    if not condition: raise ValueError(message)


def post(body):
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw=response.read(8*1024*1024+1)
    require(len(raw)<=8*1024*1024,'岗位响应过大')
    return json.loads(raw)


def query_jobs(filters, request=post):
    require(isinstance(filters,dict),'查询参数无效')
    require(not (set(filters)-set(FIELDS)-{'keyword','city','district'}),'不支持的筛选字段')
    require(isinstance(filters.get('keyword'),str) and 0<len(filters['keyword'].strip())<=100,'请提供keyword')
    if 'city' in filters:
        require(isinstance(filters['city'],str) and len(filters['city'].strip())<=100,'城市参数无效')
        filters={k:v for k,v in filters.items() if k!='city' or v.strip()}
    for key, dictionary in FIELDS.items():
        if key in filters: require(filters[key] in DICTIONARIES[dictionary],f'{key}字典Key无效')
    if 'district' in filters:require(isinstance(filters['district'],str) and len(filters['district'])<=100,'区县无效')
    rows, seen, current, total = [], set(), 1, 0
    warning=''
    while len(rows)<100:
        response=request({'size':100,'current':current,'model':filters})
        require(isinstance(response,dict) and response.get('code')==0 and response.get('isSuccess') is not False,'岗位接口未成功，不能视为无岗位')
        data=response.get('data'); require(isinstance(data,dict) and isinstance(data.get('records'),list),'岗位返回格式无效')
        require(type(data.get('total')) is int and data['total']>=0,'岗位总数无效')
        total=data['total']; batch=data['records']; added=0
        if data.get('current') is not None:require(data['current']==current,'岗位接口未正确翻页')
        for row in batch:
            require(isinstance(row,dict) and isinstance(row.get('positionId'),(str,int)),'岗位ID无效')
            identifier=str(row['positionId'])
            require(re.fullmatch(r'[0-9]{1,32}',identifier) is not None,'岗位ID格式无效')
            if identifier in seen:continue
            seen.add(identifier);added+=1
            item={key:row.get(key) for key in ('positionName','positionDescription','companyName','city','district','minSalary','maxSalary','industry','education','experience','positionType')}
            require(isinstance(item['positionName'],str) and isinstance(item['positionDescription'],str),'岗位缺少名称或JD')
            item['positionId']=identifier
            item['url']='https://job.foru-ai.com/#/station/detail/'+identifier
            rows.append(item)
            if len(rows)==100:break
        pages=data.get('pages')
        if not batch or len(rows)>=total or (type(pages) is int and current>=pages):break
        if not added:warning='接口分页出现重复，本次候选未覆盖全部结果';break
        current+=1
        require(current<=100,'岗位分页异常')
    return {'records':rows,'total':total,'candidateCount':len(rows),'filters':filters,'warning':warning,'retrievedAt':datetime.now(timezone.utc).isoformat(),'endpoint':ENDPOINT}


def score(assessment):
    values=[assessment.get(k) for k in WEIGHTS]
    require(all(v is None or (type(v) is int and 0<=v<=4) for v in values),'匹配等级必须为0–4或null')
    return None if any(v is None for v in values) else round(sum(assessment[k]/4*w for k,w in WEIGHTS.items()))


def extract_resume(workspace, request, context):
    value=request.get('resumeText','')
    file=request.get('resumePath')
    if not value and not file:
        for message in reversed(context.get('messages',[])):
            if not isinstance(message,str):continue
            match=re.search(r'(?:简历摘要|匿名经历摘要)[:：]\s*([^\n]+)',message)
            if match:
                value=match.group(1).strip();break
        if not value and len(context.get('uploads',[]))==1:file=context['uploads'][0]
    if value:
        require(isinstance(value,str) and any(value in message for message in context.get('messages',[]) if isinstance(message,str)),'简历摘要必须来自用户原话')
    if file:
        allowed=context.get('uploads',[])
        require(file in allowed,'简历文件不是用户上传的附件')
        path=(workspace/file).resolve()
        require(path.is_relative_to(workspace/'uploads') and path.is_file(),'简历必须来自uploads')
        if path.suffix.lower() in ('.txt','.md'):value=path.read_text()
        elif path.suffix.lower()=='.docx':
            with zipfile.ZipFile(path) as z:
                require(z.getinfo('word/document.xml').file_size<=5*1024*1024,'简历正文过大')
                xml=z.read('word/document.xml')
                require(len(xml)<=5*1024*1024,'简历正文过大')
                tree=ElementTree.fromstring(xml)
                value='\n'.join(''.join(p.itertext()) for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
        elif path.suffix.lower()=='.pdf':
            result=subprocess.run(['pdftotext','-layout',str(path),'-'],capture_output=True,text=True,timeout=30,check=True)
            value=result.stdout
            require(bool(value.strip()),'简历没有可提取文字，请提供文字版')
        else:raise ValueError('请使用PDF、DOCX、TXT或Markdown简历')
    require(isinstance(value,str) and len(value)<=60000,'简历内容无效或过长')
    return value


def escaped(value):
    return re.sub(r'([\\`*_{}\[\]<>|])',r'\\\1',str(value)).replace('\n',' ')


def label(value):
    return value.get('data') or value.get('key') or '未说明' if isinstance(value,dict) else value or '未说明'


def source_quote(quote, source):
    # Preserve original wording while tolerating whitespace and full-width punctuation.
    def normalized(value):
        text=[];offsets=[]
        for index,char in enumerate(value):
            for item in unicodedata.normalize('NFKC',char):
                if not item.isspace():text.append(item);offsets.append(index)
        return ''.join(text),offsets
    needle,_=normalized(quote);haystack,offsets=normalized(source)
    index=haystack.find(needle)
    require(bool(needle) and index>=0,'引文必须来自对应原文，建议只摘录一条简短要求')
    return source[offsets[index]:offsets[index+len(needle)-1]+1]


def redact_public(value, resume):
    if isinstance(value, list):return [redact_public(x,resume) for x in value]
    if isinstance(value, dict):return {k:redact_public(v,resume) for k,v in value.items()}
    if not isinstance(value,str):return value
    for address in re.findall(r'(?:家庭住址|现居住址|联系地址|住址)[:：]([^\n]{1,150})',resume):
        value=value.replace(address,'[地址已隐藏]')
    value=re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[邮箱已隐藏]', value)
    return re.sub(r'(?<![0-9])1[3-9][0-9]{9}(?![0-9])', '[电话已隐藏]', value)


def validate_source(data,source,context,state):
    require(source.get('runId')==context.get('runId') and state.get('runId')==context.get('runId'),'候选不属于本轮，请按当前条件重新查询')
    require(state.get('status') in ('ok','empty'),'本轮岗位查询失败，不能使用旧结果')
    require(state.get('snapshot')==data['snapshot'] and state.get('sha256')==data['sha256'],'评估必须使用工具返回的候选来源')


def build_page(plan, source):
    require(isinstance(plan.get('summary'),str) and plan['summary'].strip(),'缺少匹配结论')
    records={row['positionId']:row for row in source['records']}
    assessments=plan.get('assessments',[])
    require(isinstance(assessments,list),'缺少候选评估')
    ids=[a.get('id') for a in assessments]
    require(len(ids)==len(set(ids)) and set(ids)==set(records),'必须评估本次全部候选且不得引用库外岗位')
    resume=source.get('resume','')
    ranked=[]
    for a in assessments:
        require(a.get('eligibility') in ('pass','review','exclude'),'资格状态无效')
        require(isinstance(a.get('reason'),str) and bool(a['reason'].strip()),'缺少匹配或排除理由')
        value=score(a)
        if not resume:require(value is None,'无简历时不能生成完整人岗匹配分')
        if a['eligibility']!='exclude':ranked.append((a,value))
    ranked.sort(key=lambda row:(row[0]['eligibility']!='pass',-(row[1] if row[1] is not None else -1),row[0]['id']))
    ranked=ranked[:20]
    details=plan.get('details',[])
    require(isinstance(details,list),'推荐说明无效')
    detailed={a['id']:a for a in details}
    require(len(detailed)==len(details) and set(detailed)=={a['id'] for a,_ in ranked},'详细分析必须对应程序排序后的最多20个岗位')
    blocks=[{'type':'summary','lead':'为你推荐的岗位与投递顺序','text':plan['summary']}]
    if source.get('warning'):
        blocks.append({'type':'callout','text':'部分岗位资料未能完整核实，推荐仅适用于已核对的岗位。'})
    if ranked:
        blocks.append({'type':'metrics','items':[
            {'label':'推荐岗位','value':len(ranked),'unit':'个'},
            {'label':'可优先考虑','value':sum(a['eligibility']=='pass' for a,_ in ranked),'unit':'个'},
            {'label':'资格待核验','value':sum(a['eligibility']=='review' for a,_ in ranked),'unit':'个'},
        ]})
        comparison=[]
        for index,(a,value) in enumerate(ranked,1):
            dimensions=[round(a[k]/4*weight,1) if a.get(k) is not None else '未评估' for k,weight in WEIGHTS.items()]
            comparison.append([index,records[a['id']]['positionName'],*dimensions,value if value is not None else '未评估',f"{sum(a.get(k) is not None for k in WEIGHTS)}/4"])
        blocks.append({'type':'section','title':'岗位量化对比' if len(ranked)>1 else '岗位匹配指标','blocks':[
            {'type':'table','columns':[{'label':label,'numeric':i!=1} for i,label in enumerate(('排序','岗位','技能（40分）','经历（30分）','岗位方向（20分）','求职偏好（10分）','综合（100分）','已评估维度'))],'rows':comparison,
             'note':'各维度为有依据的匹配等级按权重换算的分值，不代表录用概率。未评估维度不补零，综合分留空为未评估。'}]})
    table=[];sections=[]
    for index,(a,value) in enumerate(ranked,1):
        row=records[a['id']];detail=detailed[a['id']]
        evidence=detail.get('evidence',[])
        require(isinstance(evidence,list) and bool(evidence),'每个推荐岗位必须有JD依据')
        evidence_text=[]
        for item in evidence:
            jd=item.get('jd','');quote=item.get('resume','')
            require(isinstance(jd,str) and 0<len(jd.strip())<=300,'JD引文应为不超过300字的一条具体要求')
            jd=source_quote(jd,row['positionDescription'])
            require(isinstance(quote,str) and len(quote)<=300,'简历引文必须为不超过300字的相关摘录')
            if quote:quote=source_quote(quote,resume)
            require(item.get('status') in ('已证明','部分证明','存在差距','信息不足'),'证据状态无效')
            if not quote:require(item['status'] in ('存在差距','信息不足'),'没有简历证据不能声称已证明')
            evidence_text.append(f"- **{item['status']}**：岗位要求“{escaped(jd)}”。"+(f"你的经历：“{escaped(quote)}”。" if quote else '简历未提供对应证据。'))
        for key in ('gaps','advice'):
            require(isinstance(detail.get(key),str) and bool(detail[key].strip()),'缺少能力差距或求职建议')
        salary=f"{row.get('minSalary') or '?'}–{row.get('maxSalary') or '?'} K/月"
        grade=f'{value}/100' if value is not None else '未评估完整分'
        table.append([index,row['positionName'],row.get('companyName') or '未说明',row.get('city') or '未说明',salary,grade,'优先核验' if a['eligibility']=='review' else '可优先考虑'])
        sections.append({'type':'section','title':f"{index}. {row['positionName']} · {row.get('companyName') or '公司未说明'}",'blocks':[
          {'type':'text','text':f"[{escaped('查看岗位原文')}]({row['url']}) · {salary} · 学历：{escaped(label(row.get('education')))} · 经验：{escaped(label(row.get('experience')))} · 性质：{escaped(label(row.get('positionType')))}"},
          {'type':'text','text':a['reason']}, {'type':'text','text':'\n'.join(evidence_text)},
          {'type':'text','text':'能力差距与待确认：'+detail['gaps']}, {'type':'text','text':'求职建议：'+detail['advice']}]})
    blocks.append({'type':'section','title':'推荐岗位清单','blocks':[{'type':'table','columns':[{'label':x} for x in ('排序','岗位','公司','城市','薪资','匹配度','建议')],'rows':table}] if table else [{'type':'text','text':'本次没有符合条件的可推荐岗位。请选择是否调整城市、岗位或其他筛选条件，不自动放宽。'}]})
    blocks.extend(sections)
    excluded=[a for a in assessments if a['eligibility']=='exclude']
    if excluded:blocks.append({'type':'section','title':'未推荐岗位的主要原因','blocks':[{'type':'text','text':'\n'.join('- '+escaped(records[a['id']]['positionName'])+'：'+a['reason'] for a in excluded[:10])}]})
    blocks.append({'type':'section','title':'匹配方法与适用范围','blocks':[{'type':'text','text':'技能40%、经历30%、岗位方向20%、求职偏好10%，每项按0–4级依据评分。任何一项信息不足则不输出完整总分，不把未知视为零分。先按资格条件核验，再按匹配度排序；待确认岗位单列标识。匹配判断来自JD与实际简历证据，分数不代表录用概率。薪资单位按招聘网站显示K/月，奖金、薪数及实习结算方式需向企业核实。岗位有效性以招聘页面和企业确认为准。'}]})
    return redact_public({'title':'岗位智能匹配报告','theme':'minimal','blocks':blocks,'footer':f"职位来源：优才知路招聘平台 · 资料日期：{source['retrievedAt'][:10]}。仅展示与岗位匹配有关的经历摘录，分享前请确认内容适合公开。"},resume)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['query','build','preview'])
    parser.add_argument('input',type=Path)
    args=parser.parse_args();input_file=args.input.resolve()
    workspace=Path.cwd().resolve() if args.operation=='query' else input_file.parent
    require(not workspace.is_relative_to(ROOT.parent),'不能把技能安装目录作为工作区')
    try:
        data=json.loads(input_file.read_text())
        if args.operation=='query':
            context=json.loads((workspace/'.job-request.json').read_text())
            resume=extract_resume(workspace,data,context)
            source=query_jobs(data['filters']);source['resume']=resume;source['runId']=context['runId']
            identifier=uuid.uuid4().hex
            directory=workspace/'.job-matching';directory.mkdir(exist_ok=True)
            path=directory/(identifier+'.json');path.write_text(json.dumps(source,ensure_ascii=False))
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            result={k:source[k] for k in ('total','candidateCount','filters','warning','retrievedAt')}
            result.update(status='ok' if source['records'] else 'empty',snapshot=str(path.relative_to(workspace)),sha256=digest,resume=resume,candidates=source['records'])
            print(json.dumps(result,ensure_ascii=False))
        else:
            path=(workspace/data['snapshot']).resolve()
            require(path.is_relative_to(workspace/'.job-matching') and path.suffix=='.json','候选来源路径无效')
            require(hashlib.sha256(path.read_bytes()).hexdigest()==data['sha256'],'候选来源已改变')
            source=json.loads(path.read_text())
            context=json.loads((workspace/'.job-request.json').read_text())
            state=json.loads((workspace/'.job-query-state.json').read_text())
            validate_source(data,source,context,state)
            # preview computes authoritative ranking before writing the 20 detailed recommendations.
            if args.operation=='preview':
                records={r['positionId'] for r in source['records']}
                ids=[a.get('id') for a in data['assessments']]
                require(set(ids)==records and len(ids)==len(set(ids)),'必须评估全部候选')
                ranked=[dict(a,score=score(a)) for a in data['assessments'] if a['eligibility']!='exclude']
                ranked.sort(key=lambda a:(a['eligibility']!='pass',-(a['score'] if a['score'] is not None else -1),a['id']))
                print(json.dumps({'status':'ok','ranking':ranked[:20]},ensure_ascii=False));return 0
            page=build_page(data,source)
            model=workspace/'job-page.json';model.write_text(json.dumps(page,ensure_ascii=False))
            rendering=ROOT.parent/'report-rendering/scripts'
            out=workspace/'output/public'/('jobs-'+uuid.uuid4().hex[:12])
            subprocess.run([sys.executable,str(rendering/'render.py'),str(model),'--out',str(out)],check=True,cwd=workspace)
            subprocess.run([sys.executable,str(rendering/'register_delivery.py'),str(out),'--name','岗位匹配报告'],check=True,cwd=workspace)
            print(json.dumps({'status':'ok','directory':str(out.relative_to(workspace))}))
    except Exception as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False));return 1
    return 0

if __name__=='__main__':sys.exit(main())
