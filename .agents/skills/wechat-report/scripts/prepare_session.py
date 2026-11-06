"""Prepare a small reproducible report workspace; never copy credentials or venv."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from report_request import region_request

BASE=Path(__file__).resolve().parent.parent
ASSETS=['brand.json','themes.json','curriculum_map.json','echarts.min.js','official_context.json']


def prepare(workspace,legacy_scripts=False):
    root=Path(workspace).resolve();target=root/'wechat-report'
    if target==BASE or target.is_relative_to(BASE):raise ValueError('请在会话工作区调用，不能写入安装目录')
    target.mkdir(parents=True,exist_ok=True)
    copied=0
    for name in ['scripts','references'] if legacy_scripts else []:
        (target/name).mkdir(exist_ok=True)
        for source in (BASE/name).rglob('*'):
            if '__pycache__' in source.parts:continue
            destination=target/name/source.relative_to(BASE/name)
            if source.is_dir():destination.mkdir(exist_ok=True)
            elif source.is_file() and not destination.exists():
                shutil.copyfile(source,destination);copied+=1
    (target/'assets').mkdir(exist_ok=True)
    for name in ASSETS:
        destination=target/'assets'/name
        if not destination.exists():shutil.copyfile(BASE/'assets'/name,destination);copied+=1
    turn={}
    if (root/'report-turn.json').exists():turn=json.loads((root/'report-turn.json').read_text())
    requested=region_request(turn.get('requestText',''))
    if requested['status']=='missing':requested=region_request(turn.get('originRequestText',''))
    text=turn.get('requestText','') or turn.get('originRequestText','')
    import re
    education=[]
    if re.search('只看|仅看|仅限|限定|筛选|学历为|学历是',text) and not re.search('以上|以下|至少',text):
        education=[code for name,code in [('大专','DAZHUAN'),('本科','BENKE'),('硕士','SHUOSHI'),('博士','BOSHI'),('高职','GAOZHI'),('中专','ZHONGZHUAN/ZHONGJI')] if name in text]
    region=requested.get('region',{'level':'REQUIRED','name':'用户尚未指定地区，请先询问，不得默认省份'})
    return {'status':'ready','directory':str(target),'newFiles':copied,
        'collect':f'cd {target} && node {BASE}/scripts/collect_data.mjs --plan plan.json',
        'planTemplate':{'schema':'wechat-report-plan/1','filters':{'region':region,'industries':[{'id':'替换为resolve返回的唯一根节点字符串ID','includeDescendants':True}],**({'education':education} if education else {})}},
        'planNotes':'filters.region是对象；industries是对象数组，id使用resolve返回的字符串。保留用户其他筛选。未要求的学历、工作年限、招聘类型不得添加筛选；分析这些维度并不等于限制这些维度。profile是collect_data.mjs命令行参数，不是plan字段。不要直接运行未替换的模板。',
        'allowedPlanFields':['schema','filters','sections','analysis','audience','industryLabel','execution'],
        'profiles':list(json.loads((BASE/'assets/industry_profiles.json').read_text('utf-8'))['profiles']),
        'profileUsage':'已声明产业可在collect命令末尾加 --profile 对应产业名；使用profile时plan只写schema、filters及必要的execution，不再另填analysis；只补分析规则，不替换用户产业或范围。未声明产业显式设置analysis及章节，不能套用其他产业规则。',
        'analyze':f'{BASE}/.venv/bin/python {BASE}/scripts/report.py --workdir {target} analyze',
        'assemble':f'{BASE}/.venv/bin/python {BASE}/scripts/report.py --workdir {target} assemble report_writing.json',
        'build':f'{BASE}/.venv/bin/python {BASE}/scripts/report.py --workdir {target} build'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',default='.')
    parser.add_argument('--legacy-scripts',action='store_true')
    args=parser.parse_args()
    print(json.dumps(prepare(args.workspace,args.legacy_scripts),ensure_ascii=False))
