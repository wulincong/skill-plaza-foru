"""Offline regression tests for the course package contract, hard rules and build outputs."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import course

EXCERPT = '岗位职责： 1.负责物流运输机器人(AGV/AMR)的系统开发，包括导航、路径规划与运动控制； 2.编写部署文档。'
SAMPLE = {'positionId': '14600406343483408', 'title': 'ros开发工程师', 'education': '本科',
          'experience': '3年以内', 'excerpt': EXCERPT, 'charCount': 547, 'truncated': False,
          'hash': 'b' * 64}
SYNTHETIC_RESULT = {
    'requestId': 'tq-test0001', 'contentHash': 'a' * 64,
    'freshness': {'dataReadAt': '2026-11-18T08:00:00+08:00'},
    'status': 'complete', 'quality': {'checks': [{'pass': True}]},
    'consistency': {'completeTransaction': True},
    'metrics': [
        {'metricId': 'robot/positions.count', 'name': 'positions.count', 'status': 'complete', 'value': 125377},
        {'metricId': 'robot/description.samples', 'name': 'description.samples', 'status': 'complete',
         'value': 5, 'describedN': 125377, 'rows': [SAMPLE]},
    ],
}


def fake_inspect(source):
    source.setdefault('contentHash', SYNTHETIC_RESULT['contentHash'])
    source.setdefault('dataReadAt', SYNTHETIC_RESULT['freshness']['dataReadAt'])
    source.setdefault('published', '未标注')
    source.setdefault('accessed', '2026-11-18')
    return SYNTHETIC_RESULT


def t05_package():
    return {
        'schema': 't05-course-development/1',
        'program': {'majorName': '智能机器人技术', 'majorCode': '460304', 'version': '2026-1', 'asOf': '2026-11-18'},
        'tasks': [{
            'courseId': 'CS1', 'courseName': '工业机器人系统集成', 'category': 'professional-core',
            'credits': 4.5, 'theoryHours': 40, 'practiceHours': 32, 'semesters': [3], 'assessment': '考试',
            'capabilityRefs': [{'capabilityId': 'C-OPS-1', 'level': 'H'}, {'capabilityId': 'C-OPS-2', 'level': 'M'}],
            'evidenceRefs': {'metricIds': ['M_SKILLS'], 'sourceIds': []},
            'developmentNotes': '设置理由摘要',
        }],
        'evidenceIndex': {'metrics': {}, 'sources': {}},
    }


def fixture(package=True):
    return {
        'schema': 'course-package/1', 'status': 'draft', 'asOf': '2026-11-18',
        'meta': {
            'courseName': '工业机器人系统集成', 'courseId': 'CS1',
            'positioning': '专业核心课，面向机器人运维与集成岗位群。',
            'sourcePackage': 'uploads/t05-package.json' if package else None,
            'targetPositions': [{'name': '机器人运维工程师', 'sourceIds': ['S_T05']}],
            'weeks': 18, 'totalHours': 72, 'theoryHours': 40, 'practiceHours': 32,
            'semester': 3, 'credits': 4.5, 'periodMinutes': 45,
        },
        'sources': [
            {'id': 'S_T05', 'title': 'T03 课程开发任务包', 'url': 'uploads/t05-package.json',
             'excerpt': '课程卡片与能力绑定'},
            {'id': 'S_TQ', 'title': '机器人产业岗位查询', 'url': 'data/tq-test0001/result.json'},
        ],
        'metrics': [
            {'id': 'M_POS', 'label': '机器人产业在招岗位量', 'unit': 'job_records',
             'definition': 'national + industries=15', 'source_ids': ['S_TQ'],
             'binding': {'metricId': 'robot/positions.count', 'field': 'value'}},
        ],
        'workTasks': [
            {'id': 'WT1', 'name': 'AGV 系统开发与导航调优',
             'jdRefs': [{'positionId': SAMPLE['positionId'], 'hash': SAMPLE['hash'],
                         'quote': '负责物流运输机器人(AGV/AMR)的系统开发'}], 'sourceIds': []},
        ],
        'learningUnits': [
            {'id': 'M1', 'name': '导航系统部署', 'actionDomain': '部署与实施', 'weeks': [1, 2, 3, 4], 'hours': 16, 'taskIds': ['WT1']},
            {'id': 'M2', 'name': '运动控制集成', 'actionDomain': '集成与调试', 'weeks': [5, 6, 7, 8, 9, 10, 11, 12], 'hours': 32, 'taskIds': ['WT1']},
            {'id': 'M3', 'name': '综合联调与验收', 'actionDomain': '验收与文档', 'weeks': [13, 14, 15, 16, 17, 18], 'hours': 24, 'taskIds': ['WT1']},
        ],
        'outline': [{'week': w, 'unitId': 'M1' if w <= 4 else 'M2' if w <= 12 else 'M3',
                     'content': f'第 {w} 周内容', 'task': f'第 {w} 周任务', 'assessment': '实操检查单'} for w in range(1, 19)],
        'knowledgePoints': [
            {'id': 'K1', 'type': 'skill', 'text': '能完成 AGV 导航参数配置', 'capabilityId': 'C-OPS-1', 'unitId': 'M1',
             'assessmentPoint': {'form': '实操', 'criteria': '导航路线偏差小于阈值', 'passStandard': '45 分钟内独立完成'}, 'sourceIds': ['S_T05']},
            {'id': 'K2', 'type': 'knowledge', 'text': '掌握运动控制接口协议', 'capabilityId': 'C-OPS-2', 'unitId': 'M2',
             'assessmentPoint': {'form': '笔试', 'criteria': '协议字段默写', 'passStandard': '得分≥60'}, 'sourceIds': ['S_T05']},
            {'id': 'K3', 'type': 'skill', 'text': '能完成系统联调与验收报告', 'capabilityId': 'C-OPS-1', 'unitId': 'M3',
             'assessmentPoint': {'form': '作品', 'criteria': '报告完整可复核', 'passStandard': '评审通过'}, 'sourceIds': ['S_T05']},
        ],
        'lessonSamples': [
            {'unitId': 'M1', 'title': '导航系统部署·单元教学设计', 'hours': 4, 'stages': [
                {'phase': '导入', 'minutes': 30, 'teacher': '演示产线场景', 'student': '观察记录'},
                {'phase': '展开', 'minutes': 100, 'teacher': '讲解参数', 'student': '分组配置'},
                {'phase': '收束', 'minutes': 50, 'teacher': '点评结果', 'student': '互查报告'}]},
            {'unitId': 'M2', 'title': '运动控制集成·单元教学设计', 'hours': 4, 'stages': [
                {'phase': '导入', 'minutes': 30, 'teacher': '复盘上周', 'student': '汇报'},
                {'phase': '展开', 'minutes': 100, 'teacher': '示范接线', 'student': '实操'},
                {'phase': '收束', 'minutes': 50, 'teacher': '小结', 'student': '提交记录'}]},
        ],
        'trainingTasks': [
            {'id': 'T1', 'unitId': 'M1', 'title': 'AGV 导航部署实训', 'background': '模拟产线场景',
             'requirements': ['完成导航配置'], 'deliverables': ['部署报告'],
             'scoring': [{'item': '路线可用', 'weight': 60, 'standard': '偏差达标'}, {'item': '文档', 'weight': 40, 'standard': '完整'}],
             'passStandard': '总分≥60', 'safetyNotes': ['设备断电操作']},
            {'id': 'T2', 'unitId': 'M2', 'title': '运动控制集成实训', 'background': '工位联调',
             'requirements': ['完成接口对接'], 'deliverables': ['联调记录'],
             'scoring': [{'item': '联动成功', 'weight': 100, 'standard': '全流程跑通'}],
             'passStandard': '总分≥60', 'safetyNotes': []},
        ],
        'assessmentPlan': {'forms': [
            {'form': '过程考核', 'weight': 40, 'points': ['K1', 'K2'], 'method': '实训检查单逐项评分'},
            {'form': '期末实操', 'weight': 60, 'points': ['K3'], 'method': '综合任务现场评分'}],
            'passStandard': '总评≥60 且实操≥60', 'resit': '补做综合实训'},
        'resourceGaps': [
            {'type': 'generated', 'item': '模块一实训指导书', 'consumer': 'courseware-studio', 'note': '以实训任务书为输入'},
            {'type': 'manual', 'item': 'AGV 实训设备 8 台', 'note': '实训室现有 4 台'},
        ],
        'complianceChecks': [
            {'item': '课程定位与专业教学标准课程设置对接', 'standardExcerpt': '专业核心课程应开出……',
             'sourceId': 'S_T05', 'courseRef': 'M1', 'status': 'conform', 'suggestion': None},
        ],
        'decisions': [], 'openDecisions': [],
    }


def run(d):
    return course.validate(json.loads(json.dumps(d)))


class ValidationTests(unittest.TestCase):
    def setUp(self):
        import os
        import tempfile
        self.previous = Path.cwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        Path('uploads').mkdir(exist_ok=True)
        Path('uploads/t05-package.json').write_text(json.dumps(t05_package(), ensure_ascii=False), encoding='utf-8')
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: os.chdir(self.previous))

    def test_fixture_passes(self):
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, warnings, computed = run(fixture())
        self.assertEqual(errors, [])
        self.assertEqual(computed['knowledgePoints'], 3)
        self.assertTrue(any('安全' in w for w in warnings))

    def test_binding_backfills_value(self):
        d = fixture()
        with patch.object(course, 'inspect_source', fake_inspect):
            validated, errors, _, _ = course.validate(d)
        self.assertEqual(errors, [])
        self.assertEqual(d['metrics'][0]['value'], 125377)
        self.assertEqual(d['sources'][1]['contentHash'], 'a' * 64)

    def test_binding_rejects_hand_edited_value(self):
        d = fixture()
        d['metrics'][0]['value'] = 999
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('手填数值与工件不符' in e for e in errors))

    def test_knowledge_point_without_assessment_is_blocked(self):
        d = fixture()
        d['knowledgePoints'][0]['assessmentPoint'] = {'form': '实操'}
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('考核点' in e for e in errors))

    def test_capability_outside_package_needs_user_source(self):
        d = fixture()
        d['knowledgePoints'][1]['capabilityId'] = 'C-USER-9'
        d['knowledgePoints'][1]['sourceIds'] = []
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('能力项不在任务包中' in e for e in errors))

    def test_high_capability_uncovered_warns(self):
        d = fixture()
        for p in d['knowledgePoints']:
            p['capabilityId'] = 'C-OPS-2'
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, warnings, _ = run(d)
        self.assertEqual(errors, [])
        self.assertTrue(any('C-OPS-1' in w and '高支撑' in w for w in warnings))

    def test_hours_and_outline_must_reconcile(self):
        d = fixture()
        d['learningUnits'][0]['hours'] = 20
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('totalHours' in e for e in errors))
        d = fixture()
        d['outline'] = d['outline'][:17]
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('逐周覆盖' in e for e in errors))

    def test_jd_reference_must_match_sample_fingerprint_and_quote(self):
        d = fixture()
        d['workTasks'][0]['jdRefs'][0]['hash'] = 'c' * 64
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('指纹不符' in e or '不存在' in e for e in errors))
        d = fixture()
        d['workTasks'][0]['jdRefs'][0]['quote'] = '负责与样本原文不一致的表述'
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('逐字摘录' in e for e in errors))

    def test_task_without_jd_needs_material_source(self):
        d = fixture()
        d['workTasks'][0]['jdRefs'] = []
        d['workTasks'][0]['sourceIds'] = []
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('用户材料来源' in e for e in errors))

    def test_t05_package_consistency(self):
        d = fixture()
        d['meta']['theoryHours'] = 36
        d['meta']['totalHours'] = 68
        d['meta']['practiceHours'] = 32
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('与任务包不一致' in e for e in errors))
        d = fixture()
        d['meta']['courseName'] = '改名课程'
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('课程名与任务包不一致' in e for e in errors))

    def test_standalone_course_without_package(self):
        d = fixture(package=False)
        d['meta']['sourcePackage'] = None
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertEqual(errors, [])

    def test_weights_and_pass_standards(self):
        d = fixture()
        d['assessmentPlan']['forms'][0]['weight'] = 50
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('权重合计必须为 100' in e for e in errors))
        d = fixture()
        d['trainingTasks'][0]['scoring'][0]['weight'] = 50
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('评分权重合计必须为 100' in e for e in errors))

    def test_compliance_conflict_requires_suggestion_and_excerpt(self):
        d = fixture()
        d['complianceChecks'][0]['status'] = 'conflict'
        d['complianceChecks'][0]['suggestion'] = None
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('冲突项必须给处理建议' in e for e in errors))
        d = fixture()
        d['complianceChecks'][0]['standardExcerpt'] = ''
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('原文摘录' in e for e in errors))

    def test_final_blocks_open_decisions_and_pending_checks(self):
        d = fixture()
        d['status'] = 'final'
        d['openDecisions'] = [{'question': '考核结构待定', 'options': ['A', 'B']}]
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('openDecisions 必须为空' in e for e in errors))
        d = fixture()
        d['status'] = 'final'
        d['complianceChecks'].append({'item': '技能等级标准对接', 'status': 'pending'})
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('scope=standards' in e for e in errors))

    def test_decision_quote_must_come_from_session(self):
        Path('course-input.json').write_text(json.dumps(
            {'runId': 'r1', 'message': '按现有证据继续', 'earlierMessages': []}), encoding='utf-8')
        d = fixture()
        d['decisions'] = [{'id': 'D1', 'question': '样本不足', 'userReply': '用户从未说过的话', 'scope': 'evidence'}]
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertTrue(any('userReply 不在本会话用户消息中' in e for e in errors))
        d['decisions'][0]['userReply'] = '按现有证据继续'
        with patch.object(course, 'inspect_source', fake_inspect):
            _, errors, _, _ = run(d)
        self.assertFalse(any('userReply' in e for e in errors))


class BuildTests(unittest.TestCase):
    def setUp(self):
        import tempfile, os
        self.previous = Path.cwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(lambda: os.chdir(self.previous))

    def test_build_writes_consistent_outputs(self):
        (Path('uploads')).mkdir(exist_ok=True)
        Path('uploads/t05-package.json').write_text(json.dumps(t05_package(), ensure_ascii=False), encoding='utf-8')
        d = fixture()
        with patch.object(course, 'inspect_source', fake_inspect), \
             patch('builtins.print'):
            code = course.build(d, Path.cwd())
        built_dirs = list(Path('output').glob('course-*'))
        self.assertEqual(len(built_dirs), 1)
        out = built_dirs[0]
        self.assertEqual(code, 0)
        for name in ('course.md', 'course.json', 'validation.json', 'course-files.json'):
            self.assertTrue((out / name).is_file(), name)
        manifest = json.loads((out / 'course-files.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest), 3)
        for entry in manifest:
            digest_file = hashlib.sha256((out / entry['name']).read_bytes()).hexdigest()
            self.assertEqual(digest_file, entry['sha256'])
        body = (out / 'course.md').read_text(encoding='utf-8')
        self.assertIn('课程整体设计', body)
        self.assertIn('标准合规核对表', body)
        self.assertIn('C-OPS-1', body)
        built = json.loads((out / 'course.json').read_text(encoding='utf-8'))
        self.assertEqual(built['metrics'][0]['value'], 125377)

    def test_build_blocks_on_errors(self):
        d = fixture()
        d['knowledgePoints'][0].pop('assessmentPoint')
        with patch.object(course, 'inspect_source', fake_inspect):
            with self.assertRaises(SystemExit):
                course.build(d, Path.cwd())


if __name__ == '__main__':
    unittest.main()
