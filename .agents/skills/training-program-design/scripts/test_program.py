"""Offline regression tests for program contracts, redlines and build outputs."""
import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.dom import minidom

import program

REAL_CORPUS_DIR = program.CORPUS_DIR
CORPUS_TEXT = ('人工智能技术应用专业人才培养方案\n一、培养目标\n'
               '本专业培养德智体美劳全面发展，掌握人工智能基础理论与技术应用的高素质技术技能人才。\n'
               '七、学时安排\n总学时 2600，其中实践学时 1560，占总学时 60%，公共基础课 700 学时。\n')


def make_corpus(tmp):
    """构造临时语料库：索引.csv + 三份样例 TXT（满足语料≥3 门槛）。"""
    root = Path(tmp) / 'corpus'
    (root / '人工智能').mkdir(parents=True)
    import hashlib as _h
    rows = ['方向分类,文件名,相对路径,字节数,sha256,标题,定位方式,来源批次,来源txt路径\r\n']
    for i in (1, 2, 3):
        body = (CORPUS_TEXT + f'样本 {i} 附注内容。\n').encode('utf-8')
        (root / '人工智能' / f'sample{i}.txt').write_bytes(body)
        rows.append(f'人工智能,sample{i}.txt,人才培养方案/人工智能/sample{i}.txt,{len(body)},'
                    f'{_h.sha256(body).hexdigest()},同类方案样例{i},同名txt,第三批,源路径\r\n')
    (root / '索引.csv').write_bytes(b'\xef\xbb\xbf' + ''.join(rows).encode('utf-8'))
    return root


def corpus_sources():
    """三份语料来源（excerpt 逐字取语料原文句）。"""
    excerpt = '本专业培养德智体美劳全面发展，掌握人工智能基础理论与技术应用的高素质技术技能人才'
    return [{'id': f'S_CP{i}', 'title': '', 'publisher': '',
             'url': f'corpus:人工智能/sample{i}.txt', 'published': '', 'accessed': '',
             'locator': '一、培养目标', 'scope': f'对标样例{i}', 'excerpt': excerpt}
            for i in (1, 2, 3)]


def with_corpus(test):
    """把语料根切到临时目录并清空索引缓存。"""
    def wrapper(self):
        tmp = tempfile.mkdtemp()
        root = make_corpus(tmp)
        original_dir, original_rows = program.CORPUS_DIR, program._corpus_rows
        program.CORPUS_DIR, program._corpus_rows = root, None
        try:
            return test(self)
        finally:
            program.CORPUS_DIR, program._corpus_rows = original_dir, original_rows
            shutil.rmtree(tmp, ignore_errors=True)
    return wrapper

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
        'description': f'{name}：本课程系统讲授核心概念、主流工具与工程方法，结合企业真实案例'
                       f'开展任务式训练，培养学生独立完成相关典型工作任务的综合职业能力。',
        'typicalContent': f'围绕岗位典型任务组织模块化教学：任务需求分析与方案设计、环境搭建与配置、'
                          f'核心功能实现、测试验证与性能调优、文档编制与成果汇报，'
                          f'按企业工作过程完成全流程训练并形成可交付的实践成果。',
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
         'description': '以完整项目为载体综合运用程序设计知识，训练工程规范与协作能力。',
         'typicalContent': '领取项目任务书，完成需求分析、模块划分、编码实现、联调测试与答辩汇报。',
         'domains': [{'capabilityId': 'C-DEV-1', 'level': 'H'}],
         'rationale': {'text': '衔接程序设计岗位任务', 'metricIds': ['M_POS'], 'sourceIds': []}},
        {'id': 'Z2', 'name': '数据平台运维综合实训', 'category': 'comprehensive-practice',
         'theoryHours': 0, 'practiceHours': 56, 'credits': 2.5, 'semesters': [4], 'assessment': '考查',
         'description': '在真实集群环境完成平台部署、监控与故障处置的综合演练。',
         'typicalContent': '分组完成集群规划、安装部署、监控告警配置、故障注入与排查、运维报告编写。',
         'domains': [{'capabilityId': 'C-OPS-1', 'level': 'H'}],
         'rationale': {'text': '运维岗位任务综合演练', 'metricIds': ['M_POS'], 'sourceIds': []}},
        {'id': 'Z3', 'name': '数据处理综合项目实训', 'category': 'comprehensive-practice',
         'theoryHours': 0, 'practiceHours': 84, 'credits': 3.5, 'semesters': [5], 'assessment': '考查',
         'description': '围绕企业真实数据完成从采集到可视化的端到端数据处理项目。',
         'typicalContent': '数据采集与清洗、存储建模、批处理作业开发、可视化看板搭建与项目答辩。',
         'domains': [{'capabilityId': 'C-ANA-1', 'level': 'H'}, {'capabilityId': 'C-DEV-2', 'level': 'M'}],
         'rationale': {'text': '数据开发岗位综合项目', 'metricIds': ['M_POS'], 'sourceIds': []}},
        {'id': 'Z4', 'name': '毕业设计', 'category': 'comprehensive-practice',
         'theoryHours': 0, 'practiceHours': 168, 'credits': 7, 'semesters': [6], 'assessment': '答辩',
         'description': '综合运用所学知识完成企业真题或仿真课题的设计与实现。',
         'typicalContent': '选题开题、方案设计、系统实现、论文撰写与公开答辩，全程按工程规范执行。',
         'domains': [{'capabilityId': 'C-DEV-2', 'level': 'H'}],
         'rationale': {'text': '综合运用能力毕业考核', 'metricIds': [], 'sourceIds': ['S_STD']}},
    ]
    internship = [{'id': 'I1', 'name': '岗位实习', 'category': 'internship',
                   'theoryHours': 0, 'practiceHours': 624, 'credits': 28, 'semesters': [5, 6],
                   'assessment': '企业考核',
                   'description': '在校企共建实习基地顶岗实践，在师傅指导下承担真实岗位工作。',
                   'typicalContent': '按企业岗位规程完成日常工作任务，撰写实习周记与总结，参加企业考核。',
                   'domains': [{'capabilityId': 'C-OPS-2', 'level': 'H'}],
                   'rationale': {'text': '顶岗实习对接真实岗位', 'metricIds': [], 'sourceIds': ['S_STD']}}]
    semesters = [{'no': no, 'weeks': 20, 'activities': [{'name': '教学', 'weeks': 18}, {'name': '考试与机动', 'weeks': 2}]}
                 for no in range(1, 7)]
    return {
        'schema': 'training-program/1',
        'title': '大数据技术专业人才培养方案（2026 级·测试）',
        'status': 'draft', 'as_of': '2026-11-20',
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
            *corpus_sources(),
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
        }, {
            'id': 'JG2', 'name': '数据分析与应用', 'summary': '数据价值化岗位群',
            'positions': [
                {'name': '数据分析师', 'stage': 'entry', 'metricIds': ['M_POS'], 'sourceIds': []},
                {'name': '数据运营主管', 'stage': 'development', 'metricIds': [], 'sourceIds': ['S_STD']},
            ],
            'workTasks': [
                {'id': 'WT3', 'name': '数据分析与可视化', 'capabilityIds': ['C-ANA-1']},
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
                {'dimension': '素质', 'items': [
                    {'text': '坚定理想信念，践行社会主义核心价值观，具有社会责任感', 'sourceIds': ['S_STD']},
                    {'text': '遵守职业道德与行业规范，具备爱岗敬业和精益求精的工匠精神', 'sourceIds': ['S_STD']},
                    {'text': '具备良好的身体素质与心理调适能力，养成终身学习习惯', 'sourceIds': ['S_STD']},
                    {'text': '具有团队协作与沟通表达能力，尊重劳动、尊重创造', 'sourceIds': ['S_STD']},
                    {'text': '树立安全与保密意识，遵守数据安全法律法规要求', 'sourceIds': ['S_STD']},
                ]},
                {'dimension': '知识', 'items': [
                    {'text': '掌握程序设计、数据库与网络等信息技术基础知识', 'capabilityId': 'C-DEV-1'},
                    {'text': '掌握分布式存储与计算平台的基本原理和体系结构', 'capabilityId': 'C-OPS-1'},
                    {'text': '掌握数据仓库、ETL 与数据治理的基本方法', 'capabilityId': 'C-DEV-2'},
                    {'text': '熟悉数据分析与可视化的常用算法和工具', 'capabilityId': 'C-ANA-1'},
                    {'text': '了解相关国家标准、行业规范与信息安全要求', 'capabilityId': 'C-OPS-2'},
                ]},
                {'dimension': '能力', 'items': [
                    {'text': '能完成大数据平台的部署、配置与基础调优', 'capabilityId': 'C-OPS-1'},
                    {'text': '能编写数据处理程序并完成批处理作业开发', 'capabilityId': 'C-DEV-1'},
                    {'text': '能构建数据仓库并实施 ETL 数据集成流程', 'capabilityId': 'C-DEV-2'},
                    {'text': '能完成数据清洗、统计分析与可视化呈现', 'capabilityId': 'C-ANA-1'},
                    {'text': '能执行平台监控、告警处置与常规故障排查', 'capabilityId': 'C-OPS-2'},
                ]},
            ],
        },
        'pedagogy': {
            'teachingImplementation': '推行"岗位导向、项目载体"的教学模式，按典型工作任务重构教学内容，'
                                      '采用项目教学法、任务驱动法与案例教学法组织课堂教学；理论实践一体化，'
                                      '专业核心课程全部在实训室以真实或仿真环境开展；推行线上线下混合式教学，'
                                      '依托校内实训基地与企业实习基地分段实施教学，企业导师全程参与'
                                      '实践教学环节并共同制定项目任务书，实现教、学、做有机融合。',
            'assessment': '构建过程性考核与结果性考核相结合的多元评价体系：课程考核由平时表现、'
                          '阶段任务与期末考核按比例构成，实践类课程以作品与项目成果为主要评价依据；'
                          '岗位实习由企业指导教师与校内导师按实习周记、任务完成与出勤共同评定；'
                          '积极推行以证代考与技能竞赛成绩认定学分，所有考核结果记入学业档案，'
                          '并作为教学诊断与持续改进的依据。',
        },
        'curriculum': {'courses': public_required + public_elective + prof_base + prof_core
                       + prof_ext + comp_practice + internship},
        'schedule': {'semesters': semesters,
                     'internship': {'seminars': [5, 6], 'weeks': 26, 'note': '第5-6学期集中安排'}},
        'assurance': {
            'faculty': {'status': 'supported',
                        'text': '现有专任教师 12 人，其中双师型 6 人，另有企业兼职教师 4 人，'
                                '生师比与高级职称占比符合办学要求',
                        'sourceIds': ['S_USER']},
            'facilities': {'status': 'pending', 'text': '', 'sourceIds': []},
            'cooperation': {'status': 'pending', 'text': '', 'sourceIds': []},
        },
        'graduation': {'requirements': ['在校期间思想品德考核合格，无违纪处分记录',
                                        '修满本方案规定的毕业要求学分且各课程考核合格',
                                        '完成岗位实习并取得企业考核合格及以上成绩',
                                        '获得至少 1 项职业技能等级证书或同等行业认证'],
                       'minCredits': 149.5},
        'decisions': [],
        'chartPlan': [
            {'id': 'F_SPEC', 'question': '各门课程支撑哪些能力域、强度如何？', 'kind': 'matrix',
             'reason': '课程×能力域交叉支撑关系，矩阵呈现最高支撑强度（0=无支撑）',
             'section': '附录B 能力—课程支撑矩阵', 'dataOrigin': 'program',
             'dataRefs': {'fromProgram': ['curriculum.domains', 'capabilityDomains']}},
            {'id': 'F_HOURS', 'question': '逐学期理论与实践学时占比如何递进？', 'kind': 'grouped-line',
             'reason': '学期是有序坐标，两条线看实践占比的递进节奏', 'section': '七、学时安排',
             'dataOrigin': 'program', 'dataRefs': {'fromProgram': ['curriculum.courses', 'schedule']}},
            {'id': 'F_EDU', 'question': '区域岗位的学历要求如何分布？', 'kind': 'barh',
             'reason': '学历类别为长标签，横向排名便于阅读', 'section': '四、职业面向',
             'dataOrigin': 'query', 'dataRefs': {'metricIds': ['M_EDU']}},
            {'id': 'F_SAL', 'question': '不同学历要求岗位的薪酬分位区间相差多少？', 'kind': 'interval',
             'reason': '按学历分组的 P25–P75 分位区间比较', 'section': '四、职业面向',
             'dataOrigin': 'query', 'dataRefs': {'metricIds': ['M_SAL']}},
        ],
    }


class ProgramTests(unittest.TestCase):
    def validate(self, d):
        with patch.object(program, 'inspect_source', fake_inspect):
            return program.validate(d)

    def setUp(self):
        self.d = fixture()
        # 夹具含 3 份 corpus: 来源，全部用例统一挂临时语料库
        self._corpus_tmp = tempfile.mkdtemp()
        self._corpus_prev = (program.CORPUS_DIR, program._corpus_rows)
        program.CORPUS_DIR, program._corpus_rows = make_corpus(self._corpus_tmp), None

    def tearDown(self):
        program.CORPUS_DIR, program._corpus_rows = self._corpus_prev
        shutil.rmtree(self._corpus_tmp, ignore_errors=True)

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
        # 移除对标准来源的引用：岗位、能力项、课程 rationale、规格条目改绑查询/岗位证据
        for group in self.d['jobGroups']:
            for pos in group['positions']:
                pos['sourceIds'] = [s for s in pos.get('sourceIds', []) if s != 'S_STD']
                if not pos.get('metricIds') and not pos['sourceIds']:
                    pos['metricIds'] = ['M_POS']
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

    def test_corpus_sources_backfilled_from_index(self):
        result = self.validate(self.d)
        self.assertEqual(result['errors'], [])
        src = next(s for s in self.d['sources'] if s['id'] == 'S_CP1')
        self.assertEqual(src['title'], '同类方案样例1')
        self.assertEqual(src['accessed'], program.CORPUS_SNAPSHOT)
        self.assertEqual(src['publisher'], '本地培养方案语料库（对标参考）')

    def test_corpus_source_rejects_missing_entry_and_bad_excerpt(self):
        self.d['sources'].append({'id': 'S_CPX', 'title': 'x', 'publisher': 'x', 'url': 'corpus:人工智能/无此文件.txt',
                                  'published': '未标注', 'accessed': '2026-11-20', 'locator': '', 'scope': '',
                                  'excerpt': '任意'})
        result = self.validate(self.d)
        self.assertTrue(any('corpus 索引中无此条目' in e for e in result['errors']))
        self.d['sources'][-1].update({'id': 'S_CPY', 'url': 'corpus:人工智能/sample1.txt',
                                      'excerpt': '这句话不在语料原文中'})
        result = self.validate(self.d)
        self.assertTrue(any('excerpt 须摘录语料原文' in e for e in result['errors']))

    def test_corpus_source_detects_tampered_file(self):
        body = (CORPUS_TEXT + '样本 1 附注内容。\n被篡改的正文\n').encode('utf-8')
        (program.CORPUS_DIR / '人工智能' / 'sample1.txt').write_bytes(body)  # 索引保持旧 sha
        result = self.validate(self.d)
        self.assertTrue(any('sha256 与索引不符' in e for e in result['errors']))

    def test_corpus_minimum_three_blocks(self):
        self.d['sources'] = [s for s in self.d['sources']
                             if not (s.get('url', '').startswith('corpus:') and s['id'] != 'S_CP1')]
        result = self.validate(self.d)
        self.assertTrue(any('对标语料仅 1 份' in e for e in result['errors']))

    def test_course_description_floor_blocks(self):
        core = next(c for c in self.d['curriculum']['courses'] if c['id'] == 'C1')
        core['description'] = '太短'
        result = self.validate(self.d)
        self.assertTrue(any('课程简介不足' in e for e in result['errors']))
        pub = next(c for c in self.d['curriculum']['courses'] if c['id'] == 'P1')
        pub['description'] = ''
        result = self.validate(self.d)
        self.assertTrue(any(f'P1' in e and '课程简介不足' in e for e in result['errors']))

    def test_core_typical_content_floor_blocks(self):
        core = next(c for c in self.d['curriculum']['courses'] if c['id'] == 'C1')
        core['typicalContent'] = '内容太少不足以支撑核心课要求'
        result = self.validate(self.d)
        self.assertTrue(any('典型教学内容/工作任务不足 80' in e for e in result['errors']))

    def test_spec_dimension_floor_blocks(self):
        self.d['cultivation']['spec'][0]['items'] = self.d['cultivation']['spec'][0]['items'][:2]
        result = self.validate(self.d)
        self.assertTrue(any('培养规格「素质」仅 2 条' in e for e in result['errors']))

    def test_pedagogy_floor_blocks(self):
        self.d['pedagogy']['teachingImplementation'] = '按项目教学。'
        result = self.validate(self.d)
        self.assertTrue(any('教学实施' in e and '不足 150 字' in e for e in result['errors']))

    def test_graduation_floor_blocks(self):
        self.d['graduation']['requirements'] = ['合格', '修满学分']
        result = self.validate(self.d)
        self.assertTrue(any('毕业要求仅 2 条' in e for e in result['errors']))

    def test_jobgroup_stage_coverage_blocks(self):
        for group in self.d['jobGroups']:
            for pos in group['positions']:
                pos['stage'] = 'entry'
        result = self.validate(self.d)
        self.assertTrue(any('须同时覆盖初始岗' in e for e in result['errors']))

    def test_category_coverage_blocks(self):
        self.d['curriculum']['courses'] = [c for c in self.d['curriculum']['courses']
                                           if c['category'] != 'public-elective']
        result = self.validate(self.d)
        self.assertTrue(any('缺少「公共选修」' in e for e in result['errors']))

    def test_real_corpus_index_integrity(self):
        """仓库内置语料库在位时：索引可读、抽三份文件 sha 一致、真实 corpus 来源可通过校验。"""
        if not (REAL_CORPUS_DIR / '索引.csv').is_file():
            self.skipTest('本地语料库未安装（data/人才培养方案 不存在）')
        prev = (program.CORPUS_DIR, program._corpus_rows)
        program.CORPUS_DIR, program._corpus_rows = REAL_CORPUS_DIR, None
        try:
            rows = program.corpus_index()
            self.assertGreaterEqual(len(rows), 600)
            import hashlib
            picked = []
            for rel, row in rows.items():
                file = REAL_CORPUS_DIR / rel[len('人才培养方案/'):]
                if not file.is_file():
                    continue
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), row['sha256'])
                text = program.excerpt_text(file.read_text(encoding='utf-8', errors='replace'))
                m = re.search(r'[^\s。]{16,60}。', text)
                if m:
                    picked.append((rel, row, m.group(0)))
                if len(picked) == 3:
                    break
            self.assertEqual(len(picked), 3)
            self.d['sources'] = [s for s in self.d['sources'] if not s.get('url', '').startswith('corpus:')]
            for i, (rel, row, excerpt) in enumerate(picked, 1):
                self.d['sources'].append({'id': f'S_CP{i}', 'title': '', 'publisher': '',
                                          'url': 'corpus:' + rel[len('人才培养方案/'):],
                                          'published': '', 'accessed': '', 'locator': row.get('标题', ''),
                                          'scope': '对标结构', 'excerpt': excerpt})
            result = self.validate(self.d)
            self.assertEqual(result['errors'], [])
        finally:
            program.CORPUS_DIR, program._corpus_rows = prev

    # ---- 图表规划（先定图再取数）与链接式依据 ----

    def composed(self):
        result = self.validate(self.d)
        self.assertEqual(result['errors'], [])
        self.d['computed'] = result['computed']
        return program.compose_blocks(self.d)

    def test_chart_plan_required(self):
        self.d.pop('chartPlan')
        result = self.validate(self.d)
        self.assertTrue(any('chartPlan' in e for e in result['errors']))

    def test_chart_plan_family_gate(self):
        self.d['chartPlan'] = [dict(e, kind='bar') for e in fixture()['chartPlan']]
        result = self.validate(self.d)
        joined = '\n'.join(result['errors'])
        self.assertIn('图型家族', joined)
        self.assertIn('一半', joined)

    def test_chart_plan_two_families_blocks(self):
        self.d['chartPlan'] = [e for e in fixture()['chartPlan'] if e['id'] not in ('F_SAL', 'F_HOURS')]
        result = self.validate(self.d)
        self.assertTrue(any('至少 3 种完全不同的图型' in e for e in result['errors']))

    def test_chart_plan_kind_refs_and_section(self):
        plan = fixture()['chartPlan']
        plan[0]['kind'] = 'pie'
        plan[2]['dataRefs'] = {}
        plan[3]['section'] = '十三、不存在的章节'
        self.d['chartPlan'] = plan
        result = self.validate(self.d)
        joined = '\n'.join(result['errors'])
        self.assertIn('不在 figure/1 可执行集', joined)
        self.assertIn('须绑定 metricIds', joined)
        self.assertIn('不在正文章节中', joined)

    def test_body_uses_readable_links_not_ids(self):
        blocks = self.composed()
        body = []
        at_appendix = False
        for kind, payload in blocks:
            if kind == 'h2' and payload.startswith('附录'):
                at_appendix = True
            if not at_appendix:
                body.append(str(payload))
        text = '\n'.join(body)
        self.assertEqual(re.findall(r'(?:指标|来源|能力)[ \t]*[MSC][-_]', text), [])
        folded = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
        self.assertEqual(re.findall(r'(?<![A-Za-z0-9_-])[MSC][-_][A-Za-z0-9_-]+', folded), [])
        self.assertIn('](#M_POS)', text)
        self.assertIn('](#S_STD)', text)
        self.assertIn('](#C-OPS-1)', text)

    def test_page_blocks_anchors_cover_all_links(self):
        result = self.validate(self.d)
        self.d['computed'] = result['computed']
        blocks = program.page_blocks(self.d)

        def collect(items):
            texts, ids = [], []
            for b in items:
                if not isinstance(b, dict):
                    continue
                if b.get('id'):
                    ids.append(b['id'])
                for key in ('text', 'label'):
                    if b.get(key):
                        texts.append(str(b[key]))
                for it in b.get('items', []) if isinstance(b.get('items'), list) else []:
                    if it.get('id'):
                        ids.append(it['id'])
                    for key in ('label', 'text'):
                        if it.get(key):
                            texts.append(str(it[key]))
                if isinstance(b.get('blocks'), list):
                    sub_texts, sub_ids = collect(b['blocks'])
                    texts += sub_texts
                    ids += sub_ids
            return texts, ids

        texts, ids = collect(blocks)
        self.assertEqual(len(ids), len(set(ids)), '锚点 id 须全页唯一')
        for anchor in ids:
            self.assertTrue(program.ANCHOR_ID.fullmatch(anchor), f'锚点 id 不合规：{anchor}')
        targets = {m.group(1) for t in texts for m in re.finditer(r'\]\(#([^)]+)\)', t)}
        self.assertEqual(sorted(targets - set(ids)), [], '存在没有锚点落点的链接目标')
        for anchor in ('M_POS', 'M_SAL', 'C-OPS-1', 'S_STD'):
            self.assertIn(anchor, ids)

    def test_page_blocks_place_figures_per_plan(self):
        result = self.validate(self.d)
        self.d['computed'] = result['computed']
        blocks = program.page_blocks(self.d)

        def figure_specs(section):
            out = []
            for b in section.get('blocks', []):
                if b.get('type') == 'figure':
                    out.append(b['spec'])
                if isinstance(b.get('blocks'), list):
                    out += figure_specs(b)
            return out

        by_title = {b.get('title'): b for b in blocks if b.get('type') == 'section'}
        self.assertEqual(figure_specs(by_title['附录B 能力—课程支撑矩阵']), ['F_SPEC.json'])
        self.assertEqual(sorted(figure_specs(by_title['四、职业面向'])), ['F_EDU.json', 'F_SAL.json'])
        self.assertEqual(figure_specs(by_title['七、学时安排']), ['F_HOURS.json'])

    def test_program_chart_kinds_restricted(self):
        plan = fixture()['chartPlan']
        plan[1]['kind'] = 'bar'
        self.d['chartPlan'] = plan
        result = self.validate(self.d)
        self.assertTrue(any('program.py charts 生成规格' in e for e in result['errors']))

    def test_display_title_cleans_ordinals_and_extensions(self):
        self.assertEqual(program.display_title('5-2025级人工智能技术应用专业人才培养方案.pdf.'),
                         '2025级人工智能技术应用专业人才培养方案')
        self.assertEqual(program.display_title('3-2023级软件技术专业培养方案.txt'),
                         '2023级软件技术专业培养方案')
        self.assertEqual(program.display_title('2026级软件技术专业三年制人才培养方案'),
                         '2026级软件技术专业三年制人才培养方案')

    def test_support_matrix_spec_zero_means_no_support(self):
        result = self.validate(self.d)
        self.d['computed'] = result['computed']
        entry = next(e for e in self.d['chartPlan'] if e['id'] == 'F_SPEC')
        spec = program.support_matrix_spec(self.d, entry)
        bound = [c for c in self.d['curriculum']['courses'] if c.get('domains')]
        domains = [dom['name'].replace('能力域', '') for dom in self.d['capabilityDomains']]
        all_rows = [r for rows in spec['datasets'].values() for r in rows]
        # 每个课程×能力域组合都有已知取值：无支撑是 0，不是缺失
        self.assertEqual(len(all_rows), len(bound) * len(domains))
        self.assertTrue(all(r['强度'] in (0, 1, 2, 3) for r in all_rows))
        self.assertTrue(any(r['强度'] == 0 for r in all_rows))
        # 行标签用课程全称（不截断），列标签为能力域名去「能力域」后缀
        names = {c['name'] for c in bound}
        self.assertTrue({r['课程'] for r in all_rows} == names)
        for panel in spec['panels']:
            self.assertEqual(panel['fields'], {'row': '课程', 'column': '能力域', 'value': '强度'})
        self.assertIn('0=无支撑', spec['caption'])
        self.assertIn('未列入', spec['caption'])  # 未绑定能力域的公共课在图注说明
        # 面板每幅至多 7 行，避免高图占屏
        for key, rows in spec['datasets'].items():
            self.assertLessEqual(len({r['课程'] for r in rows}), 7)

    def test_semester_trend_spec_pairs(self):
        result = self.validate(self.d)
        self.d['computed'] = result['computed']
        entry = next(e for e in self.d['chartPlan'] if e['id'] == 'F_HOURS')
        spec = program.semester_trend_spec(self.d, entry)
        rows = spec['datasets']['学时占比']
        by_semester = {}
        for r in rows:
            by_semester.setdefault(r['学期'], {})[r['类型']] = r['占比']
        self.assertEqual(sorted(by_semester), [1, 2, 3, 4, 5, 6])
        for sem, pair in by_semester.items():
            self.assertEqual(sorted(pair), ['实践学时占比', '理论学时占比'])
            self.assertAlmostEqual(sum(pair.values()), 100.0, delta=0.2)

    def test_charts_command_writes_program_specs_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'program.json'
            path.write_text(json.dumps(self.d, ensure_ascii=False), encoding='utf-8')
            with patch.object(program, 'inspect_source', fake_inspect):
                self.assertEqual(program.charts(path, work=Path(tmp) / 'work'), 0)
            self.assertTrue((Path(tmp) / 'work' / 'F_SPEC.json').is_file())
            self.assertTrue((Path(tmp) / 'work' / 'F_HOURS.json').is_file())
            for query_id in ('F_EDU', 'F_SAL'):
                self.assertFalse((Path(tmp) / 'work' / f'{query_id}.json').is_file())

    def test_link_text_short_and_scope_stated_once(self):
        blocks = self.composed()
        body = []
        at_appendix = False
        for kind, payload in blocks:
            if kind == 'h2' and payload.startswith('附录'):
                at_appendix = True
            if not at_appendix and kind in ('p', 'mdtable'):
                body.append(str(payload))
        text = '\n'.join(body)
        links = re.findall(r'\[([^\]]+)\]\(', text)
        self.assertTrue(links)
        date_suffix = re.compile(r'（[^）]*\d{4}-\d{2}-\d{2}[^）]*）\s*$')
        for label in links:
            weighted = sum(1.0 if ord(ch) > 0x2E7F else 0.5 for ch in label)
            self.assertLessEqual(weighted, 26, f'链接文字过宽（{weighted:g}）：{label}')
            self.assertFalse(date_suffix.search(label), f'链接文字带日期后缀：{label}')
            self.assertNotIn('（广东省', label)  # 地域/时期在表内说明一次，不进每条链接
        self.assertIn('依据口径（广东省口径）', text)  # 表头一次说明
        md = program.blocks_markdown(blocks)
        self.assertNotIn('](', md)  # 下载件 md 与 Word 一致：只显示可读文字，无死链

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
        self._corpus_prev = (program.CORPUS_DIR, program._corpus_rows)
        program.CORPUS_DIR, program._corpus_rows = make_corpus(tempfile.mkdtemp()), None

    def tearDown(self):
        import os
        program.CORPUS_DIR, program._corpus_rows = self._corpus_prev
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

    def test_docx_links_readable_without_ids_or_markdown(self):
        with patch.object(program, 'inspect_source', fake_inspect):
            self.assertEqual(program.build(self.cwd / 'program.json'), 0)
        out = next((self.cwd / 'output').iterdir())
        with zipfile.ZipFile(out / 'program.docx') as archive:
            document = archive.read('word/document.xml').decode()
            rels = archive.read('word/_rels/document.xml.rels').decode()
        # 锚点链接显示可读文字：不带 markdown 语法、不带编号目标、不做内部假超链接
        self.assertNotIn('](', document)
        self.assertNotIn('#M_POS', document)
        self.assertIn('区域在招岗位数 123 个', document)
        self.assertIn('能完成集群部署与基础调优', document)
        self.assertNotIn('<w:hyperlink', document)
        self.assertNotIn('TargetMode', rels)

    def test_program_md_has_no_link_syntax(self):
        with patch.object(program, 'inspect_source', fake_inspect):
            self.assertEqual(program.build(self.cwd / 'program.json'), 0)
        out = next((self.cwd / 'output').iterdir())
        md = (out / 'program.md').read_text(encoding='utf-8')
        # 下载件与 Word 一致：只显示可读文字，文件内没有点击不到的锚点链接
        self.assertNotIn('](', md)
        self.assertIn('区域在招岗位数 123 个', md)
        self.assertIn('依据口径（广东省口径）', md)

    def test_docx_external_hyperlink(self):
        path = self.cwd / 'links.docx'
        blocks = [('p', '外部 [教育部文件](https://www.moe.gov.cn/example) 与内部 [指标甲](#M_X) 引用')]
        program.write_docx(path, blocks)
        with zipfile.ZipFile(path) as archive:
            document = archive.read('word/document.xml').decode()
            rels = archive.read('word/_rels/document.xml.rels').decode()
            minidom.parseString(document)
            minidom.parseString(rels)
        self.assertIn('<w:hyperlink r:id="rId10">', document)
        self.assertIn('https://www.moe.gov.cn/example', rels)
        self.assertIn('TargetMode="External"', rels)
        self.assertIn('教育部文件', document)
        self.assertIn('指标甲', document)
        self.assertNotIn('](', document)

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


class CheckPageTests(unittest.TestCase):
    """成品页面校验：图型家族门槛、编号清零、死链与规划一致性。"""

    def make_workspace(self, tmp, kinds=('matrix', 'bar', 'interval'), body_text=None,
                       dead=False, unplanned=False, drop_plan_entry=False, long_link=False,
                       date_suffix_link=False, single_group_interval=False):
        root = Path(tmp)
        specs = []
        for i, kind in enumerate(kinds):
            fid = f'F{i}{kind.replace("-", "")}'
            if kind == 'interval':
                dataset = {'d': ([{'g': '单组', 'v': 9, 'lo': 6, 'hi': 14}] if single_group_interval
                                 else [{'g': '大专', 'v': 9, 'lo': 6, 'hi': 14},
                                       {'g': '本科', 'v': 13, 'lo': 8, 'hi': 20}])}
                fields = {'group': 'g', 'value': 'v', 'lower': 'lo', 'upper': 'hi'}
            else:
                dataset = {'d': [{'c': '甲', 'v': 1}]}
                fields = {'category': 'c', 'value': 'v'}
            spec = {'schema': 'figure/1', 'id': fid, 'lang': 'zh', 'title': f'图{i}',
                    'datasets': dataset,
                    'panels': [{'kind': kind, 'title': f'图{i}', 'data': 'd',
                                'fields': fields, 'x_label': 'x', 'y_label': 'y'}]}
            (root / 'work').mkdir(parents=True, exist_ok=True)
            (root / 'work' / f'{fid}.json').write_text(json.dumps(spec), encoding='utf-8')
            bundle = root / 'work' / 'figures' / fid
            bundle.mkdir(parents=True, exist_ok=True)
            (bundle / 'values.json').write_text(
                json.dumps([{'kind': kind, 'title': f'图{i}', 'rows': []}]), encoding='utf-8')
            specs.append((fid, kind))
        plan = [{'id': fid, 'question': 'q', 'kind': kind, 'reason': 'r', 'section': '四、职业面向',
                 'dataOrigin': 'query', 'dataRefs': {'metricIds': ['M_X']}} for fid, kind in specs]
        figures = [{'type': 'figure', 'spec': f'{fid}.json', 'bundle': f'figures/{fid}'}
                   for fid, _ in specs]
        if unplanned:
            spec = {'schema': 'figure/1', 'id': 'F_EXTRA', 'lang': 'zh', 'title': '额外',
                    'datasets': {'d': [{'c': '甲', 'v': 1}]},
                    'panels': [{'kind': 'bar', 'title': '额外', 'data': 'd',
                                'fields': {'category': 'c', 'value': 'v'},
                                'x_label': 'x', 'y_label': 'y'}]}
            (root / 'work' / 'F_EXTRA.json').write_text(json.dumps(spec), encoding='utf-8')
            extra = root / 'work' / 'figures' / 'F_EXTRA'
            extra.mkdir(parents=True, exist_ok=True)
            (extra / 'values.json').write_text(json.dumps([{'kind': 'bar', 'title': '额外'}]),
                                               encoding='utf-8')
            figures.append({'type': 'figure', 'spec': 'F_EXTRA.json', 'bundle': 'figures/F_EXTRA'})
        if drop_plan_entry:
            plan = plan[:-1]
        blocks = [
            {'type': 'text', 'text': body_text
             or '岗位判断见 [区域在招岗位数 12,280 个](#M_X)，对标 [同类方案样例1](#S_X)。'},
            {'type': 'section', 'title': '四、职业面向', 'blocks': figures},
            {'type': 'section', 'title': '附录A 证据与口径', 'blocks': [
                {'type': 'text', 'id': 'M_X', 'text': '**M_X · 区域在招岗位数**：12,280 个｜广东省｜口径见条目'},
                {'type': 'text', 'id': 'S_X', 'text': '**S_X · 同类方案样例1**：本地语料对标来源'},
            ]},
        ]
        (root / 'work' / 'page.json').write_text(
            json.dumps({'title': '测试方案', 'blocks': blocks}, ensure_ascii=False), encoding='utf-8')
        (root / 'program.json').write_text(
            json.dumps({'schema': 'training-program/1', 'chartPlan': plan}), encoding='utf-8')
        metric_label = ('区域在招岗位数 12,280 个（全国人才数据库受管查询，去重岗位主键口径，'
                        '样本分母与读取时间说明见附录条目，这里是超长回退示例）' if long_link
                       else '区域在招岗位数 12,280 个')
        if date_suffix_link:
            metric_label = '区域在招岗位数 12,280 个（广东省，2026-11-01）'
        html = ('<html><body><div id="M_X"></div><div id="S_X"></div>'
                '<h2>四、职业面向</h2>'
                f'<a href="#M_X">{metric_label}</a>'
                '<a href="#S_X">同类方案样例1</a>'
                '<h2>附录A 证据与口径</h2><p>M_X · 区域在招岗位数</p></body></html>')
        if dead:
            html = html.replace('<a href="#S_X">', '<a href="#S_MISSING">', 1)
        site = root / 'output' / 'public' / 'site'
        site.mkdir(parents=True, exist_ok=True)
        (site / 'index.html').write_text(html, encoding='utf-8')
        return root

    def run_check(self, **kwargs):
        import check_page
        tmp = tempfile.mkdtemp()
        try:
            root = self.make_workspace(tmp, **kwargs)
            return check_page.check(root, Path('work/page.json'),
                                    Path('output/public/site'), Path('program.json'))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_passes_with_three_families_and_live_links(self):
        summary, errors = self.run_check(kinds=('matrix', 'bar', 'interval'))
        self.assertEqual(errors, [])
        self.assertEqual(summary['familyCount'], 3)
        self.assertEqual(summary['barPanels'], 1)
        self.assertEqual(summary['deadLinks'], 0)
        self.assertGreaterEqual(summary['internalLinks'], 2)

    def test_all_bar_families_fail(self):
        summary, errors = self.run_check(kinds=('bar', 'barh', 'bar'))
        self.assertTrue(any('图型家族' in e for e in errors))

    def test_bar_over_half_fails(self):
        summary, errors = self.run_check(kinds=('bar', 'bar', 'bar', 'matrix', 'interval'))
        self.assertTrue(any('超过全部图的一半' in e for e in errors))

    def test_dead_anchor_fails(self):
        summary, errors = self.run_check(dead=True)
        self.assertTrue(any('死链' in e for e in errors))

    def test_combo_pattern_fails(self):
        summary, errors = self.run_check(
            body_text='依据 指标 M_X 与 能力 C-A-1 支撑该判断，详见附录。')
        self.assertTrue(any('编号引用写法' in e for e in errors))

    def test_bare_id_in_body_fails(self):
        summary, errors = self.run_check(body_text='依据 M_X 支撑该判断。')
        self.assertTrue(any('裸编号' in e for e in errors))

    def test_link_text_too_long_fails(self):
        summary, errors = self.run_check(kinds=('matrix', 'bar', 'interval'), long_link=True)
        self.assertTrue(any('超过' in e and '上限' in e for e in errors))
        self.assertTrue(summary['linkTextOverLimit'] >= 1)

    def test_link_text_date_suffix_fails(self):
        summary, errors = self.run_check(kinds=('matrix', 'bar', 'interval'), date_suffix_link=True)
        self.assertTrue(any('带日期后缀' in e for e in errors))
        self.assertTrue(summary['linkTextOverLimit'] >= 1)

    def test_interval_single_group_fails(self):
        summary, errors = self.run_check(kinds=('matrix', 'bar', 'interval'),
                                         single_group_interval=True)
        self.assertTrue(any('区间图仅 1 组' in e for e in errors))

    def test_unplanned_figure_fails(self):
        summary, errors = self.run_check(kinds=('matrix', 'bar', 'interval'), unplanned=True)
        self.assertTrue(any('不在 chartPlan' in e for e in errors))

    def test_planned_figure_missing_from_page_fails(self):
        summary, errors = self.run_check(kinds=('matrix', 'bar', 'interval'),
                                         drop_plan_entry=False)
        # 对照：删掉页面上的最后一图但保留规划 → 规划图未上页
        import check_page
        tmp = tempfile.mkdtemp()
        try:
            root = self.make_workspace(tmp, kinds=('matrix', 'bar', 'interval'))
            page = json.loads((root / 'work' / 'page.json').read_text())
            section = next(b for b in page['blocks'] if b.get('title') == '四、职业面向')
            section['blocks'] = section['blocks'][:-1]
            (root / 'work' / 'page.json').write_text(json.dumps(page, ensure_ascii=False))
            summary, errors = check_page.check(root, Path('work/page.json'),
                                               Path('output/public/site'), Path('program.json'))
            self.assertTrue(any('规划图未上页' in e for e in errors))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
