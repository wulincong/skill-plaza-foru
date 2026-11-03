"""Pi's non-interactive build entry: saved data + agent analysis -> checked images."""
import argparse
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent.parent


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
    # A failed revision must not leave an old declaration looking like the new result.
    declaration = Path(args.workspace).resolve()/'delivery.json'
    declaration.unlink(missing_ok=True)
    for name, options in steps:
        subprocess.run([sys.executable, str(BASE/'scripts'/name), *options], cwd=BASE, check=True)
    print('报告图片已生成并通过程序检查，请审核最终成品。')


if __name__ == '__main__':
    main()
