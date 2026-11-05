"""Atomically register a finished website, preserving verified content downloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


def register(directory, name='报告网页版', entry='index.html', files_from=None):
    root = Path.cwd().resolve()
    site = directory.resolve()
    if not site.is_relative_to(root / 'output/public') or directory.is_symlink():
        raise ValueError('网页须位于工作区 output/public/ 下的专用目录')
    page = site / entry
    if not page.resolve().is_relative_to(site) or not page.is_file() or page.suffix.lower() not in ('.html', '.htm'):
        raise ValueError('网页入口无效')
    manifest = root / 'delivery.json'
    data = json.loads(manifest.read_text()) if manifest.exists() else {}
    if files_from:
        files = json.loads(files_from.read_text())['files']
        for item in files:
            file = root / item['path']
            if not file.resolve().is_relative_to(root) or file.is_symlink():
                raise ValueError('内容文件须位于工作区内')
            if hashlib.sha256(file.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('内容原件已改变，请回到业务复核与构建')
        data['files'] = files
    web = data.get('web', [])
    relative = site.relative_to(root).as_posix()
    # A named revision replaces its own declaration, leaving other products alone.
    data['web'] = [item for item in web if item['name'] != name and item['directory'] != relative]
    data['web'].append({'name': name, 'directory': relative, 'entry': entry})
    fd, scratch = tempfile.mkstemp(prefix='.delivery-', dir=root)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.chmod(scratch, 0o640)
        os.replace(scratch, manifest)
    finally:
        Path(scratch).unlink(missing_ok=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--name', default='报告网页版')
    parser.add_argument('--entry', default='index.html')
    parser.add_argument('--files-from', type=Path)
    args = parser.parse_args()
    print(register(args.directory, args.name, args.entry, args.files_from))
