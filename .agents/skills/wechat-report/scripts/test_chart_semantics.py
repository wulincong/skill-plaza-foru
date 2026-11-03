import copy
import unittest
from chart_semantics import errors


class SemanticsTests(unittest.TestCase):
    def test_heatmap_transpose_is_rejected_even_when_picture_is_nonblank(self):
        cfg={'kind':'heatmap','rows':['r1','r2'],'cols':['c1','c2'],'cells':[[0,0,1],[0,1,2],[1,0,9],[1,1,4]]}
        actual={'xAxis':[cfg['cols']],'yAxis':[cfg['rows']],'series':[{'data':[[0,0,1],[1,0,2],[0,1,9],[1,1,4]]}]}
        self.assertFalse(errors(cfg,actual))
        actual['series'][0]['data']=[[r,c,v] for r,c,v in cfg['cells']]
        self.assertTrue(errors(cfg,actual))

    def test_counts_are_not_misrepresented_as_percentages(self):
        cfg={'kind':'vbar','data':[['甲',100],['乙',50]]}
        actual={'xAxis':[['甲','乙']],'series':[{'data':[66.7,33.3]}]}
        self.assertTrue(errors(cfg,actual))
        actual['series'][0]['data']=[100,50]
        self.assertFalse(errors(cfg,actual))
        actual['xAxis'][0].reverse();self.assertTrue(errors(cfg,actual))

    def test_salary_missing_median_or_swapped_endpoints_fail(self):
        cfg={'kind':'range_dot','data':[['方向',40,5,10,20]]}
        actual={'yAxis':[['方向']],'series':[{'data':[5]},{'data':[15]},{'data':[[10,0]]}]}
        self.assertFalse(errors(cfg,actual))
        actual['series'].pop();self.assertTrue(errors(cfg,actual))


if __name__=='__main__':unittest.main()
