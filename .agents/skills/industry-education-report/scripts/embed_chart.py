"""Insert the verified chart-visualization figure at its HTML comment marker."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import NamedTemporaryFile


RENDERER = Path(__file__).resolve().parents[2] / 'chart-visualization/scripts/figure.py'


def embed(spec, bundle, page):
    subprocess.run([sys.executable, str(RENDERER), 'verify', str(spec), '--out', str(bundle)], check=True)
    figure_id = json.loads(spec.read_text(encoding='utf-8'))['id']
    marker = f'<!-- chart:{figure_id} -->'
    source = (bundle / 'figure.html').read_text(encoding='utf-8')
    start = source.index('<figure ')
    figure = source[start:source.index('</figure>', start) + len('</figure>')]
    # The directory inode stays stable when a parallel chart replaces the page.
    directory = os.open(page.parent, os.O_DIRECTORY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        insert_figure(page, marker, figure)
    finally:
        os.close(directory)


def insert_figure(page, marker, figure):
    html = page.read_text(encoding='utf-8')
    wrapped = f'<div style="min-width:0;max-width:100%;overflow-x:auto">{figure}</div>'
    if marker not in html and html.count(figure) == 1:
        if wrapped in html:
            return
        marker = figure
    elif html.count(marker) != 1 or figure in html:
        raise ValueError(f'在目标网页中为此图保留一个占位：{marker}')
    with NamedTemporaryFile(dir=page.parent, delete=False) as staged:
        try:
            staged.write(html.replace(marker, wrapped).encode('utf-8'))
            staged.flush()
            os.fchmod(staged.fileno(), stat.S_IMODE(page.stat().st_mode))
            os.replace(staged.name, page)
        finally:
            Path(staged.name).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('page', type=Path)
    args = parser.parse_args()
    try:
        embed(args.spec, args.bundle, args.page)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(f'embed_chart: {error}')
