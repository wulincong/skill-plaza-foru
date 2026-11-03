"""Create an INTERNAL audit workbook from actual shared query evidence."""
import argparse
import json
from pathlib import Path
from openpyxl import Workbook
from bound_report import load_data

from report_runtime import report_root
BASE = report_root(__file__)


def cell(value):
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
    return "'"+text if isinstance(text, str) and text.startswith(('=', '+', '-', '@')) else text


def build_workbook(data, binding):
    wb = Workbook()
    ws = wb.active
    ws.title = '实际查询'
    ws.append(['queryId', '完成', '实际SQL', '返回聚合行数', '逐语句耗时'])
    if binding:
        evidence = json.loads(binding['_source'].with_name('evidence.json').read_text('utf-8'))
        for q in evidence['queries']:
            ws.append([cell(q['id']), q['completed'], cell(q['sql']), len(q.get('rows', [])), '未可靠测量'])
    else:
        ws.append(['离线演示', False, '未执行真实查询', 0, '不适用'])
    ws = wb.create_sheet('指标与方法')
    ws.append(['metricId', '状态', '单位', '分母', '方法', '实际查询引用', '结果'])
    if binding:
        for m in binding['_result']['metrics']:
            # Excel cells have a 32767 character limit; rows retain the actual source reference.
            value = m.get('value', m.get('rows'))
            encoded = json.dumps(value, ensure_ascii=False)
            ws.append([m['metricId'], m['status'], m['unit'], m.get('denominator'), cell(m['method']),
                       cell(m.get('evidenceIds', [])), cell(encoded if len(encoded) < 32000 else '完整结果见对应metricId的result.json，超出单元格容量')])
    ws = wb.create_sheet('报告字段引用')
    ws.append(['报告字段', '来源metricId'])
    if binding:
        for field, ids in binding['fields'].items():
            ws.append([field, cell(ids)])
    ws = wb.create_sheet('对账与范围')
    ws.append(['项目', '内容'])
    ws.append(['来源', '优才知路平台数据库'])
    ws.append(['筛选', cell(data['meta'].get('filters', {}))])
    ws.append(['读取时间', data['meta']['generated_at']])
    if binding:
        ws.append(['来源请求ID', binding['source']['requestId']])
        ws.append(['结果内容指纹', binding['source']['contentHash']])
        ws.append(['来源结果文件', binding['source']['result']])
        for c in binding['_result']['quality']['checks']:
            ws.append([c['id'], cell(c)])
        ws.append(['批次耗时ms（含建连传输）', binding['_result']['execution']['sqlBatchMs']])
    return wb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=str(BASE/'report_data.json'))
    ap.add_argument('--out', default=str(BASE/'output/internal/evidence_核查表.xlsx'))
    ap.add_argument('--demo', action='store_true')
    args = ap.parse_args()
    data, binding = load_data(args.data, args.demo)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    build_workbook(data, binding).save(out)
    print('内部核查表：'+str(out))


if __name__ == '__main__':
    main()
