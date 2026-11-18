import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
import sys
import tempfile

spec=importlib.util.spec_from_file_location('learning_build',Path(__file__).parents[1]/'scripts/build.py')
build=importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.doc={'id':'doc','title':'教材','tag_id':'course','preview_url':'https://example.test/api/learning-materials/'+'a'*48+'/preview','download_url':'https://example.test/api/learning-materials/'+'a'*48+'/download'}
        self.evidence=[{'operation':'tags','result':{'status':'ok','items':[{'id':'course','name':'模型训练'}]}}, {'operation':'documents','result':{'status':'ok','items':[self.doc]}}]
        self.plan={'profile':{'role':'模型训练助理','goal':'实习','foundation':'Python基础','availability':'每天1小时，每周5天'},'mode':'full','summary':'先复习再训练模型。','assumptions':[], 'days_per_week':5,'minutes_per_day':60,'courses':[{'id':'course','name':'模型训练','reason':'覆盖模型训练任务','document_ids':['doc']}],'stages':[{'title':'基础','goal':'掌握训练流程','completion':'独立训练小模型','days':[{'tasks':[{'task':'阅读并完成练习','minutes':60,'materials':['doc'],'deliverable':'训练记录'}]}]}],'adjustments':'已有基础通过练习后跳过复习。'}

    def test_valid_plan_preserves_material_links_and_daily_budget(self):
        page=build.build_page(self.plan,self.evidence)
        self.assertIn(self.doc['preview_url'],str(page))
        self.assertIn('60',str(page))

    def test_cli_uses_plan_directory_when_invoked_elsewhere(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root=Path(directory)
            (root/'learning-plan.json').write_text(json.dumps(self.plan))
            (root/'.weknora-evidence.jsonl').write_text('\n'.join(json.dumps(row) for row in self.evidence))
            result=subprocess.run([sys.executable,str(Path(build.__file__).resolve()),str(root/'learning-plan.json')],cwd=other,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            manifest=json.loads((root/'delivery.json').read_text())
            page=root/manifest['web'][0]['directory']/'index.html'
            self.assertIn('href="'+self.doc['preview_url']+'"',page.read_text())
            self.assertFalse((Path(other)/'delivery.json').exists())

    def test_over_budget_is_rejected(self):
        self.plan['stages'][0]['days'][0]['tasks'][0]['minutes']=61
        with self.assertRaisesRegex(ValueError,'时间'): build.build_page(self.plan,self.evidence)

    def test_unknown_document_is_rejected(self):
        self.plan['stages'][0]['days'][0]['tasks'][0]['materials']=['invented']
        with self.assertRaisesRegex(ValueError,'教材'): build.build_page(self.plan,self.evidence)

    def test_self_plan_requires_successful_retrieval_but_no_invented_links(self):
        self.plan['mode']='self';self.plan['courses']=[]
        self.plan['stages'][0]['days'][0]['tasks'][0]['materials']=[]
        page=build.build_page(self.plan,self.evidence[:1])
        self.assertIn('自主规划',str(page))
        with self.assertRaisesRegex(ValueError,'查询'):build.build_page(self.plan,[])

    def test_failure_fallback_requires_actual_user_authorization(self):
        self.plan['mode']='self';self.plan['courses']=[]
        self.plan['stages'][0]['days'][0]['tasks'][0]['materials']=[]
        self.plan['fallback_authorization']='按我的岗位自主规划'
        failures=[{'operation':'tags','result':{'status':'unavailable'}}]
        with self.assertRaises(ValueError):build.build_page(self.plan,failures,[])
        page=build.build_page(self.plan,failures,['请按我的岗位自主规划'])
        self.assertIn('知识库访问未完成',str(page))

    def test_previous_success_does_not_mask_current_failure(self):
        self.plan['mode']='self';self.plan['courses']=[]
        self.plan['stages'][0]['days'][0]['tasks'][0]['materials']=[]
        previous={'runId':'old','operation':'tags','result':{'status':'ok','items':[]}}
        current={'runId':'current','operation':'tags','result':{'status':'unavailable'}}
        with self.assertRaisesRegex(ValueError,'本轮'):build.build_page(self.plan,[previous,current],current_run='current')
        self.plan['fallback_authorization']='自主规划'
        page=build.build_page(self.plan,[previous,current],['请自主规划'],'current')
        self.assertNotIn('本次未匹配到合适',str(page))
        self.assertIn('知识库访问未完成',str(page))
        # A later revision can reuse verified evidence without pretending an old failure is current.
        self.plan.pop('fallback_authorization')
        build.build_page(self.plan,[previous,current],current_run='next')

    def test_cross_course_document_is_rejected(self):
        self.doc['tag_id']='other'
        with self.assertRaisesRegex(ValueError,'分类'):build.build_page(self.plan,self.evidence)

    def test_matched_course_must_be_used_in_tasks(self):
        self.plan['stages'][0]['days'][0]['tasks'][0]['materials']=[]
        with self.assertRaisesRegex(ValueError,'任务'):build.build_page(self.plan,self.evidence)

if __name__=='__main__':unittest.main()
