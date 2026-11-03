"""Separate read-only installed Python code from writable report data and assets."""
import os
from pathlib import Path


def report_root(source_file):
    configured=os.environ.get('WECHAT_REPORT_WORKDIR')
    return Path(configured).resolve() if configured else Path(source_file).resolve().parent.parent
