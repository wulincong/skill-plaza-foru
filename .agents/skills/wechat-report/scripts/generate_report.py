"""Pi's non-interactive build entry: saved data + agent analysis -> checked images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone
from time import perf_counter

from report_runtime import report_root
BASE = report_root(__file__)
SCRIPTS = Path(__file__).resolve().parent
PIPELINE_FILES=['gen_outline.py','verify_data.py','render_report.py','render_check.py',
    'chart_layout.py','chart_recommender.py','report_charts.py','chart_semantics.py',
    'browser_renderer.py','bound_report.py','report_analysis.py','build_article.py',
    'evidence_sheet.py','pack_delivery.py','generate_report.py','adapt_query_result.mjs','collect_data.mjs','refresh_policy.mjs','prepare_session.py',
    'joint_report_charts.py','joint_chart_layout.py','joint_findings.py','executive_analysis.py',
    'deep_outline.py','report_references.py','report_runtime.py','report.py','analysis_quality.py','article_content.py','writing_batches.py','report_preflight.py','analytical_reasoning.py','regional_reasoning.py','editorial_prose.py','editorial_projects.py','regional_research.py','../assets/regional_sources.json','../assets/official_context.json']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', default=str(BASE))
    parser.add_argument('--theme', default='zhengwu')
    args = parser.parse_args()
    steps = [('gen_outline.py', []), ('verify_data.py', ['--stage','data']),
             ('render_report.py', ['--theme',args.theme,'--no-stitch']),
             ('verify_data.py', ['--stage','final','--theme',args.theme]),
             ('build_article.py', []), ('evidence_sheet.py', []),
             ('pack_delivery.py', ['--workspace',str(Path(args.workspace).resolve())])]
    if (BASE/'report_writing.json').exists():steps.insert(0,('report_analysis.py',['--assemble',str(BASE/'report_writing.json')]))
    if 'city_profiles' in json.loads((BASE/'report_data.json').read_text('utf-8')):steps.insert(0,('report_preflight.py',[]))
    # A failed revision must not leave an old declaration looking like the new result.
    declaration = Path(args.workspace).resolve()/'delivery.json'
    declaration.unlink(missing_ok=True)
    receipt=BASE/'output/report/build_receipt.json'
    receipt.unlink(missing_ok=True)
    started=datetime.now(timezone.utc).isoformat()
    pipeline={name:sha(SCRIPTS/name) for name in PIPELINE_FILES}
    stages=[]
    for name, options in steps:
        timer=perf_counter()
        subprocess.run([sys.executable, str(SCRIPTS/name), *options], cwd=BASE, check=True)
        stages.append({'script':name,'durationMs':round((perf_counter()-timer)*1000),'exitCode':0})
    if pipeline!={name:sha(SCRIPTS/name) for name in PIPELINE_FILES}:
        declaration.unlink(missing_ok=True)
        raise RuntimeError('生成期间程序版本改变，已停止交付，请沿用数据重试')
    payload={'schema':'wechat-build/1','startedAt':started,'finishedAt':datetime.now(timezone.utc).isoformat(),
        'stages':stages,'pipelineFiles':pipeline,
        'reportDataSha256':sha(BASE/'report_data.json'),'analysisSha256':sha(BASE/'report_analysis.json'),
        'outlineSha256':sha(BASE/'output/outline/report_outline.json'),
        'manifestSha256':sha(BASE/'output/report/manifest.json'),
        'deliveryManifest':json.loads(declaration.read_text('utf-8'))}
    temporary=receipt.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
    os.replace(temporary,receipt)
    print('报告图片已生成并通过程序检查，请审核最终成品。')


if __name__ == '__main__':
    main()
