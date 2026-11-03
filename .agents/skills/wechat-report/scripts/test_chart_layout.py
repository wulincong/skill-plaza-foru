"""Regression probes for rendering mistakes, independent of the model and database."""
import io
import unittest
from chart_recommender import recommend_composition, check_chart_choice
from chart_layout import chart_js, chart_height
from render_report import THEME
from render_check import band_funcs, _rgb
from PIL import Image


class ChartTests(unittest.TestCase):
    def test_unsorted_composition_uses_full_denominator(self):
        choice = recommend_composition([{'name':'minor','count':5,'pct':90}, {'name':'major','count':95,'pct':1}])
        self.assertEqual(choice['kind'], 'bignum')
        self.assertEqual(choice['card']['value']['name'], 'major')

    def test_unsorted_ranking_is_rejected(self):
        self.assertTrue(check_chart_choice({'kind':'hbar','data':[['a',1],['b',2]]}))

    def test_units_are_explicit(self):
        code = chart_js({'kind':'vbar','data':[['a',120]],'unit':'条'}, 'c1', THEME)
        self.assertIn('120条', code)
        self.assertNotIn('120%', code)
        with self.assertRaises(ValueError):
            chart_js({'kind':'vbar','data':[['a',120]],'pct_label':True}, 'c1', THEME)

    def test_unknown_graph_fails_loudly(self):
        with self.assertRaises(ValueError):
            chart_js({'kind':'not_implemented'},'c1',THEME)

    def test_heatmap_orientation_and_height(self):
        cfg={'kind':'heatmap','rows':['one','two'],'cols':['a','b','c'],'cells':[[1,2,37]]}
        self.assertIn('[2, 1, 37]',chart_js(cfg,'c1',THEME))
        self.assertGreater(chart_height(dict(cfg,rows=list(range(10)))),chart_height(cfg))

    def test_all_theme_endpoints_match_their_color_band(self):
        from render_report import load_theme
        for name in ['deep_purple','bamboo','crimson','ink_gold','warm_sand']:
            predicate,_=band_funcs(name)
            self.assertTrue(predicate(*_rgb(load_theme(name)['heat'][-1])),name)


if __name__ == '__main__':
    unittest.main()
