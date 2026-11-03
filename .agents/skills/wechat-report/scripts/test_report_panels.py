import unittest
from report_charts import requirements_composition,city_concentration,salary_cohorts,cohort_cities


class PanelTests(unittest.TestCase):
    def test_stacks_use_education_denominators_and_preserve_unknown(self):
        chart=requirements_composition([['本科','不限',30],['本科','经验',70],['大专','不限',10],['未知','未知',5]])
        self.assertEqual(chart['counts'],[100,10,5])
        matrix={(r,c):v for r,c,v in chart['cells']}
        for row in range(3):self.assertAlmostEqual(sum(v for (r,c),v in matrix.items() if r==row),100)
        self.assertEqual(matrix[(0,chart['cols'].index('不限'))],30)
        self.assertEqual(matrix[(1,chart['cols'].index('不限'))],100)

    def test_city_share_accounts_for_unassigned_records(self):
        chart=city_concentration({'city':[['乙市',20],['甲市',50],['丙市',10]],'total':{'positions':100}})
        self.assertEqual(chart['data'],[['甲市',50],['乙市',20],['其余地区及地址未归属',30]])
        self.assertEqual(sum(row[1] for row in chart['data']),100)

    def test_salary_comparison_excludes_small_or_missing_quantiles(self):
        data={'salary':{'valid':100,'p25':5,'median':10,'p75':20},'voc_pool':{'salary':{'valid':29,'p25':3,'median':5,'p75':7}}}
        self.assertIsNone(salary_cohorts(data))
        data['voc_pool']['salary']['valid']=30
        self.assertEqual(salary_cohorts(data)['data'][1],['职教入门池',30,3,5,7])

    def test_city_cohort_comparison_is_not_recruitment_conversion(self):
        data={'total':{'positions':100},'city':[['甲市',70],['乙市',30]],'voc_pool':{'count':20,'city':[['甲市',10],['乙市',10]]}}
        self.assertEqual(cohort_cities(data)['data'],[['甲市',70,50],['乙市',30,50]])
        data['voc_pool']['count']=0
        self.assertIsNone(cohort_cities(data))


if __name__=='__main__':unittest.main()
