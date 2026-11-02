"""Package public report artifacts; query evidence stays in output/internal."""
import argparse
import json
from pathlib import Path
import zipfile
from bound_report import load_data, verify_outline, digest
BASE = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(BASE/'report_data.json'))
    ap.add_argument('--outline', default=str(BASE/'output/outline/report_outline.json'))
    ap.add_argument('--report-dir', default=str(BASE/'output/report'))
    ap.add_argument('--name', default='人才需求观察报告_交付包')
    args = ap.parse_args()
    if Path(args.name).name != args.name:
        raise ValueError('交付包名称不能包含路径')
    data, binding = load_data(args.data)
    outline_path = Path(args.outline)
    outline = json.loads(outline_path.read_text('utf-8'))
    verify_outline(data, binding, outline)
    report = Path(args.report_dir).resolve()
    manifest = json.loads((report/'manifest.json').read_text('utf-8'))
    if manifest.get('outline_sha256') != digest(outline_path.read_bytes()) or len(manifest['pages']) != len(outline['screens']):
        raise ValueError('图片清单与当前大纲不一致')
    files = []
    for page in manifest['pages']:
        source = (report/page['file']).resolve()
        if not source.is_relative_to(report) or not source.is_file():
            raise ValueError('清单图片缺失或路径无效')
        files.append(('report/'+page['file'], source))
    for name in ['report_full.jpg', 'manifest.json']:
        if (report/name).is_file():
            files.append(('report/'+name, report/name))
    for name in ['article.md', 'article.html']:
        source = report.parent/'article'/name
        if source.is_file():
            files.append(('article/'+name, source))
    data.pop('provenance', None)
    outline.pop('bindings', None)
    out = report.parent/(args.name+'.zip')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, source in files:
            z.write(source, args.name+'/'+name)
        z.writestr(args.name+'/report_data.json', json.dumps(data, ensure_ascii=False, indent=2))
        z.writestr(args.name+'/outline/report_outline.json', json.dumps(outline, ensure_ascii=False, indent=2))
    print(str(out))


if __name__ == '__main__':
    main()
