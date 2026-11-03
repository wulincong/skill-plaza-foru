"""Package public report artifacts; query evidence stays in output/internal."""
import argparse
import json
import html
import os
import shutil
import stat
import tempfile
from pathlib import Path
import zipfile
from PIL import Image
from bound_report import load_data, verify_outline, digest
from report_runtime import report_root
BASE = report_root(__file__)


def prepare_delivery(workspace, report, outline, manifest, archive):
    """Prepare a self-contained public site; never copies a whole work directory."""
    public = report.parent/'public'
    public.resolve().relative_to(workspace)
    public.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.site-', dir=public))
    try:
        # mkdtemp defaults to 0700; the web server uses the shared workspace group.
        temporary.chmod(temporary.stat().st_mode | stat.S_IRGRP | stat.S_IXGRP)
        (temporary/'assets').mkdir()
        blocks = []
        for i, screen in enumerate(outline['screens']):
            source = (report/manifest['pages'][i]['file']).resolve()
            image = 'page_'+str(i+1).zfill(2)+source.suffix
            shutil.copyfile(source, temporary/'assets'/image)
            with Image.open(source) as page:
                width, height = page.size
            alt = html.escape(screen['title'], quote=True)
            loading = 'eager' if i == 0 else 'lazy'
            blocks.append(f'<img src="assets/{image}" width="{width}" height="{height}" '
                          f'loading="{loading}" alt="第{i+1}页 {alt}">')
        title = html.escape(outline['title'])
        document = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width,initial-scale=1">'
                    f'<title>{title}</title><style>body{{margin:0;background:#edf0f4}}'
                    'main{max-width:720px;margin:auto;background:white}'
                    'img{display:block;width:100%;height:auto}</style></head><body>'
                    '<main>'+''.join(blocks)+'</main></body></html>')
        (temporary/'index.html').write_text(document, 'utf-8')
        site = public/'site'
        if site.is_symlink():
            raise ValueError('公开网页目录不能为符号链接')
        if site.exists():
            shutil.rmtree(site)
        temporary.rename(site)
        shutil.copyfile(archive, public/'report.zip')
        declaration = {'web': [{'name': outline['title'], 'directory': site.relative_to(workspace).as_posix(), 'entry': 'index.html'}],
                       'files': [{'name': archive.stem, 'path': (public/'report.zip').relative_to(workspace).as_posix()}]}
        # Manifest is the last write: the server never receives a partial delivery.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=workspace, prefix='.delivery-', delete=False) as pending:
            json.dump(declaration, pending, ensure_ascii=False, indent=2)
            os.fchmod(pending.fileno(), 0o640)
        os.replace(pending.name, workspace/'delivery.json')
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(BASE/'report_data.json'))
    ap.add_argument('--outline', default=str(BASE/'output/outline/report_outline.json'))
    ap.add_argument('--report-dir', default=str(BASE/'output/report'))
    ap.add_argument('--name', default='人才需求观察报告_交付包')
    ap.add_argument('--workspace', default=str(BASE), help='会话根目录；工作副本位于 wechat-report/ 时传 ..')
    args = ap.parse_args()
    if Path(args.name).name != args.name:
        raise ValueError('交付包名称不能包含路径')
    data, binding = load_data(args.data)
    outline_path = Path(args.outline)
    outline = json.loads(outline_path.read_text('utf-8'))
    verify_outline(data, binding, outline)
    report = Path(args.report_dir).resolve()
    workspace = Path(args.workspace).resolve(strict=True)
    report.relative_to(workspace)
    manifest = json.loads((report/'manifest.json').read_text('utf-8'))
    if manifest.get('outline_sha256') != digest(outline_path.read_bytes()) or len(manifest['pages']) != len(outline['screens']):
        raise ValueError('图片清单与当前大纲不一致')
    quality = json.loads((report/'quality.json').read_text('utf-8'))
    if (quality.get('schema') != 'wechat-quality/1' or quality.get('all_pass') is not True
            or quality.get('outline_sha256') != digest(outline_path.read_bytes())
            or quality.get('manifest_sha256') != digest((report/'manifest.json').read_bytes())):
        raise ValueError('最终质检未通过或产物版本已变化')
    files = []
    seen = set()
    for i, page in enumerate(manifest['pages']):
        source = (report/page['file']).resolve()
        if (page['index'] != i or page['name'] != outline['screens'][i]['title']
                or source in seen or not source.is_relative_to(report) or not source.is_file()):
            raise ValueError('清单图片缺失、重复或顺序与大纲不符')
        if page.get('sha256') != digest(source.read_bytes()):
            raise ValueError('图片在质检后已改变')
        with Image.open(source) as image:
            if source.suffix != '.png' or image.format != 'PNG':
                raise ValueError('报告分屏必须是 PNG 图片')
            image.verify()
        seen.add(source)
        files.append((f'page_{i+1:02}.png', source))
    out = report.parent/(args.name+'.zip')
    with zipfile.ZipFile(out, 'w') as z:
        for name, source in files:
            z.write(source, args.name+'/'+name)
    prepare_delivery(workspace, report, outline, manifest, out)
    print(str(out))


if __name__ == '__main__':
    main()
