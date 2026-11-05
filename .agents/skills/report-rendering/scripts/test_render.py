"""Content preservation and delivery regressions for the report UI renderer."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import render
import os
import hashlib
from register_delivery import register


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_markdown_retains_content_and_table_semantics(self):
        source = self.root / '原稿.md'
        source.write_text('# 标题\n\n原始判断 **保持**。\n\n| 对象 | 数值 |\n|---|---:|\n|甲|0|\n\n> 原话\n')
        page = render.build(source, self.root / 'site').read_text()
        for value in ['<h1>标题</h1>', '<strong>保持</strong>', '<td style="text-align:right">0</td>', '<blockquote>', 'scope="col"']:
            self.assertIn(value, page)

    def test_register_revision_preserves_content_and_fails_before_replacing_manifest(self):
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        source = self.root / 'report.md'
        source.write_text('# 已审内容\n保留原结论。')
        files = [{'name':'报告正文','path':'report.md','sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]
        receipt = self.root / 'receipt.json'
        receipt.write_text(json.dumps({'files':files}))
        first = self.root / 'output/public/r1'
        render.build(source, first)
        register(first, files_from=receipt)
        original_page = (first/'index.html').read_bytes()
        second = self.root / 'output/public/r2'
        render.build(source, second, theme='minimal')
        register(second, files_from=receipt)
        manifest = json.loads((self.root/'delivery.json').read_text())
        self.assertEqual(manifest['files'],files)
        self.assertEqual([w['directory'] for w in manifest['web']],['output/public/r2'])
        self.assertEqual((first/'index.html').read_bytes(),original_page)
        source.write_text('# 未审内容\n结论被修改。')
        with self.assertRaisesRegex(ValueError,'原件已改变'):
            register(second,files_from=receipt)
        self.assertEqual(json.loads((self.root/'delivery.json').read_text()),manifest)

    def test_themes_preserve_same_content_and_missing_values(self):
        source = self.root / 'page.json'
        source.write_text(json.dumps({'title':'报告','blocks':[{'type':'table','title':'比较','columns':[{'label':'对象'},{'label':'值','numeric':True}], 'rows':[['甲',0],['乙',None],['丙','']]}]}))
        first = render.build(source, self.root / 'paper', theme='paper').read_text()
        second = render.build(source, self.root / 'minimal', theme='minimal').read_text()
        self.assertEqual(first, second)
        self.assertIn('>0</td>', first)
        self.assertIn('>未提供</td>', first)
        self.assertIn('class="report-number"></td>', first)
        self.assertNotEqual((self.root/'paper/theme.css').read_text(), (self.root/'minimal/theme.css').read_text())

    def test_failed_build_preserves_existing_revision(self):
        source = self.root / 'report.md'
        source.write_text('# 原稿\n内容')
        page = render.build(source, self.root / 'site')
        original = page.read_bytes()
        source.write_text('# 改稿\n新内容')
        with self.assertRaises(ValueError):
            render.build(source, self.root / 'site')
        self.assertEqual(page.read_bytes(), original)
        with self.assertRaises(OSError):
            render.build(source, self.root / 'failed', theme_css=self.root/'absent.css')
        self.assertFalse((self.root/'failed').exists())
        self.assertFalse(list(self.root.glob('.report-*')))

    def test_content_is_escaped_and_bad_urls_are_not_links(self):
        content = render.Page(self.root).render({'title':'<script>alert(1)</script>', 'blocks':[
            {'type':'text','text':'<script>alert(1)</script> [危险](javascript:alert(1))'},
            {'type':'sources','items':[{'label':'来源','url':'javascript:alert(1)'}]}]})
        self.assertNotIn('<script>', content)
        self.assertNotIn('href="javascript:', content)
        self.assertIn('&lt;script&gt;', content)

    def test_malformed_internal_model_does_not_silently_lose_cells(self):
        page = render.Page(self.root)
        with self.assertRaises(ValueError):
            page.table({'columns':[{'label':'一列'}],'rows':[[1,2]]})
        with self.assertRaises(ValueError):
            page.blocks([{'type':'text','id':'same','text':'甲'},{'type':'text','id':'same','text':'乙'}])

    def test_chart_bundle_is_verified_before_publication(self):
        spec = {'schema':'figure/1','id':'CHECK','lang':'zh','title':'示意数量','caption':'组件测试','source':'模拟记录',
                'datasets':{'数据':[{'组':'甲','值':3},{'组':'乙','值':0}]},
                'panels':[{'kind':'barh','data':'数据','title':'数量','fields':{'category':'组','value':'值'},'x_label':'条','y_label':'分组'}]}
        spec_path = self.root/'spec.json'
        spec_path.write_text(json.dumps(spec))
        tool = render.ROOT.parent/'chart-visualization/scripts/figure.py'
        subprocess.run([sys.executable,str(tool),'render',str(spec_path),'--out',str(self.root/'figure')],check=True, capture_output=True)
        source = self.root/'page.json'
        source.write_text(json.dumps({'title':'报告','blocks':[{'type':'figure','spec':'spec.json','bundle':'figure'}]}))
        page = render.build(source,self.root/'site').read_text()
        bundle = (self.root/'figure/figure.html').read_text()
        start = bundle.index('<figure ')
        figure = bundle[start:bundle.index('</figure>',start)+len('</figure>')]
        self.assertIn(figure,page)
        (self.root/'figure/figure.svg').write_text('<svg/>')
        with self.assertRaises(subprocess.CalledProcessError):
            render.build(source,self.root/'rejected')
        self.assertFalse((self.root/'rejected').exists())


if __name__ == '__main__':
    unittest.main()
