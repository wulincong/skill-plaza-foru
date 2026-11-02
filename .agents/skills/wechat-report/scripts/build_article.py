"""Build article text from the same validated outline; never queries data."""
import argparse
import html
import json
import os
from pathlib import Path
from bound_report import load_data, verify_outline, digest

BASE = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(BASE/'report_data.json'))
    ap.add_argument('--outline', default=str(BASE/'output/outline/report_outline.json'))
    ap.add_argument('--report-dir', default=str(BASE/'output/report'))
    ap.add_argument('--out', default=str(BASE/'output/article'))
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--style', choices=['data', 'voc', 'scene'], default='data')
    args = ap.parse_args()
    data, binding = load_data(args.data, args.demo)
    outline = json.loads(Path(args.outline).read_text('utf-8'))
    if binding:
        verify_outline(data, binding, outline)
    manifest = json.loads((Path(args.report_dir)/'manifest.json').read_text('utf-8'))
    if manifest.get('outline_sha256') != digest(Path(args.outline).read_bytes()):
        raise ValueError('图片来自其他大纲版本')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md, blocks = ['# '+outline['title'], ''], ['<h1>'+html.escape(outline['title'])+'</h1>']
    intro = {'data': '从平台在招岗位记录观察地域、门槛与能力要求，以下分析与图文采用同一份统计结果。',
             'voc': '从专业定位、实训项目和校企合作出发，结合招聘条件识别人才培养的对接方向。',
             'scene': '将研究视角放到目标地区的岗位职责与招聘条件，观察企业用人和人才培养的连接点。'}[args.style]
    md += [intro, '']
    blocks.append('<p>'+intro+'</p>')
    for i, s in enumerate(outline['screens']):
        md += ['## '+s['title'], '']
        blocks.append('<h2>'+html.escape(s['title'])+'</h2>')
        for p in s.get('paragraphs', []):
            md += [p, '']
            blocks.append('<p>'+p+'</p>')
        if s.get('summary'):
            text = s['summary']['text']
            md += [text, '']
            blocks.append('<p>'+html.escape(text)+'</p>')
        if i < len(manifest['pages']):
            image = (Path(args.report_dir)/manifest['pages'][i]['file']).resolve()
            if not image.is_file():
                raise ValueError('图片缺失')
            rel = os.path.relpath(image, out)
            md += ['!['+s['title']+']('+rel+')', '']
            blocks.append('<img alt=\"'+html.escape(s['title'], quote=True)+'\" src=\"'+html.escape(rel, quote=True)+'\">')
    (out/'article.md').write_text('\n'.join(md), 'utf-8')
    (out/'article.html').write_text('<!doctype html><meta charset=\"utf-8\"><article>'+''.join(blocks)+'</article>', 'utf-8')
    print(str(out))


if __name__ == '__main__':
    main()
