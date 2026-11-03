"""Trusted Pi entry point: initialize, analyze, assemble and build a report workspace."""
import argparse
import os
from pathlib import Path
import runpy
import sys

SCRIPTS=Path(__file__).resolve().parent
TASKS={'preflight':'report_preflight.py','analyze':'report_analysis.py','assemble':'report_analysis.py','build':'generate_report.py','check':'verify_data.py'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir',default='wechat-report')
    parser.add_argument('task',choices=['init','next','accept','revise',*TASKS])
    args,options=parser.parse_known_args()
    root=Path(args.workdir).resolve()
    if root==SCRIPTS.parent or root.is_relative_to(SCRIPTS.parent):raise ValueError('报告数据目录不能位于安装技能目录')
    if args.task=='init':
        if root.name!='wechat-report':raise ValueError('初始化目录应命名为wechat-report')
        from prepare_session import prepare
        import json
        print(json.dumps(prepare(root.parent),ensure_ascii=False));return
    if not root.is_dir() or not (root/'report_data.json').is_file():raise ValueError('请先初始化会话并通过共享工具完成取数')
    os.environ['WECHAT_REPORT_WORKDIR']=str(root)
    os.chdir(root)
    if args.task in ('next','accept','revise'):
        from writing_batches import next_task,accept_part,revise
        import json
        if args.task=='accept' and not options:raise ValueError('accept需要report_part.json')
        if args.task=='revise' and not options:raise ValueError('revise需要本轮修订标识')
        result=next_task() if args.task=='next' else revise(options[0]) if args.task=='revise' else accept_part(options[0])
        print(json.dumps(result,ensure_ascii=False));return
    if args.task=='assemble':
        if not options:raise ValueError('assemble需要已完成的report_writing.json')
        options=['--assemble',*options]
    if args.task=='build' and '--workspace' not in options:options=['--workspace',str(root.parent),*options]
    script=SCRIPTS/TASKS[args.task]
    sys.argv=[str(script),*options]
    runpy.run_path(str(script),run_name='__main__')


if __name__=='__main__':main()
