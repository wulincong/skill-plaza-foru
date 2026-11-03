"""Validate bound report data/claims; render checks are a separate final stage."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from bound_report import load_data, verify_outline, digest

BASE = Path(__file__).resolve().parent.parent
BANNED = r'可投递|增长最快|快速增长|增速|保持稳定|持续释放|招聘节奏|显著高于|远高于|溢价|样本代表性'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(BASE/'report_data.json'))
    ap.add_argument('--outline', default=str(BASE/'output/outline/report_outline.json'))
    ap.add_argument('--report-dir', default=str(BASE/'output/report'))
    ap.add_argument('--out', default=str(BASE/'output/verify_report.md'))
    ap.add_argument('--stage', choices=['data', 'final'], default='data')
    ap.add_argument('--theme', default='zhengwu')
    ap.add_argument('--demo', action='store_true')
    args = ap.parse_args()
    checks = []
    try:
        data, binding = load_data(args.data, args.demo)
        outline = json.loads(Path(args.outline).read_text('utf-8'))
        if binding:
            verify_outline(data, binding, outline)
        elif not outline.get('demo'):
            raise ValueError('离线样例大纲缺少演示标记')
        checks.append(('数据工件、适配和指标引用', True, '通过'))
        if binding:
            checks.append(('分析覆盖、比较证据与行动建议', True, '分析稿及报告正文一致；解释合理性仍需审阅'))
        for s in outline['screens']:
            visible = s.get('paragraphs', []) + [s.get('summary', {}).get('text', '')]
            if any(re.search(BANNED, t) for t in visible):
                raise ValueError('正文包含无证据支撑的动态或因果判断')
        checks.append(('文案证据边界', True, '通过'))
        from chart_recommender import check_chart_choice
        problems = []
        for i, s in enumerate(outline['screens']):
            for key in ('chart', 'chart2', 'chartA', 'chartB'):
                cfg = s.get(key)
                if not cfg:
                    continue
                for problem in check_chart_choice(cfg):
                    problems.append('第%d页 %s：%s' % (i+1, key, problem))
        if problems:
            raise ValueError('图表选型违规：'+'；'.join(problems))
        checks.append(('图表选型（FT 规则）', True, '通过'))
        if args.stage == 'final':
            manifest_path = Path(args.report_dir)/'manifest.json'
            manifest = json.loads(manifest_path.read_text('utf-8'))
            if manifest.get('outline_sha256') != digest(Path(args.outline).read_bytes()):
                raise ValueError('渲染产物来自其他大纲版本')
            if len(manifest.get('pages', [])) != len(outline['screens']):
                raise ValueError('渲染页数不完整')
            for page in manifest['pages']:
                if not (Path(args.report_dir)/page['file']).is_file():
                    raise ValueError('渲染图片缺失')
            cmd = [sys.executable, str(BASE/'scripts/render_check.py'), '--outline', args.outline,
                   '--report-dir', args.report_dir, '--theme', args.theme,
                   '--out', str(Path(args.out).with_suffix('.render.json'))]
            subprocess.run(cmd, check=True)
            checks.append(('实际渲染检查', True, '通过'))
        else:
            checks.append(('实际渲染检查', None, '待渲染后执行 --stage final'))
    except Exception as exc:
        checks.append(('验收', False, str(exc)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('# 报告验收\n\n'+'\n'.join('- %s：%s（%s）' % (name, 'PASS' if ok else 'PENDING' if ok is None else 'FAIL', msg) for name, ok, msg in checks), 'utf-8')
    print(out.read_text('utf-8'))
    return 1 if any(ok is False for _, ok, _ in checks) else 0


if __name__ == '__main__':
    raise SystemExit(main())
