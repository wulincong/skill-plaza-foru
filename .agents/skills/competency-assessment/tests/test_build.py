import copy
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('assessment',Path(__file__).parents[1]/'scripts/build.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture():
    source={'records':[{'positionId':'123','positionName':'前端实习','companyName':'示例企业','positionDescription':'熟悉Vue，能够独立完成页面开发。本科在校生。','url':'https://job.foru-ai.com/#/station/detail/123'}], 'resume':'本科计算机专业在校生；独立完成Vue校园网站页面开发。','retrievedAt':'2026-11-20'}
    plan={'targetRole':'前端实习','mode':'position','selectedJobs':[{'id':'123','reason':'同方向实习岗位'}],'summary':'页面开发有项目证据，仍需验证工程质量。','qualifications':[{'name':'学历','status':'符合','sources':[{'positionId':'123','quote':'本科在校生'}],'studentQuote':'本科计算机专业在校生','reason':'材料自述符合'}], 'competencies':[{'id':'vue','name':'Vue页面开发','dimension':'开发能力','weight':100,'requiredLevel':3,'observedLevel':3,'sources':[{'positionId':'123','quote':'熟悉Vue','basis':'explicit'}],'evidence':[{'quote':'独立完成Vue校园网站页面开发','kind':'项目描述'}],'explanation':'项目自述支持独立开发，尚未经实操验证。','improvement':{'task':'完善错误处理','deliverable':'代码和测试记录','check':'接口失败时有提示','priority':'高'}}]}
    return plan,source

class AssessmentTests(unittest.TestCase):
    def test_known_score(self):
        p,s=fixture();result=m.validate(p,s);self.assertEqual(result['score'],100);self.assertEqual(result['coverage'],100)
    def test_partial_coverage_is_weighted_without_renormalizing(self):
        p,s=fixture();first=p['competencies'][0];first['weight']=40
        second=copy.deepcopy(first);second.update(id='other',weight=60,observedLevel=None,evidence=[]);p['competencies'].append(second)
        result=m.validate(p,s);self.assertEqual(result['coverage'],40);self.assertIsNone(result['score'])
        second.update(observedLevel=2,requiredLevel=4,evidence=copy.deepcopy(first['evidence']))
        self.assertEqual(m.validate(p,s)['score'],70)
    def test_direction_multiple_jobs_have_provenance(self):
        p,s=fixture();p['mode']='direction'
        for i in range(124,128):
            row=copy.deepcopy(s['records'][0]);row['positionId']=str(i);s['records'].append(row)
            p['selectedJobs'].append({'id':str(i),'reason':'同方向初级岗位'})
        self.assertEqual(len(p['selectedJobs']),5);self.assertEqual(m.validate(p,s)['score'],100)
    def test_unknown_is_not_zero(self):
        p,s=fixture();p['competencies'][0].update(observedLevel=None,evidence=[])
        result=m.validate(p,s);self.assertIsNone(result['score']);self.assertEqual(result['coverage'],0)
        self.assertIn('信息不足',str(m.build_page(p,s)))
    def test_score_requires_student_quote(self):
        p,s=fixture();p['competencies'][0]['evidence']=[]
        with self.assertRaises(ValueError):m.validate(p,s)
    def test_fabricated_quotes_rejected(self):
        for field in ('jd','student'):
            p,s=fixture()
            if field=='jd':p['competencies'][0]['sources'][0]['quote']='精通React'
            else:p['competencies'][0]['evidence'][0]['quote']='负责百万用户系统'
            with self.assertRaises(ValueError):m.validate(p,s)
    def test_inference_requires_explanation(self):
        p,s=fixture();p['competencies'][0]['sources'][0]['basis']='inferred'
        with self.assertRaises(ValueError):m.validate(p,s)
    def test_qualification_is_separate_and_needs_evidence(self):
        p,s=fixture();p['qualifications'][0]['status']='不符合'
        self.assertEqual(m.validate(p,s)['score'],100)
        p['qualifications'][0]['studentQuote']=''
        with self.assertRaises(ValueError):m.validate(p,s)
    def test_education_and_preferences_do_not_count_as_ability(self):
        context={'skill':'competency-assessment','message':'','messages':['【测评材料】\n{"education":"本科","notes":"想评估Vue"}']}
        result=m.shared.assessment_context(context);self.assertFalse(result['hasAbilityMaterials'])
        p,s=fixture();s.update(result);s['resume']=''
        with self.assertRaises(ValueError):m.validate(p,s)
    def test_no_materials_no_assessment(self):
        p,s=fixture();s['resume']=''
        with self.assertRaises(ValueError):m.validate(p,s)
    def test_unknown_job_rejected(self):
        p,s=fixture();p['selectedJobs'][0]['id']='456'
        with self.assertRaises(ValueError):m.validate(p,s)
    def test_weights_and_levels(self):
        for changes in ({'weight':99},{'requiredLevel':0},{'observedLevel':5},{'weight':True}):
            p,s=fixture();p['competencies'][0].update(changes)
            with self.assertRaises(ValueError):m.validate(p,s)
    def test_form_context_is_separate_and_scope_is_current(self):
        context={'skill':'competency-assessment','message':'【测评范围】\n{"mode":"position","positionId":"123"}',
          'messages':['【测评材料】\n{"projects":"完成Vue项目","role":"高级架构师","jd":"精通React"}\n【测评范围】\n{"mode":"position","positionId":"123"}']}
        result=m.shared.assessment_context(context)
        self.assertIn('完成Vue项目',result['studentMaterials']);self.assertNotIn('精通React',result['studentMaterials'])
        self.assertEqual(result['assessmentScope']['positionId'],'123')
        context['messages'].append('【测评材料】\n'+__import__('json').dumps({'resume':'学历\n独立完成Vue项目'}))
        self.assertIn('学历\n独立完成Vue项目',m.shared.assessment_context(context)['studentMaterials'])
        context['message']='继续'
        self.assertEqual(m.shared.assessment_context(context)['assessmentScope']['positionId'],'123')
        context['message']='我选择另一个岗位456'
        self.assertEqual(m.shared.assessment_context(context)['assessmentScope']['positionId'],'456')
    def test_explicit_scope_and_role_are_enforced(self):
        p,s=fixture();s['assessmentScope']={'mode':'position','positionId':'456'}
        with self.assertRaises(ValueError):m.validate(p,s)
        del s['assessmentScope'];s['filters']={'keyword':'Java'}
        with self.assertRaises(ValueError):m.validate(p,s)
    def test_stale_or_changed_source_rejected(self):
        import tempfile, hashlib, json
        with tempfile.TemporaryDirectory() as root:
            w=Path(root);(w/'.job-matching').mkdir();p,s=fixture();s['runId']='old'
            path=w/'.job-matching/a.json';path.write_text(json.dumps(s));p.update(snapshot='.job-matching/a.json',sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            (w/'.job-request.json').write_text(json.dumps({'runId':'new'}));(w/'.job-query-state.json').write_text(json.dumps({'runId':'new','status':'ok',**{k:p[k] for k in ('snapshot','sha256')}}))
            with self.assertRaises(ValueError):m.load_source(w,p)
            p['sha256']='fake'
            with self.assertRaises(ValueError):m.load_source(w,p)
    def test_public_report_no_contact_or_raw_materials(self):
        p,s=fixture();p['summary']='联系13800138000或test@example.com'
        text=str(m.build_page(p,s));self.assertNotIn('13800138000',text);self.assertNotIn('test@example.com',text)
        self.assertNotIn('snapshot',text);self.assertNotIn('检索条件',text)

if __name__=='__main__':unittest.main()
