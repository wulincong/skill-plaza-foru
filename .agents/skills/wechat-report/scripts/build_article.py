"""Private draft article: all verified visible prose first, then all ordered images."""
import argparse
import html
import json
import os
from pathlib import Path
from bound_report import load_data,verify_outline,digest
from report_runtime import report_root
from article_content import html_prose,prose_blocks

BASE=report_root(__file__)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default=str(BASE/'report_data.json'))
    parser.add_argument('--outline',default=str(BASE/'output/outline/report_outline.json'))
    parser.add_argument('--report-dir',default=str(BASE/'output/report'))
    parser.add_argument('--out',default=str(BASE/'output/article'))
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--style',choices=['data','voc','scene'],default='data',help='兼容旧参数；正文始终消费已验证分析')
    args=parser.parse_args()
    data,binding=load_data(args.data,args.demo)
    outline=json.loads(Path(args.outline).read_text('utf-8'))
    if binding:verify_outline(data,binding,outline)
    manifest=json.loads((Path(args.report_dir)/'manifest.json').read_text('utf-8'))
    if manifest.get('outline_sha256')!=digest(Path(args.outline).read_bytes()):raise ValueError('图片来自其他排版版本')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    prefix={'title':'# ','heading':'## ','subheading':'### ','paragraph':''}
    markdown=[prefix[kind]+text+'\n' for kind,text in prose_blocks(outline)]
    body=[html_prose(outline)]
    for page in manifest['pages']:
        path=Path(args.report_dir)/page['file']
        if not path.is_file() or digest(path.read_bytes())!=page['sha256']:raise ValueError('正文图片不完整或已改变')
        relative=os.path.relpath(path.resolve(),out.resolve())
        markdown.append('!['+page['name']+']('+relative+')\n')
        body.append('<p><img style="width:100%;display:block" alt="'+html.escape(page['name'],quote=True)+'" src="'+html.escape(relative,quote=True)+'"></p>')
    (out/'article.md').write_text('\n'.join(markdown),'utf-8')
    (out/'article.html').write_text('<!doctype html><meta charset="utf-8"><article>'+''.join(body)+'</article>','utf-8')
    print(str(out))


if __name__=='__main__':main()
