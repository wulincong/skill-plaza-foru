"""Prepare a small reproducible report workspace; never copy credentials or venv."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

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
    return {'status':'ready','directory':str(target),'newFiles':copied,
        'collect':f'cd {target} && node {BASE}/scripts/collect_data.mjs --plan plan.json',
        'analyze':f'{BASE}/.venv/bin/python {BASE}/scripts/report.py --workdir {target} analyze',
        'assemble':f'{BASE}/.venv/bin/python {BASE}/scripts/report.py --workdir {target} assemble report_writing.json',
        'build':f'{BASE}/.venv/bin/python {BASE}/scripts/report.py --workdir {target} build'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',default='.')
    parser.add_argument('--legacy-scripts',action='store_true')
    args=parser.parse_args()
    print(json.dumps(prepare(args.workspace,args.legacy_scripts),ensure_ascii=False))
