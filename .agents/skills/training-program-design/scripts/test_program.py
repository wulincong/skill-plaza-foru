"""Offline regression tests for program contracts, redlines and build outputs."""
import json
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.dom import minidom

import program

SYNTHETIC_RESULT = {
    'requestId': 'tq-test0001', 'contentHash': 'a' * 64,
    'freshness': {'dataReadAt': '2026-11-10T08:00:00+08:00'},
    'status': 'complete', 'quality': {'checks': [{'pass': True}]},
    'consistency': {'completeTransaction': True},
    'metrics': [
        {'metricId': 'all/positions.count', 'name': 'positions.count', 'status': 'complete',
         'value': 123},
        {'metricId': 'all/salary.summary', 'name': 'salary.summary', 'status': 'complete',
         'value': {'median': 9.5}},
        {'metricId': 'all/education.distribution', 'name': 'education.distribution', 'status': 'complete',
         'denominator': 123,
         'rows': [{'labels': {'学历': '大专/高职'}, 'count': 40, 'share': 0.33}]},
    ],
}


def fake_inspect(source):
    source.setdefault('contentHash', SYNTHETIC_RESULT['contentHash'])
    source.setdefault('dataReadAt', SYNTHETIC_RESULT['freshness']['dataReadAt'])
    source.setdefault('published', '未标注')
    source.setdefault('accessed', '2026-11-10')
    return SYNTHETIC_RESULT


def course(cid, name, category, theory, practice, credits, semesters, caps, extra_sources=()):
    return {
        'id': cid, 'name': name, 'category': category,
        'theoryHours': theory, 'practiceHours': practice, 'credits': credits,
        'semesters': semesters, 'assessment': '考试',
        'domains': [{'capabilityId': cap, 'level': level} for cap, level in caps],
        'rationale': {'text': f'{name} 依据岗位证据设置',
                      'metricIds': ['M_POS'], 'sourceIds': list(extra_sources)},
    }


def fixture():
    public_required = [
        course('P1', '思想道德与法治', 'public-required', 48, 0, 3, [1], [], ['S_STD']),
        course('P2', '毛泽东思想和中国特色社会主义理论体系概论', 'public-required', 64, 0, 4, [2], [], ['S_STD']),
        course('P3', '习近平新时代中国特色社会主义思想概论', 'public-required', 48, 0, 3, [3], [], ['S_STD']),
        course('P4', '形势与政策', 'public-required', 16, 0, 1, [1, 2, 3], [], ['S_STD']),
        course('P5', '体育', 'public-required', 0, 108, 6, [1, 2, 3, 4], [], ['S_STD']),
        course('P6', '大学英语', 'public-required', 128, 0, 8, [1, 2], [], ['S_STD']),
        course('P7', '信息技术基础', 'public-required', 32, 32, 4, [1], [], ['S_STD']),
        course('P8', '心理健康教育', 'public-required', 28, 4, 2, [1, 2], [], ['S_STD']),
        course('P9', '军事理论与军训', 'public-required', 16, 28, 2, [1], [], ['S_STD']),
        course('P10', '劳动教育', 'public-required', 16, 8, 1.5, [1, 2, 3], [], ['S_STD']),
        course('P11', '职业发展与就业指导', 'public-required', 24, 8, 2, [1, 5], [], ['S_STD']),
    ]
    public_elective = [
        course('E1', '人文素养类选修', 'public-elective', 32, 0, 2, [2], [], ['S_STD']),
        course('E2', '艺术类选修', 'public-elective', 32, 0, 2, [3], [], ['S_STD']),
        course('E3', '科学素养类选修', 'public-elective', 16, 0, 1, [2], [], ['S_STD']),
        course('E4', '健康教育类选修', 'public-elective', 16, 0, 1, [4], [], ['S_STD']),
        course('E5', '创新创业基础', 'public-elective', 32, 0, 2, [3], [], ['S_STD']),
        course('E6', '人工智能伦理', 'public-elective', 16, 0, 1, [4], [], ['S_STD']),
    ]
    prof_base = [
        course('B1', '程序设计基础', 'professional-base', 48, 32, 5, [1], [('C-DEV-1', 'H')]),
        course('B2', '数据库技术', 'professional-base', 40, 40, 5, [2], [('C-DEV-2', 'H'), ('C-OPS-2', 'M')]),
        course('B3', 'Linux 操作系统', 'professional-base', 32, 48, 5, [2], [('C-OPS-1', 'H')]),
        course('B4', '计算机网络基础', 'professional-base', 40, 8, 3, [2], [('C-OPS-2', 'M')]),
        course('B5', 'Python 数据分析基础', 'professional-base', 32, 48, 5, [2], [('C-ANA-1', 'H')]),
    ]
    prof_core = [
        course('C1', 'Hadoop 大数据平台运维', 'professional-core', 40, 32, 4.5, [3], [('C-OPS-1', 'H'), ('C-OPS-2', 'M')]),
        course('C2', 'Spark 数据处理与编程', 'professional-core', 40, 32, 4.5, [3], [('C-DEV-1', 'H')]),
        course('C3', '数据仓库与 ETL 技术', 'professional-core', 40, 32, 4.5, [4], [('C-DEV-2', 'H')]),
        course('C4', '数据可视化技术', 'professional-core', 32, 40, 4.5, [4], [('C-ANA-1', 'H')]),
        course('C5', '流式数据实时处理', 'professional-core', 32, 32, 4, [4], [('C-DEV-1', 'M'), ('C-OPS-1', 'M')]),
        course('C6', '分布式数据库技术', 'professional-core', 32, 32, 4, [5], [('C-DEV-2', 'M'), ('C-ANA-1', 'M')]),
        course('C7', '大数据安全与运维监控', 'professional-core', 32, 32, 4, [5], [('C-OPS-1', 'M'), ('C-OPS-2', 'H')]),
    ]
    prof_ext = [
        course('X1', '人工智能导论', 'professional-extension', 24, 8, 2, [4], [('C-ANA-1', 'M')]),
        course('X2', '云计算基础', 'professional-extension', 24, 8, 2, [5], [('C-OPS-2', 'M')]),
        course('X3', '大数据治理概论', 'professional-extension', 24, 8, 2, [5], [('C-ANA-1', 'M')]),
        course('X4', '1+X 证书综合实训', 'professional-extension', 0, 32, 1.5, [5], [('C-DEV-2', 'M')]),
    ]
    comp_practice = [
        {'id': 'Z1', 'name': '程序设计综合实训', 'category': 'comprehensive-practice',
         'theoryHours': 0, 'practiceHours': 56, 'credits': 2.5, 'semesters': [2], 'assessment': '考查',
         'domains': [{'capabilityId': 'C-DEV-1', 'level': 'H'}],
         'rationale': {'text': '衔接程序设计岗位任务', 'metricIds': ['M_POS'], 'sourceIds': []}},
        {'id': 'Z2', 'name': '数据平台运维综合实训', 'category': 'comprehensive-practice',
         'theoryHours': 0, 'practiceHours': 56, 'credits': 2.5, 'semesters': [4], 'assessment': '考查',
         'domains': [{'capabilityId': 'C-OPS-1', 'level': 'H'}],
         'rationale': {'text': '运维岗位任务综合演练', 'metricIds': ['M_POS'], 'sourceIds': []}},
        {'id': 'Z3', 'name': '数据处理综合项目实训', 'category': 'comprehensive-practice',
         'theoryHours': 0, 'practiceHours': 84, 'credits': 3.5, 'semesters': [5], 'assessment': '考查',
         'domains': [{'capabilityId': 'C-ANA-1', 'level': 'H'}, {'capabilityId': 'C-DEV-2', 'level': 'M'}],
         'rationale': {'text': '数据开发岗位综合项目', 'metricIds': ['M_POS'], 'sourceIds': []}},
        {'id': 'Z4', 'name': '毕业设计', 'category': 'comprehensive-practice',
         'theoryHours': 0, 'practiceHours': 168, 'credits': 7, 'semesters': [6], 'assessment': '答辩',
         'domains': [{'capabilityId': 'C-DEV-2', 'level': 'H'}],
         'rationale': {'text': '综合运用能力毕业考核', 'metricIds': [], 'sourceIds': ['S_STD']}},
    ]
    internship = [{'id': 'I1', 'name': '岗位实习', 'category': 'internship',
                   'theoryHours': 0, 'practiceHours': 624, 'credits': 28, 'semesters': [5, 6],
                   'assessment': '企业考核',
                   'domains': [{'capabilityId': 'C-OPS-2', 'level': 'H'}],
                   'rationale': {'text': '顶岗实习对接真实岗位', 'metricIds': [], 'sourceIds': ['S_STD']}}]
    semesters = [{'no': no, 'weeks': 20, 'activities': [{'name': '教学', 'weeks': 18}, {'name': '考试与机动', 'weeks': 2}]}
                 for no in range(1, 7)]
    return {
        'schema': 'training-program/1',
        'title': '大数据技术专业人才培养方案（2026 级·测试）',
        'status': 'draft', 'as_of': '2026-11-18',
        'meta': {
            'majorName': '大数据技术', 'majorCode': '510205', 'level': '高职专科',
            'duration': {'years': 3, 'maxYears': 5},
            'entryRequirement': '高中阶段学校毕业或具有同等学力',
            'region': '广东省', 'industries': ['数字经济'],
            'version': '2026-1',
            'basedOnStandard': {'name': '高等职业学校专业教学标准：大数据技术',
                                'sourceId': 'S_STD', 'status': 'verified'},
        },
        'sources': [
            {'id': 'S_Q', 'title': '区域岗位统计（测试）', 'publisher': '人才数据库',
             'url': 'data/tq-test0001/result.json', 'published': '未标注', 'accessed': '2026-11-10',
             'locator': 'cohort all', 'scope': '广东省·数字经济产业链·在招岗位',
             'excerpt': '去重岗位计数与学历分布'},
            {'id': 'S_STD', 'title': '专业教学标准原文（用户提供）', 'publisher': '用户提供',
             'url': 'user:专业教学标准', 'published': '未标注', 'accessed': '2026-11-17',
             'locator': '职业面向节', 'scope': '大数据技术专业教学标准',
             'excerpt': '面向数据工程技术人员等职业群'},
            {'id': 'S_USER', 'title': '办学条件说明', 'publisher': '用户提供',
             'url': 'user:办学条件说明', 'published': '未标注', 'accessed': '2026-11-17',
             'locator': '师资节', 'scope': '本校师资', 'excerpt': '现有专任教师 12 人，其中双师型 6 人'},
        ],
        'metrics': [
            {'id': 'M_POS', 'label': '区域在招岗位数', 'unit': '个', 'period': '查询时点', 'region': '广东省',
             'population': '数字经济产业链在招岗位', 'definition': '去重岗位计数', 'source_ids': ['S_Q'],
             'binding': {'metricId': 'all/positions.count', 'field': 'value'}},
            {'id': 'M_SAL', 'label': '岗位薪酬中位数', 'unit': 'K_CNY/月', 'period': '查询时点',
             'region': '广东省', 'population': '同上', 'definition': '声明区间中位数', 'source_ids': ['S_Q'],
             'binding': {'metricId': 'all/salary.summary', 'field': 'value.median'}},
            {'id': 'M_EDU', 'label': '学历分布', 'unit': '个', 'period': '查询时点', 'region': '广东省',
             'population': '同上', 'definition': '按学历计数分布', 'source_ids': ['S_Q'],
             'binding': {'metricId': 'all/education.distribution', 'field': 'rows'}},
        ],
        'jobGroups': [{
            'id': 'JG1', 'name': '数据平台运维与开发', 'summary': '区域岗位量支撑的主岗位群',
            'positions': [
                {'name': '大数据运维工程师', 'stage': 'entry', 'metricIds': ['M_POS'], 'sourceIds': []},
                {'name': '数据开发工程师', 'stage': 'development', 'metricIds': ['M_POS'], 'sourceIds': []},
            ],
            'workTasks': [
                {'id': 'WT1', 'name': '集群部署与监控', 'capabilityIds': ['C-OPS-1', 'C-OPS-2']},
                {'id': 'WT2', 'name': '数据管道开发', 'capabilityIds': ['C-DEV-1', 'C-DEV-2']},
            ],
        }],
        'capabilityDomains': [
            {'id': 'CD-OPS', 'name': '平台运维能力域', 'capabilities': [
                {'id': 'C-OPS-1', 'name': '能完成集群部署与基础调优',
                 'evidence': {'status': 'verified', 'metricIds': ['M_POS'], 'sourceIds': []}},
                {'id': 'C-OPS-2', 'name': '能执行平台监控与故障处理',
                 'evidence': {'status': 'verified', 'metricIds': [], 'sourceIds': ['S_STD']}},
            ]},
            {'id': 'CD-DEV', 'name': '数据开发能力域', 'capabilities': [
                {'id': 'C-DEV-1', 'name': '能编写数据处理程序',
                 'evidence': {'status': 'verified', 'metricIds': ['M_POS'], 'sourceIds': []}},
                {'id': 'C-DEV-2', 'name': '能构建数据仓库与 ETL 流程',
                 'evidence': {'status': 'verified', 'metricIds': ['M_EDU'], 'sourceIds': []}},
            ]},
            {'id': 'CD-ANA', 'name': '数据分析能力域', 'capabilities': [
                {'id': 'C-ANA-1', 'name': '能完成数据清洗与可视化分析',
                 'evidence': {'status': 'verified', 'metricIds': ['M_SAL'], 'sourceIds': []}},
            ]},
        ],
        'standards': [
            {'element': '职业面向', 'content': '面向数据工程技术人员等职业群',
             'sourceId': 'S_STD', 'status': 'verified', 'note': '原文核对'},
            {'element': '培养目标', 'content': '培养德智体美劳全面发展的高素质技术技能人才',
             'sourceId': 'S_STD', 'status': 'verified', 'note': '原文核对'},
            {'element': '课程设置及学时安排', 'content': '专业核心课程 6—8 门',
             'sourceId': 'S_STD', 'status': 'verified', 'note': '原文核对'},
        ],
        'cultivation': {
            'goal': '培养德智体美劳全面发展，服务区域数字经济的大数据平台运维与开发高素质技术技能人才。',
            'goalBasis': {'standardSourceId': 'S_STD', 'metricIds': ['M_POS'],
                          'note': '标准目标结合区域岗位证据'},
            'spec': [
                {'dimension': '素质', 'items': [{'text': '坚定理想信念，践行社会主义核心价值观',
                                                'sourceIds': ['S_STD']}]},
                {'dimension': '知识', 'items': [{'text': '掌握分布式存储基本知识', 'capabilityId': 'C-OPS-1'}]},
                {'dimension': '能力', 'items': [{'text': '能完成集群部署与调优', 'capabilityId': 'C-OPS-1'}]},
            ],
        },
        'curriculum': {'courses': public_required + public_elective + prof_base + prof_core
                       + prof_ext + comp_practice + internship},
        'schedule': {'semesters': semesters,
                     'internship': {'seminars': [5, 6], 'weeks': 26, 'note': '第5-6学期集中安排'}},
        'assurance': {
            'faculty': {'status': 'supported', 'text': '现有专任教师 12 人，其中双师型 6 人',
                        'sourceIds': ['S_USER']},
            'facilities': {'status': 'pending', 'text': '', 'sourceIds': []},
            'cooperation': {'status': 'pending', 'text': '', 'sourceIds': []},
        },
        'graduation': {'requirements': ['思想品德考核合格', '修满毕业要求学分', '完成岗位实习'],
                       'minCredits': 149.5},
        'decisions': [],
    }


class ProgramTests(unittest.TestCase):
    def validate(self, d):
        with patch.object(program, 'inspect_source', fake_inspect):
            return program.validate(d)

    def setUp(self):
        self.d = fixture()

    def test_fixture_passes_all_redlines(self):
        result = self.validate(self.d)
        self.assertEqual(result['errors'], [])
        computed = result['computed']
        self.assertEqual(computed['totalHours'], 2716)
        self.assertEqual(computed['totalCredits'], 149.5)
        self.assertEqual(computed['coreCourses'], 7)
        self.assertGreaterEqual(computed['practiceRatio'], 0.5)
        self.assertGreaterEqual(computed['publicRatio'], 0.25)
        self.assertGreaterEqual(computed['electiveRatio'], 0.10)

    def test_binding_fills_and_verifies(self):
        result = self.validate(self.d)
        self.assertEqual(result['errors'], [])
        metrics = {m['id']: m for m in self.d['metrics']}
        self.assertEqual(metrics['M_POS']['value'], 123)
        self.assertEqual(metrics['M_SAL']['value'], 9.5)
        self.assertEqual(metrics['M_EDU']['value'], 123)
        self.assertEqual(metrics['M_EDU']['breakdown']['groups'][0]['label'], '大专/高职')

    def test_hand_typed_value_rejected(self):
        self.d['metrics'][0]['value'] = 999
        result = self.validate(self.d)
        self.assertTrue(any('differs from query result' in e for e in result['errors']))

    def test_practice_ratio_blocks(self):
        internship = next(c for c in self.d['curriculum']['courses'] if c['id'] == 'I1')
        internship['category'] = 'professional-extension'
        internship['practiceHours'], internship['theoryHours'] = 0, 624
        result = self.validate(self.d)
        self.assertTrue(any('R2' in e for e in result['errors']))

    def test_core_course_count_blocks(self):
        core = [c for c in self.d['curriculum']['courses'] if c['category'] == 'professional-core']
        core[-1]['category'] = 'professional-extension'
        core[-2]['category'] = 'professional-extension'
        result = self.validate(self.d)
        self.assertTrue(any('R5' in e for e in result['errors']))

    def test_weeks_per_year_blocks(self):
        self.d['schedule']['semesters'][0]['weeks'] = 18
        self.d['schedule']['semesters'][0]['activities'][0]['weeks'] = 16
        result = self.validate(self.d)
        self.assertTrue(any('R7' in e for e in result['errors']))

    def test_internship_weeks_block(self):
        self.d['schedule']['internship']['weeks'] = 15
        result = self.validate(self.d)
        self.assertTrue(any('R6' in e for e in result['errors']))

    def test_total_hours_bounds_block(self):
        for c in self.d['curriculum']['courses']:
            c['semesters'] = c['semesters'][:1]
        c = next(c for c in self.d['curriculum']['courses'] if c['id'] == 'I1')
        c['practiceHours'] = 400
        c['credits'] = 17
        result = self.validate(self.d)
        self.assertTrue(any('R1' in e for e in result['errors']))

    def test_credit_conversion_blocks(self):
        for c in self.d['curriculum']['courses']:
            c['credits'] = round(c['credits'] * 0.8, 1)
        result = self.validate(self.d)
        self.assertTrue(any('R8' in e for e in result['errors']))

    def test_elective_ratio_blocks(self):
        self.d['curriculum']['courses'] = [c for c in self.d['curriculum']['courses']
                                           if c['id'] not in ('E1', 'E2', 'E3', 'E4', 'E5', 'E6')]
        result = self.validate(self.d)
        self.assertTrue(any('R4' in e for e in result['errors']))

    def test_capability_without_course_support_blocks(self):
        self.d['capabilityDomains'][0]['capabilities'].append(
            {'id': 'C-OPS-9', 'name': '孤立能力项', 'evidence': {'status': 'verified', 'metricIds': ['M_POS'],
                                                              'sourceIds': []}})
        result = self.validate(self.d)
        self.assertTrue(any('R12' in e for e in result['errors']))

    def test_single_course_support_warns_only(self):
        for c in self.d['curriculum']['courses']:
            c['domains'] = [r for r in c.get('domains', []) if r['capabilityId'] != 'C-ANA-1']
        core = next(c for c in self.d['curriculum']['courses'] if c['id'] == 'B5')
        core['domains'] = [{'capabilityId': 'C-ANA-1', 'level': 'H'}]
        result = self.validate(self.d)
        self.assertFalse(any('R12' in e for e in result['errors']))
        self.assertTrue(any('C-ANA-1 仅 1 门' in w for w in result['warnings']))

    def test_insufficient_capability_requires_decision(self):
        cap = self.d['capabilityDomains'][0]['capabilities'][0]
        cap['evidence'] = {'status': 'insufficient', 'metricIds': [], 'sourceIds': []}
        result = self.validate(self.d)
        self.assertTrue(any('insufficient' in e for e in result['errors']))
        self.d['decisions'] = [{'id': 'D1', 'question': '样本量不足如何处理？',
                                'userReply': '按现有证据继续', 'scope': 'evidence'}]
        result = self.validate(self.d)
        self.assertFalse(any('insufficient' in e for e in result['errors']))

    def test_pending_standard_requires_decision_and_blocks_final(self):
        self.d['standards'].append({'element': '教学条件', 'content': '', 'sourceId': 'S_STD',
                                    'status': 'pending', 'note': '未取得原文'})
        self.d['meta']['basedOnStandard']['status'] = 'verified'
        result = self.validate(self.d)
        self.assertTrue(any('pending 标准缺少用户继续决策' in e for e in result['errors']))
        self.d['decisions'] = [{'id': 'D1', 'question': '教学条件要素无原文，是否按待核对继续？',
                                'userReply': '按待核对继续', 'scope': 'standards'}]
        result = self.validate(self.d)
        self.assertFalse(any('pending' in e for e in result['errors']))
        self.d['status'] = 'final'
        result = self.validate(self.d)
        self.assertTrue(any('final 方案不得有待核对标准' in e for e in result['errors']))

    def test_rationale_must_bind_evidence(self):
        core = next(c for c in self.d['curriculum']['courses'] if c['id'] == 'C1')
        core['rationale'] = {'text': '重要课程', 'metricIds': [], 'sourceIds': []}
        result = self.validate(self.d)
        self.assertTrue(any('rationale 须绑定' in e for e in result['errors']))

    def test_user_quote_authenticity(self):
        self.d['decisions'] = [{'id': 'D1', 'question': '是否采用订单班约束？',
                                'userReply': '采用华为订单班', 'scope': 'curriculum'}]
        earlier = ['面向数据工程技术人员等职业群', '现有专任教师 12 人，其中双师型 6 人']
        context = {'message': '采用华为订单班', 'earlierMessages': earlier, 'uploads': []}
        with patch.object(program, 'inspect_source', fake_inspect), \
                patch.object(program, 'session_context', return_value=context):
            result = program.validate(self.d)
        self.assertFalse(result['errors'])
        self.d['decisions'][0]['userReply'] = '采用百度订单班'
        with patch.object(program, 'inspect_source', fake_inspect), \
                patch.object(program, 'session_context', return_value=context):
            result = program.validate(self.d)
        self.assertTrue(any('userReply 须引用用户原话' in e for e in result['errors']))

    def test_degraded_standards_path_needs_no_standard_source(self):
        """标准原文不可得（已决策继续）时：pending 条目免 sourceId、goalBasis 免 standardSourceId。"""
        self.d['decisions'] = [{'id': 'D1', 'question': '标准原文不可得，是否按待核对继续？',
                                'userReply': '按待核对继续', 'scope': 'standards'}]
        self.d['meta']['basedOnStandard'] = {'status': 'pending'}
        self.d['standards'] = [{'element': '职业面向', 'status': 'pending', 'note': '未取得原文'}]
        self.d['sources'] = [s for s in self.d['sources'] if s['id'] != 'S_STD']
        # 移除对标准来源的引用：能力项、课程 rationale、规格条目改绑查询/岗位证据
        for cap in [c for dom in self.d['capabilityDomains'] for c in dom['capabilities']]:
            if 'S_STD' in (cap['evidence'].get('sourceIds') or []):
                cap['evidence']['sourceIds'] = []
                cap['evidence']['metricIds'] = ['M_POS']
                cap['evidence']['status'] = 'verified'
        for c in self.d['curriculum']['courses']:
            c['rationale']['sourceIds'] = [s for s in c['rationale'].get('sourceIds', []) if s != 'S_STD']
            if not c['rationale']['metricIds'] and not c['rationale']['sourceIds']:
                c['rationale']['metricIds'] = ['M_POS']
        for dim in self.d['cultivation']['spec']:
            for item in dim['items']:
                item['sourceIds'] = [s for s in item.get('sourceIds', []) if s != 'S_STD'] or None
                if item['sourceIds'] is None:
                    item.pop('sourceIds')
        self.d['cultivation']['goalBasis'] = {'metricIds': ['M_POS'], 'note': '标准待核对，目标先按区域证据拟定'}
        result = self.validate(self.d)
        self.assertEqual(result['errors'], [])
        self.d['status'] = 'final'
        result = self.validate(self.d)
        self.assertTrue(any('final 方案不得有待核对标准' in e for e in result['errors']))

    def test_user_source_excerpt_verified(self):
        earlier = ['面向数据工程技术人员等职业群', '现有专任教师 12 人，其中双师型 6 人']
        context = {'message': '', 'earlierMessages': earlier, 'uploads': []}
        with patch.object(program, 'inspect_source', fake_inspect), \
                patch.object(program, 'session_context', return_value=context):
            result = program.validate(self.d)
        self.assertFalse(result['errors'])
        source = next(s for s in self.d['sources'] if s['id'] == 'S_STD')
        source['excerpt'] = '面向人工智能工程技术人员等职业群'
        with patch.object(program, 'inspect_source', fake_inspect), \
                patch.object(program, 'session_context', return_value=context):
            result = program.validate(self.d)
        self.assertTrue(any('excerpt 须引用用户原句' in e for e in result['errors']))


class BuildTests(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.prev = Path.cwd()
        import os
        os.chdir(self.cwd)
        self.d = fixture()
        (self.cwd / 'program.json').write_text(json.dumps(self.d, ensure_ascii=False), encoding='utf-8')

    def tearDown(self):
        import os
        os.chdir(self.prev)
        self.tmp.cleanup()

    def test_build_produces_all_outputs(self):
        with patch.object(program, 'inspect_source', fake_inspect):
            code = program.build(self.cwd / 'program.json')
        self.assertEqual(code, 0)
        out = next((self.cwd / 'output').iterdir())
        for name in ('program.md', 'program.json', 'validation.json', 't05-package.json',
                     't05-overview.md', 'program.docx', 'program-files.json'):
            self.assertTrue((out / name).is_file(), name)
        validation = json.loads((out / 'validation.json').read_text())
        self.assertEqual(validation['errors'], [])
        self.assertTrue(all(row[2] == '通过' for row in validation['redlines']))
        md = (out / 'program.md').read_text()
        for section in ('一、专业名称及代码', '四、职业面向', '七、学时安排', '附录A 证据与口径',
                        '附录B 能力—课程支撑矩阵', '附录C 待核对与未决清单'):
            self.assertIn(section, md)
        package = json.loads((out / 't05-package.json').read_text())
        self.assertEqual(package['schema'], 't05-course-development/1')
        self.assertEqual(len(package['tasks']), len(self.d['curriculum']['courses']))
        self.assertIn('M_POS', package['evidenceIndex']['metrics'])
        manifest = json.loads((out / 'program-files.json').read_text())
        import hashlib
        for item in manifest['files']:
            self.assertEqual(hashlib.sha256((self.cwd / item['path']).read_bytes()).hexdigest(),
                             item['sha256'])
        self.assertIn(('培养方案Word版', 'program.docx'),
                      [(f['name'], Path(f['path']).name) for f in manifest['files']])

    def test_docx_is_wellformed_package(self):
        with patch.object(program, 'inspect_source', fake_inspect):
            self.assertEqual(program.build(self.cwd / 'program.json'), 0)
        out = next((self.cwd / 'output').iterdir())
        with zipfile.ZipFile(out / 'program.docx') as archive:
            names = set(archive.namelist())
            for required in ('[Content_Types].xml', '_rels/.rels', 'word/document.xml',
                             'word/styles.xml', 'docProps/core.xml'):
                self.assertIn(required, names)
            for name in names:
                if name.endswith('.xml') or name.endswith('.rels'):
                    minidom.parseString(archive.read(name))
            document = archive.read('word/document.xml').decode()
        self.assertIn('Hadoop 大数据平台运维', document)
        self.assertIn('附录A 证据与口径', document)

    def test_build_without_docx_flags_fallback(self):
        with patch.object(program, 'inspect_source', fake_inspect):
            self.assertEqual(program.build(self.cwd / 'program.json', skip_docx=True), 0)
        out = next((self.cwd / 'output').iterdir())
        self.assertFalse((out / 'program.docx').exists())
        validation = json.loads((out / 'validation.json').read_text())
        self.assertTrue(any('Word 版未生成' in w for w in validation['warnings']))

    def test_build_blocked_by_redline(self):
        d = json.loads((self.cwd / 'program.json').read_text())
        core = next(c for c in d['curriculum']['courses'] if c['id'] == 'C1')
        core['theoryHours'] = 5000
        (self.cwd / 'program.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        with patch.object(program, 'inspect_source', fake_inspect):
            code = program.build(self.cwd / 'program.json')
        self.assertEqual(code, 1)
        self.assertFalse((self.cwd / 'output').exists())


if __name__ == '__main__':
    unittest.main()
