# -*- coding: utf-8 -*-
"""
pack_delivery.py — 生成对外交付压缩包（自动脱敏 + 敏感信息自检）
用法:
    python pack_delivery.py                    # 打包 output/ 下的最新产物
    python pack_delivery.py --name 自定义名称

脱敏规则:
    * report_data.json 副本剔除 provenance.queries（SQL 片段）与内部键，
      仅保留 对账结果/参数/指纹；
    * manifest.json 已为相对路径（渲染器保证）；
    * 打包前对全部文本文件做敏感扫描（内网IP / 本机路径 / SQL / 凭据），
      命中即中止，杜绝内部信息进入用户下载包。
"""
import argparse
import glob
import io
import json
import os
import re
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(BASE, 'output')

SENSITIVE = [
    (r'\b\d{1,3}(?:\.\d{1,3}){3}\b', '内网IP'),
    (r'[A-Za-z]:\\\\Users', '本机路径'),
    (r'\bSELECT\b.{0,40}\bFROM\b', 'SQL片段'),
    (r'"?password"?\s*:', '凭据字段'),
]


def sanitize_report_data(src):
    with open(src, 'r', encoding='utf-8') as f:
        d = json.load(f)
    prov = d.get('provenance') or {}
    d['provenance'] = {
        'generated_at': prov.get('generated_at'),
        'source_platform': prov.get('source_platform', '优才知路平台的数据库'),
        'params': prov.get('params'),
        'checks': prov.get('checks'),
        'all_checks_pass': prov.get('all_checks_pass'),
        'data_sha256': prov.get('data_sha256'),
    }
    return json.dumps(d, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default='人才需求观察报告_交付包')
    args = ap.parse_args()

    zip_path = os.path.join(OUTDIR, '%s.zip' % args.name)
    root = args.name
    files = []  # (arcname, kind, payload/path)

    for p in sorted(glob.glob(os.path.join(OUTDIR, 'report', 'pages',
                                           'page_*.png'))):
        files.append(('report/pages/' + os.path.basename(p), 'path', p))
    for rel in ('report/report_full.jpg', 'report/manifest.json'):
        p = os.path.join(OUTDIR, rel.replace('/', os.sep))
        if os.path.exists(p):
            files.append((rel, 'path', p))
    ev = os.path.join(OUTDIR, 'evidence_核查表.xlsx')
    if os.path.exists(ev):
        files.append(('evidence_核查表.xlsx', 'path', ev))
    for rel in ('article/article.md', 'article/article.html',
                'outline/outline.md', 'outline/report_outline.json',
                'verify_report.md', 'render_check.json'):
        p = os.path.join(OUTDIR, rel.replace('/', os.sep))
        if os.path.exists(p):
            files.append((rel, 'path', p))
    # V4：学生版（如已生成）一并入包
    for rel in ('article_student/article.md', 'article_student/article.html',
                'outline_student/outline.md',
                'outline_student/report_outline.json',
                'verify_report_student.md', 'render_check_student.json'):
        p = os.path.join(OUTDIR, rel.replace('/', os.sep))
        if os.path.exists(p):
            files.append((rel, 'path', p))
    if os.path.isdir(os.path.join(OUTDIR, 'report_student', 'pages')):
        for p in sorted(glob.glob(os.path.join(OUTDIR, 'report_student',
                                               'pages', 'page_*.png'))):
            files.append(('report_student/pages/' + os.path.basename(p),
                          'path', p))
        for rel in ('report_student/report_full.jpg',
                    'report_student/manifest.json'):
            p = os.path.join(OUTDIR, rel.replace('/', os.sep))
            if os.path.exists(p):
                files.append((rel, 'path', p))
    files.append(('report_data.json', 'text',
                  sanitize_report_data(os.path.join(BASE, 'report_data.json'))))

    # 敏感信息预检（文本类）
    problems = []
    for arc, kind, payload in files:
        if kind != 'text':
            continue
        for pat, name in SENSITIVE:
            if re.search(pat, payload):
                problems.append('%s 命中 %s' % (arc, name))
    if problems:
        print('❌ 敏感信息未清除，中止打包：')
        for x in problems:
            print('  -', x)
        raise SystemExit(1)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc, kind, payload in files:
            if kind == 'text':
                z.writestr(root + '/' + arc, payload)
            else:
                z.write(payload, root + '/' + arc)

    # 复检：压缩包内全部文本再扫一遍（双保险，需在关闭后进行）
    with zipfile.ZipFile(zip_path) as z:
        for n in z.namelist():
            if n.endswith(('.json', '.md', '.html')):
                txt = z.read(n).decode('utf-8', 'ignore')
                for pat, name in SENSITIVE:
                    if re.search(pat, txt):
                        raise SystemExit('❌ 打包后复检命中 %s：%s' % (name, n))

    print('✅ 脱敏打包完成: %s' % zip_path)
    print('   文件数 %d  大小 %.1f MB' % (len(files),
                                       os.path.getsize(zip_path) / 1048576))


if __name__ == '__main__':
    main()
