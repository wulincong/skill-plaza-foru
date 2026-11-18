"""Validate an individualized plan against retrieval receipts, then render and register it."""
import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f'缺少{label}')
    return value.strip()


def integer(value, minimum, maximum, label):
    require(type(value) is int and minimum <= value <= maximum, f'{label}无效')
    return value


def escaped(value):
    return re.sub(r'([\\`*_{}\[\]<>|])', r'\\\1', str(value)).replace('\n', ' ')


def section(title, blocks):
    return {'type': 'section', 'title': title, 'blocks': blocks}


def build_page(plan, evidence, user_messages=None, current_run=None):
    profile = plan['profile']
    role = text(profile.get('role'), '目标岗位')
    mode = plan.get('mode')
    require(mode in ('full', 'partial', 'self'), '匹配状态无效')
    queried = any(e.get('operation') == 'tags' and e.get('result', {}).get('status') in ('ok', 'empty') for e in evidence)
    authorization = plan.get('fallback_authorization', '')
    authorized = isinstance(authorization, str) and bool(authorization.strip()) and any(authorization in message for message in (user_messages or []) if isinstance(message, str))
    active = [e for e in evidence if e.get('runId') == current_run] if current_run else evidence
    failed = any(e.get('result', {}).get('status') not in ('ok', 'empty') for e in active)
    require(not failed or (mode == 'self' and authorized), '本轮知识库查询失败，必须等待用户选择自主规划')
    require(queried or (mode == 'self' and failed and authorized), '缺少成功的课程分类查询记录或用户授权的故障后自主规划')
    require(not authorization or authorized, '自主规划授权必须引用用户的实际原话')
    tags, documents = {}, {}
    for entry in evidence:
        result = entry.get('result', {})
        if result.get('status') not in ('ok', 'empty'):
            continue
        for item in result.get('items', []):
            if entry['operation'] == 'tags':
                tags[item['id']] = item
            elif entry['operation'] == 'documents':
                documents[item['id']] = item
    days_per_week = integer(plan.get('days_per_week'), 1, 7, '每周学习天数')
    budget = integer(plan.get('minutes_per_day'), 1, 1440, '每日学习时间')
    courses = plan.get('courses', [])
    require(isinstance(courses, list) and ((mode == 'self' and not courses) or (mode != 'self' and bool(courses))), '匹配状态与课程包不一致')
    selected, course_blocks = {}, []
    for course in courses:
        tag = tags.get(course['id'])
        require(tag is not None and course['name'] == tag['name'], '课程分类不是查询返回的真实分类')
        ids = course.get('document_ids', [])
        require(isinstance(ids, list) and bool(ids), '匹配课程缺少教材')
        links = []
        for doc_id in ids:
            doc = documents.get(doc_id)
            require(doc is not None, '引用了未经查询的教材')
            require(doc.get('tag_id') == course['id'], '教材不属于对应分类')
            for field, action in (('preview_url', 'preview'), ('download_url', 'download')):
                require(re.fullmatch(r'https?://[^/\s]+/api/learning-materials/[a-f0-9]{48}/' + action, doc.get(field, '')) is not None, '教材缺少平台授权链接')
            selected[doc_id] = doc
            links.append(f"[{escaped(doc['title'])}]({doc['preview_url']}) · [下载]({doc['download_url']})")
        course_blocks.append(section(course['name'], [{'type':'text', 'text':text(course.get('reason'), '课程匹配理由')}, {'type':'text', 'text':'\n\n'.join(links)}]))
    stage_blocks, used, count, total_minutes = [], set(), 0, 0
    stages = plan.get('stages')
    require(isinstance(stages, list) and bool(stages), '缺少学习阶段')
    for stage in stages:
        daily_blocks = []
        require(isinstance(stage.get('days'), list) and bool(stage['days']), '阶段缺少每日任务')
        for day in stage['days']:
            count += 1
            tasks = day.get('tasks', [])
            require(isinstance(tasks, list) and bool(tasks), '缺少每日任务')
            day_minutes = 0
            task_rows = []
            for task in tasks:
                minutes = integer(task.get('minutes'), 1, 1440, '任务时间')
                day_minutes += minutes
                materials = task.get('materials', [])
                require(isinstance(materials, list), '教材引用格式无效')
                material_links = []
                for doc_id in materials:
                    require(doc_id in selected, '任务引用未知教材')
                    used.add(doc_id)
                    doc = selected[doc_id]
                    material_links.append(f"[{escaped(doc['title'])}]({doc['preview_url']})")
                task_rows.append({'title':text(task.get('task'), '任务内容'), 'text':f'{minutes} 分钟。' + ('教材：' + ' · '.join(material_links) if material_links else '自主练习。') + '\n\n完成要求：' + text(task.get('deliverable'), '完成标准')})
            require(day_minutes <= budget, f'第{count}天任务时间超过每日可投入时间')
            total_minutes += day_minutes
            daily_blocks.append(section(f'第{count}天 · {day_minutes}分钟', [{'type':'actions','items':task_rows}]))
        stage_blocks.append(section(text(stage.get('title'), '阶段名称'), [
            {'type':'text','text':text(stage.get('goal'), '阶段目标')},
            *daily_blocks,
            {'type':'text','text':'阶段验收：' + text(stage.get('completion'), '阶段成果与验收')},
        ]))
    for course in courses:
        require(any(doc_id in used for doc_id in course['document_ids']), '匹配课程没有关联到每日任务')
    mode_label = {'full':'知识库课程规划', 'partial':'知识库课程与补充规划', 'self':'自主规划，未匹配到合适的库内教材'}[mode]
    if mode == 'self' and authorized:
        mode_label = '按你的选择自主规划；本次知识库访问未完成，尚未核实库内教材'
    assumptions = plan.get('assumptions', [])
    require(isinstance(assumptions, list) and all(isinstance(x, str) for x in assumptions), '规划假设格式无效')
    if not profile.get('availability', '').strip():
        require(bool(assumptions), '未提供可投入时间，需写明时间安排假设')
    summary = text(plan.get('summary'), '规划结论')
    lead, separator, remainder = summary.partition('。')
    if len(lead) > 80:
        lead, remainder = f'{role}学习路线', summary
    elif separator:
        lead += separator
    blocks = [
        {'type':'summary','lead':lead,'text':remainder + f'\n\n{mode_label}。共 {count} 个学习日，按每周 {days_per_week} 天安排，约 {math.ceil(count / days_per_week)} 周，总学习时间 {total_minutes / 60:g} 小时。'},
        section('你的学习起点', [{'type':'table','pattern':'key-value','columns':[{'label':'项目'},{'label':'内容'}], 'rows':[[label, profile.get(key) or '未提供'] for key,label in (('role','目标岗位'),('goal','学习目标'),('foundation','当前基础'),('availability','可投入时间'))]}]),
    ]
    if assumptions:
        blocks.append(section('本次规划的假设', [{'type':'text','text':'\n'.join('- ' + escaped(x) for x in assumptions)}]))
    empty_note = '按你的选择采用自主规划，本次知识库访问未完成，尚未核实库内教材。' if authorized else '本次未匹配到合适的库内教材，以下任务为根据目标岗位生成的学习建议。'
    blocks.append(section('推荐课程包与教材', course_blocks or [{'type':'text','text':empty_note}]))
    blocks.append(section('分阶段学习路线与每日任务', stage_blocks))
    blocks.append(section('进度调整建议', [{'type':'text','text':text(plan.get('adjustments'), '调整建议')}]))
    return {'title':f'{role}个性化学习计划','eyebrow':'学生学习规划','theme':'minimal','blocks':blocks,
            'footer':('本报告采用自主学习建议，未完成库内教材核验。' if authorized else '本报告为自主学习建议，未匹配到合适的库内教材。' if mode == 'self' else '课程资料来自已核对的知识库查询；补充任务为学习规划建议。教材入口按持链接可访问，请仅分享给需要使用资料的人。')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--workdir', type=Path)
    args = parser.parse_args()
    plan_file = args.plan.resolve()
    root = (args.workdir or plan_file.parent).resolve()
    try:
        require(plan_file.is_relative_to(root), '计划文件必须位于指定工作区内')
        require(not root.is_relative_to(Path(__file__).resolve().parents[2]), '不能把技能安装目录作为报告工作区')
        evidence = [json.loads(line) for line in (root / '.weknora-evidence.jsonl').read_text().splitlines() if line.strip()]
        request_file = root / '.learning-request.json'
        request = json.loads(request_file.read_text()) if request_file.exists() else {}
        page = build_page(json.loads(plan_file.read_text()), evidence, request.get('messages', []), request.get('runId'))
        model = root / 'learning-page.json'
        model.write_text(json.dumps(page, ensure_ascii=False, indent=2))
        out = (root / (args.out or Path('output/public') / ('learning-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f')))).resolve()
        require(out.is_relative_to(root / 'output/public'), '报告必须在工作区 output/public 下')
        rendering = Path(__file__).resolve().parents[2] / 'report-rendering/scripts'
        subprocess.run([sys.executable, str(rendering / 'render.py'), str(model), '--out', str(out)], check=True, cwd=root)
        subprocess.run([sys.executable, str(rendering / 'register_delivery.py'), str(out), '--name', '个性化学习计划'], check=True, cwd=root)
        print(json.dumps({'status':'ok','directory':str(out.relative_to(root)), 'entry':'index.html'}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'status':'validation_error','message':str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
