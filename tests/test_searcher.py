import unittest
from io import StringIO
from textwrap import dedent
from unittest import mock

import numpy as np

from formula_altsearch import searcher as _searcher


class TestUtilities(unittest.TestCase):
    def test_load_formula_database(self):
        database = _searcher.load_formula_database(StringIO(dedent(
            """\
            - name: “張三”芍藥甘草湯濃縮細粒
              key: 芍藥甘草湯
              vendor: 張三製藥股份有限公司
              url: https://example.org/?id=123
              unit_dosage: 9.0
              composition:
                白芍: 12.0
                炙甘草: 12.0
            """
        )))
        self.assertEqual(database, {
            '芍藥甘草湯': {
                '炙甘草': 1.3333333333333333,
                '白芍': 1.3333333333333333,
            },
        })

    def test_load_formula_database_no_unit_dosage(self):
        database = _searcher.load_formula_database(StringIO(dedent(
            """\
            - name: “張三”芍藥甘草湯濃縮細粒
              key: 芍藥甘草湯
              vendor: 張三製藥股份有限公司
              url: https://example.org/?id=123
              composition:
                白芍: 1.333
                炙甘草: 1.333
            """
        )))
        self.assertEqual(database, {
            '芍藥甘草湯': {
                '炙甘草': 1.333,
                '白芍': 1.333,
            },
        })

    @mock.patch.object(_searcher, 'log')
    def test_load_formula_database_duplicated_key(self, m_log):
        """Should ignore an item with a duplicated key."""
        database = _searcher.load_formula_database(StringIO(dedent(
            """\
            - name: “張三”芍藥甘草湯濃縮細粒
              key: 芍藥甘草湯
              vendor: 張三製藥股份有限公司
              url: https://example.org/?id=123
              unit_dosage: 9.0
              composition:
                白芍: 12.0
                炙甘草: 12.0
            - name: “李四”芍藥甘草湯濃縮細粒
              key: 芍藥甘草湯
              vendor: 李四製藥股份有限公司
              url: https://example.org/?id=456
              unit_dosage: 8.0
              composition:
                白芍: 12.0
                炙甘草: 12.0
            """
        )))
        self.assertEqual(database, {
            '芍藥甘草湯': {
                '炙甘草': 1.3333333333333333,
                '白芍': 1.3333333333333333,
            },
        })

    @mock.patch.object(_searcher, 'BeamFormulaSearcher')
    def test_find_best_matches(self, m_cls):
        _searcher.find_best_matches({}, {}, excludes=None, penalty_factor=2.0)
        m_cls.assert_called_with({})
        m_cls().find_best_matches.assert_called_with(None, {}, excludes=None, penalty_factor=2.0)


class TestExhaustiveFormulaSearcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '麻黃湯': {'麻黃': 0.9, '桂枝': 0.6, '炙甘草': 0.3, '杏仁': 0.5},
            '桂枝': {'桂枝': 1}, '白芍': {'白芍': 1}, '生薑': {'生薑': 0.8}, '炙甘草': {'炙甘草': 0.8},
        }

    @staticmethod
    def _test_context_db():
        return {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
            '乙複方': {'丙藥': 1.0, '丁藥': 1.0},
            '甲單方': {'甲藥': 1.0},
            '乙單方': {'乙藥': 1.0},
            '丙單方': {'丙藥': 1.0},
            '丁單方': {'丁藥': 1.0},
        }

    def test_context_formula_mapping_basic(self):
        """cformulas/sformulas should contain only compound/simple formulas"""
        database = self._test_context_db()
        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context({'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0, '丁藥': 1.0})
        self.assertEqual(set(searcher.cformulas), {'甲複方', '乙複方'})
        self.assertEqual(set(searcher.sformulas), {'甲單方', '乙單方', '丙單方', '丁單方'})

    def test_context_formula_mapping_filter_by_target(self):
        """Formulas containing no herbs in target should not present"""
        database = self._test_context_db()
        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context({'甲藥': 1.0, '乙藥': 1.0})
        self.assertEqual(set(searcher.cformulas), {'甲複方'})
        self.assertEqual(set(searcher.sformulas), {'甲單方', '乙單方'})

    def test_context_formula_mapping_filter_by_zero_target(self):
        """Formulas containing only herbs in target with zero dose should not present"""
        database = self._test_context_db()
        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context({'甲藥': 1.0, '乙藥': 1.0, '丙藥': 0.0, '丁藥': 0.0})
        self.assertEqual(set(searcher.cformulas), {'甲複方'})
        self.assertEqual(set(searcher.sformulas), {'甲單方', '乙單方'})

    def test_context_formula_mapping_herb_to_sformula(self):
        """Herbs should be mapped to all related sformulas"""
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0},
            '甲單方': {'甲藥': 1.0},
            '乙單方': {'乙藥': 1.0},
            '丙單方': {'乙藥': 1.0},
            '丁單方': {'丁藥': 1.0},
        }
        searcher = _searcher.ExhaustiveFormulaSearcher(database)

        # - herbs with one related sformula should present (甲藥)
        # - herbs with multiple related sformulas should present (乙藥)
        # - herbs with no related sformula should not present (丙藥)
        # - herbs not in the target composition should not present (丁藥)
        searcher._set_context({'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0})
        self.assertEqual(searcher.herb_sformulas, {
            '甲藥': ['甲單方'],
            '乙藥': ['乙單方', '丙單方'],
        })

    def test_context_formula_excludes(self):
        """Formulas listed in `excludes` not appear in any map"""
        database = self._test_context_db()
        searcher = _searcher.ExhaustiveFormulaSearcher(database)

        searcher._set_context(
            {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0, '丁藥': 1.0},
            excludes={'乙複方', '丙單方', '丁單方'},
        )
        self.assertEqual(set(searcher.cformulas), {'甲複方'})
        self.assertEqual(set(searcher.sformulas), {'甲單方', '乙單方'})
        self.assertEqual(searcher.herb_sformulas, {'甲藥': ['甲單方'], '乙藥': ['乙單方']})

        searcher._set_context(
            {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0, '丁藥': 1.0},
            excludes={'甲複方', '乙複方', '甲單方', '乙單方', '丙單方', '丁單方'},
        )
        self.assertEqual(set(searcher.cformulas), set())
        self.assertEqual(set(searcher.sformulas), set())
        self.assertEqual(searcher.herb_sformulas, {})

    def test_generate_combinations(self):
        target_composition = {
            '桂枝': 1.0, '白芍': 1.0, '杏仁': 1.0,
        }
        searcher = _searcher.ExhaustiveFormulaSearcher(self.database)

        searcher._set_context(target_composition, max_cformulas=3, max_sformulas=0)
        self.assertEqual(list(searcher.generate_combinations()), [
            (),
            ('桂枝湯',), ('桂枝去芍藥湯',), ('麻黃湯',),
            ('桂枝湯', '桂枝去芍藥湯'), ('桂枝湯', '麻黃湯'), ('桂枝去芍藥湯', '麻黃湯'),
            ('桂枝湯', '桂枝去芍藥湯', '麻黃湯'),
        ])

        searcher._set_context(target_composition, max_cformulas=1, max_sformulas=0)
        self.assertEqual(list(searcher.generate_combinations()), [
            (), ('桂枝湯',), ('桂枝去芍藥湯',), ('麻黃湯',),
        ])

        searcher._set_context(target_composition, max_cformulas=0, max_sformulas=3)
        self.assertEqual(list(searcher.generate_combinations()), [
            (),
        ])

    def test_generate_combinations_for_sformulas(self):
        database = {
            '桂枝甘草湯': {'桂枝': 0.8, '炙甘草': 0.6},
            '芍藥甘草湯': {'白芍': 0.6, '炙甘草': 0.6},
            '桂枝': {'桂枝': 1}, '白芍': {'白芍': 1}, '生薑': {'生薑': 0.8}, '炙甘草': {'炙甘草': 0.8},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.0,
        }
        searcher = _searcher.ExhaustiveFormulaSearcher(database)

        # should supplement herbs with largest remaining dosage
        searcher._set_context(target_composition, max_cformulas=1, max_sformulas=5)
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas((), ())),
            [('桂枝', '白芍', '生薑')],
        )
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas(('桂枝甘草湯',), (1.5,))),
            [('桂枝甘草湯', '白芍', '生薑')],
        )
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas(('芍藥甘草湯',), (2,))),
            [('芍藥甘草湯', '桂枝', '生薑')],
        )

        # should honor max_sformulas
        searcher._set_context(target_composition, max_cformulas=1, max_sformulas=1)
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas((), ())),
            [('桂枝',)],
        )
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas(('桂枝甘草湯',), (1.5,))),
            [('桂枝甘草湯', '白芍')],
        )
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas(('芍藥甘草湯',), (2,))),
            [('芍藥甘草湯', '桂枝')],
        )

        # should honor max_sformulas
        searcher._set_context(target_composition, max_cformulas=1, max_sformulas=0)
        # -- should not generate empty combos
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas((), ())),
            [],
        )
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas(('桂枝甘草湯',), (1.5,))),
            [('桂枝甘草湯',)],
        )
        self.assertEqual(
            list(searcher.generate_combinations_for_sformulas(('芍藥甘草湯',), (2,))),
            [('芍藥甘草湯',)],
        )

        # should skip herbs with zero dosage (after rounded)
        database = {
            '芍藥甘草湯': {'白芍': 0.6, '炙甘草': 0.38},
            '白芍': {'白芍': 1}, '炙甘草': {'炙甘草': 1},
        }
        target_composition = {
            '白芍': 1.2, '炙甘草': 0.8,
        }
        combo = ('芍藥甘草湯',)
        dosages = (2,)

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, max_cformulas=1, max_sformulas=2, places=1)
        self.assertEqual(list(searcher.generate_combinations_for_sformulas(combo, dosages)), [
            ('芍藥甘草湯',),
        ])

        searcher._set_context(target_composition, max_cformulas=1, max_sformulas=2, places=2)
        self.assertEqual(list(searcher.generate_combinations_for_sformulas(combo, dosages)), [
            ('芍藥甘草湯', '炙甘草'),
        ])

        # should generate all sformula combinations if multiple sformulas have the target herb
        database = {
            '桂枝': {'桂枝': 1}, '製桂枝': {'桂枝': 0.8},
            '白芍': {'白芍': 1}, '芍藥': {'白芍': 0.8}, '炒白芍': {'白芍': 1.2},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2,
        }
        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, max_cformulas=1, max_sformulas=3)
        self.assertEqual(list(searcher.generate_combinations_for_sformulas((), ())), [
            ('桂枝', '白芍'), ('桂枝', '芍藥'), ('桂枝', '炒白芍'),
            ('製桂枝', '白芍'), ('製桂枝', '芍藥'), ('製桂枝', '炒白芍'),
        ])

    def test_calculate_delta(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {'桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8}

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, penalty_factor=2.0)
        self.assertEqual(searcher.calculate_delta([1, 1], ['桂枝湯', '桂枝去芍藥湯']), 0.6)
        self.assertEqual(searcher.calculate_delta([2, 0], ['桂枝湯', '桂枝去芍藥湯']), 0)
        self.assertEqual(searcher.calculate_delta([0, 2], ['桂枝湯', '桂枝去芍藥湯']), 1.2)

    def test_calculate_delta_with_penalty(self):
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
        }
        target_composition = {'甲藥': 1.0}

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, penalty_factor=4.0)
        self.assertEqual(searcher.calculate_delta([1], ('甲複方',)), 4.0)

    def test_find_best_dosages(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '苓桂朮甘湯': {'桂枝': 1, '茯苓': 1, '白朮': 0.8, '炙甘草': 0.4},
        }

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context({
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }, penalty_factor=2.0)

        dosages, delta = searcher.find_best_dosages(['桂枝湯', '桂枝去芍藥湯'])
        np.testing.assert_allclose(dosages, [2, 0], atol=1e-3)
        self.assertAlmostEqual(delta, 0, places=3)

        dosages, delta = searcher.find_best_dosages(['桂枝去芍藥湯', '桂枝湯'])
        np.testing.assert_allclose(dosages, [0, 2], atol=1e-3)
        self.assertAlmostEqual(delta, 0, places=3)

        searcher._set_context({
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8, '白朮': 1.0,
        }, penalty_factor=2.0)
        dosages, delta = searcher.find_best_dosages(['桂枝湯', '桂枝去芍藥湯'])
        np.testing.assert_allclose(dosages, [1.997, 0.000], atol=1e-3)
        self.assertAlmostEqual(delta, 1, places=3)

    def test_calculate_match_perfect_fit(self):
        """Should result in nearly 0 delta and 100% match_pct when combo can fit target perfectly."""
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
        }
        target_composition = {'甲藥': 2.0, '乙藥': 2.0}
        combo = ('甲複方',)

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, places=3)
        dosages, delta, match_pct = searcher.calculate_match(combo)

        np.testing.assert_allclose(dosages, [2.0], atol=1e-1)
        self.assertAlmostEqual(delta, 0.0, places=3)
        self.assertAlmostEqual(match_pct, 100.0, places=2)

    def test_calculate_match_approximate_fit(self):
        """Should result in minimal delta and maximal match_pct."""
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
        }
        target_composition = {'甲藥': 2.0, '乙藥': 3.0}
        combo = ('甲複方',)

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, places=3)
        dosages, delta, match_pct = searcher.calculate_match(combo)

        # expected delta = sqrt((2.5-2.0)^2 + (2.5-3.0)^2) = sqrt(0.5)
        # expected variance = sqrt(2.0^2 + 3.0^2) = sqrt(13.0)
        # expected match_ratio = 1 - sqrt(0.5)/sqrt(13.0)
        np.testing.assert_allclose(dosages, [2.5], atol=1e-1)
        self.assertAlmostEqual(delta, 0.707, places=3)
        self.assertAlmostEqual(match_pct, 80.39, places=2)

    def test_calculate_match_redundant_formulas(self):
        database = {
            '甲複方': {'甲藥': 1.0},
            '乙複方': {'甲藥': 1.0},
        }
        target_composition = {'甲藥': 5.0}
        combo = ('甲複方', '乙複方')

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, places=3)
        dosages, delta, match_pct = searcher.calculate_match(combo)

        self.assertAlmostEqual(dosages[0] + dosages[1], 5.0, places=1)
        self.assertAlmostEqual(delta, 0.0, places=3)
        self.assertAlmostEqual(match_pct, 100.0, places=2)

    def test_calculate_match_zero_combo(self):
        """Should result in 0 delta and 100% match_pct when combo is empty."""
        database = {
            '甲複方': {'甲藥': 1.0},
        }
        target_composition = {'甲藥': 5.0}
        combo = ()

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, places=3)
        dosages, delta, match_pct = searcher.calculate_match(combo)

        self.assertEqual(dosages, ())
        self.assertAlmostEqual(delta, 0.0, places=3)
        self.assertAlmostEqual(match_pct, 100.0, places=2)

    def test_evaluate_combination_basic(self):
        """Should return values as underlying `calculate_match` does."""
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
        }
        target_composition = {'甲藥': 2.0, '乙藥': 2.0}
        combo = ('甲複方',)

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, places=3)
        new_combo, new_dosages, match_pct = searcher.evaluate_combination(combo)

        self.assertEqual(new_combo, ('甲複方',))
        np.testing.assert_allclose(new_dosages, [2.0], atol=1e-1)
        self.assertAlmostEqual(match_pct, 100.0, places=2)

    def test_evaluate_combination_round(self):
        """Should round returned dosages to the specified places."""
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
        }
        target_composition = {'甲藥': 0.06, '乙藥': 0.06}
        combo = ('甲複方',)
        searcher = _searcher.ExhaustiveFormulaSearcher(database)

        searcher._set_context(target_composition, places=2)
        new_combo, new_dosages, match_pct = searcher.evaluate_combination(combo)

        self.assertEqual(new_combo, ('甲複方',))
        np.testing.assert_allclose(new_dosages, [0.06], atol=1e-2)
        self.assertAlmostEqual(match_pct, 100.0, places=2)

        searcher._set_context(target_composition, places=1)
        new_combo, new_dosages, match_pct = searcher.evaluate_combination(combo)

        self.assertEqual(new_combo, ('甲複方',))
        np.testing.assert_allclose(new_dosages, [0.1], atol=1e-1)
        self.assertAlmostEqual(match_pct, 33.33, places=2)

    def test_evaluate_combination_fix_zero(self):
        """Should strip zero-dose formulas from the returned combo and dosages."""
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
            '乙複方': {'乙藥': 1.0, '丙藥': 1.0},
            '丙複方': {'丙藥': 1.0, '丁藥': 1.0},
        }
        target_composition = {'甲藥': 2.0, '乙藥': 2.0, '丙藥': 2.0, '丁藥': 2.0}
        combo = ('甲複方', '乙複方', '丙複方')

        searcher = _searcher.ExhaustiveFormulaSearcher(database)
        searcher._set_context(target_composition, places=3)
        new_combo, new_dosages, match_pct = searcher.evaluate_combination(combo)

        # fix from ('甲複方', '乙複方', '丙複方'), [2.0, 0.0, 2.0]
        self.assertEqual(new_combo, ('甲複方', '丙複方'))
        np.testing.assert_allclose(new_dosages, [2.0, 2.0], atol=1e-1)
        self.assertAlmostEqual(match_pct, 100.0, places=2)

    def test_find_best_matches(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }
        penalty_factor = 2.0
        searcher = _searcher.ExhaustiveFormulaSearcher(database)

        # without excludes
        best_matches = searcher.find_best_matches(5, target_composition, penalty_factor=penalty_factor)
        self.assertEqual(len(best_matches), 2)

        match_pct, combo, dosages = best_matches[0]
        self.assertAlmostEqual(match_pct, 100.0, places=3)
        self.assertEqual(combo, ('桂枝湯',))
        np.testing.assert_allclose(dosages, [2], atol=1e-3)

        match_pct, combo, dosages = best_matches[1]
        self.assertAlmostEqual(match_pct, 50.84596674545061, places=3)
        self.assertEqual(combo, ('桂枝去芍藥湯',))
        np.testing.assert_allclose(dosages, [2], atol=1e-3)

        # with excludes
        best_matches = searcher.find_best_matches(
            5, target_composition, excludes={'桂枝湯'}, penalty_factor=penalty_factor)
        self.assertEqual(len(best_matches), 1)

        match_pct, combo, dosages = best_matches[0]
        self.assertAlmostEqual(match_pct, 50.84596674545061, places=3)
        self.assertEqual(combo, ('桂枝去芍藥湯',))
        np.testing.assert_allclose(dosages, [2], atol=1e-3)


class TestBeamFormulaSearcher(unittest.TestCase):
    @staticmethod
    def _sample_data():
        database = {
            '甲複方': {'甲藥': 1.0, '甲無關藥': 1.0},
            '乙複方': {'乙藥': 1.0, '乙無關藥': 1.0},
            '丙複方': {'丙藥': 1.0, '丙無關藥': 1.0},
            '丁複方': {'丁藥': 1.0, '丁無關藥': 1.0},
        }
        target_composition = {'甲藥': 1.0, '乙藥': 2.0, '丙藥': 3.0, '丁藥': 4.0}
        return database, target_composition

    @staticmethod
    def _se_eval(combo, *args, **kwargs):
        return combo, (1.0,) * len(combo), 100.0

    @staticmethod
    def _se_heur(self):
        def wrapped(combo, *args, **kwargs):
            return self.generate_ramaining_candidates(combo)
        return wrapped

    def test_generate_combinations_max_depth(self):
        """Should generate items through `generate_unique_combinations_at_depth` depth by depth."""
        database, target_composition = self._sample_data()
        searcher = _searcher.BeamFormulaSearcher(database)

        # depth 0
        searcher._set_context(target_composition, max_cformulas=0, top_n=1,
                              beam_width_factor=1000, beam_multiplier=1)
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates', side_effect=self._se_heur(searcher)), \
             mock.patch.object(searcher, 'generate_unique_combinations_at_depth',
                               wraps=searcher.generate_unique_combinations_at_depth) as m_gen:
            items = list(searcher.generate_combinations())
            self.assertEqual(items, [(100.0, (), ())])
            self.assertListEqual(m_gen.call_args_list, [])

        # depth 1
        searcher._set_context(target_composition, max_cformulas=1, top_n=1,
                              beam_width_factor=1000, beam_multiplier=1)
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates', side_effect=self._se_heur(searcher)), \
             mock.patch.object(searcher, 'generate_unique_combinations_at_depth',
                               wraps=searcher.generate_unique_combinations_at_depth) as m_gen:
            items = list(searcher.generate_combinations())
            self.assertEqual(items, [
                (100.0, (), ()),
                (100.0, ('甲複方',), (1.0,)),
                (100.0, ('乙複方',), (1.0,)),
                (100.0, ('丙複方',), (1.0,)),
                (100.0, ('丁複方',), (1.0,)),
            ])
            self.assertListEqual(m_gen.call_args_list, [
                mock.call(0, [
                    (0, 100.0, (), ()),
                ]),
            ])

        m_gen.assert_called_with(0, [(0, 100.0, (), ())])

        # depth 2
        searcher._set_context(target_composition, max_cformulas=2, top_n=1,
                              beam_width_factor=1000, beam_multiplier=1)
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates', side_effect=self._se_heur(searcher)), \
             mock.patch.object(searcher, 'generate_unique_combinations_at_depth',
                               wraps=searcher.generate_unique_combinations_at_depth) as m_gen:
            items = list(searcher.generate_combinations())
            self.assertEqual(items, [
                (100.0, (), ()),
                (100.0, ('甲複方',), (1.0,)),
                (100.0, ('乙複方',), (1.0,)),
                (100.0, ('丙複方',), (1.0,)),
                (100.0, ('丁複方',), (1.0,)),
                (100.0, ('甲複方', '乙複方'), (1.0, 1.0)),
                (100.0, ('甲複方', '丙複方'), (1.0, 1.0)),
                (100.0, ('甲複方', '丁複方'), (1.0, 1.0)),
                (100.0, ('乙複方', '丙複方'), (1.0, 1.0)),
                (100.0, ('乙複方', '丁複方'), (1.0, 1.0)),
                (100.0, ('丙複方', '丁複方'), (1.0, 1.0)),
            ])
            self.assertListEqual(m_gen.call_args_list, [
                mock.call(0, [
                    (0, 100.0, (), ()),
                ]),
                mock.call(1, [
                    (0, 100.0, (), ()),
                    (1, 100.0, ('甲複方',), (1.0,)),
                    (1, 100.0, ('乙複方',), (1.0,)),
                    (1, 100.0, ('丙複方',), (1.0,)),
                    (1, 100.0, ('丁複方',), (1.0,)),
                ]),
            ])

        # depth 3
        searcher._set_context(target_composition, max_cformulas=3, top_n=1,
                              beam_width_factor=1000, beam_multiplier=1)
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates', side_effect=self._se_heur(searcher)), \
             mock.patch.object(searcher, 'generate_unique_combinations_at_depth',
                               wraps=searcher.generate_unique_combinations_at_depth) as m_gen:
            items = list(searcher.generate_combinations())
            self.assertEqual(items, [
                (100.0, (), ()),
                (100.0, ('甲複方',), (1.0,)),
                (100.0, ('乙複方',), (1.0,)),
                (100.0, ('丙複方',), (1.0,)),
                (100.0, ('丁複方',), (1.0,)),
                (100.0, ('甲複方', '乙複方'), (1.0, 1.0)),
                (100.0, ('甲複方', '丙複方'), (1.0, 1.0)),
                (100.0, ('甲複方', '丁複方'), (1.0, 1.0)),
                (100.0, ('乙複方', '丙複方'), (1.0, 1.0)),
                (100.0, ('乙複方', '丁複方'), (1.0, 1.0)),
                (100.0, ('丙複方', '丁複方'), (1.0, 1.0)),
                (100.0, ('甲複方', '乙複方', '丙複方'), (1.0, 1.0, 1.0)),
                (100.0, ('甲複方', '乙複方', '丁複方'), (1.0, 1.0, 1.0)),
                (100.0, ('甲複方', '丙複方', '丁複方'), (1.0, 1.0, 1.0)),
                (100.0, ('乙複方', '丙複方', '丁複方'), (1.0, 1.0, 1.0)),
            ])
            self.assertListEqual(m_gen.call_args_list, [
                mock.call(0, [
                    (0, 100.0, (), ()),
                ]),
                mock.call(1, [
                    (0, 100.0, (), ()),
                    (1, 100.0, ('甲複方',), (1.0,)),
                    (1, 100.0, ('乙複方',), (1.0,)),
                    (1, 100.0, ('丙複方',), (1.0,)),
                    (1, 100.0, ('丁複方',), (1.0,)),
                ]),
                mock.call(2, [
                    (0, 100.0, (), ()),
                    (1, 100.0, ('甲複方',), (1.0,)),
                    (1, 100.0, ('乙複方',), (1.0,)),
                    (1, 100.0, ('丙複方',), (1.0,)),
                    (1, 100.0, ('丁複方',), (1.0,)),
                    (2, 100.0, ('甲複方', '乙複方'), (1.0, 1.0)),
                    (2, 100.0, ('甲複方', '丙複方'), (1.0, 1.0)),
                    (2, 100.0, ('甲複方', '丁複方'), (1.0, 1.0)),
                    (2, 100.0, ('乙複方', '丙複方'), (1.0, 1.0)),
                    (2, 100.0, ('乙複方', '丁複方'), (1.0, 1.0)),
                    (2, 100.0, ('丙複方', '丁複方'), (1.0, 1.0)),
                ]),
            ])

    def test_generate_combinations_beam_width(self):
        """Should pass items up to beam width in order of match_pct for each (non-last) depth."""
        def se_eval(combo, *, initial_guess=None):
            return combo, (1.0,) * len(combo), 50.0 + 10 * len(combo)

        database, target_composition = self._sample_data()
        searcher = _searcher.BeamFormulaSearcher(database)

        searcher._set_context(target_composition, max_cformulas=3, top_n=1,
                              beam_width_factor=3, beam_multiplier=10)
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates', side_effect=self._se_heur(searcher)), \
             mock.patch.object(searcher, 'generate_unique_combinations_at_depth',
                               wraps=searcher.generate_unique_combinations_at_depth) as m_gen:
            items = list(searcher.generate_combinations())
            self.assertEqual(items, [
                (100.0, (), ()),
                (70.0, ('甲複方', '乙複方'), (1.0, 1.0)),
                (70.0, ('甲複方', '丙複方'), (1.0, 1.0)),
                (80.0, ('甲複方', '乙複方', '丙複方'), (1.0, 1.0, 1.0)),
                (80.0, ('甲複方', '乙複方', '丁複方'), (1.0, 1.0, 1.0)),
                (80.0, ('甲複方', '丙複方', '丁複方'), (1.0, 1.0, 1.0)),
            ])
            self.assertListEqual(m_gen.call_args_list, [
                mock.call(0, [
                    (0, 100.0, (), ()),
                ]),
                mock.call(1, [
                    (0, 100.0, (), ()),
                    (1, 60.0, ('甲複方',), (1.0,)),
                    (1, 60.0, ('乙複方',), (1.0,)),
                ]),
                mock.call(2, [
                    (0, 100.0, (), ()),
                    (2, 70.0, ('甲複方', '乙複方'), (1.0, 1.0)),
                    (2, 70.0, ('甲複方', '丙複方'), (1.0, 1.0)),
                ]),
            ])

    def test_generate_unique_combinations_at_depth(self):
        """Should remove generated items with same combo set."""
        database, target_composition = self._sample_data()
        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition)
        candidates = [
            (0, 100.0, (), ()),
            (1, 100.0, ('丁複方',), (1.0,)),
            (1, 100.0, ('丙複方',), (1.0,)),
        ]
        gen_values = (
            (0, 100.0, (), ()),
            (1, 100.0, ('丁複方',), (1.0,)),
            (2, 100.0, ('丁複方', '丙複方'), (1.0, 1.0)),
            (2, 100.0, ('丁複方', '乙複方'), (1.0, 1.0)),
            (2, 100.0, ('丁複方', '甲複方'), (1.0, 1.0)),
            (1, 100.0, ('丙複方',), (1.0,)),
            (2, 100.0, ('丙複方', '丁複方'), (1.0, 1.0)),
            (2, 100.0, ('丙複方', '乙複方'), (1.0, 1.0)),
            (2, 100.0, ('丙複方', '甲複方'), (1.0, 1.0)),
            (1, 100.0, ('乙複方',), (1.0,)),
            (2, 100.0, ('乙複方', '丁複方'), (1.0, 1.0)),
            (2, 100.0, ('乙複方', '丙複方'), (1.0, 1.0)),
            (2, 100.0, ('乙複方', '甲複方'), (1.0, 1.0)),
            (1, 100.0, ('甲複方',), (1.0,)),
            (2, 100.0, ('甲複方', '丁複方'), (1.0, 1.0)),
            (2, 100.0, ('甲複方', '丙複方'), (1.0, 1.0)),
            (2, 100.0, ('甲複方', '乙複方'), (1.0, 1.0)),
        )
        with mock.patch.object(searcher, 'generate_combinations_at_depth',
                               return_value=gen_values):
            items = list(searcher.generate_unique_combinations_at_depth(1, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('丁複方',), (1.0,)),
                (2, 100.0, ('丁複方', '丙複方'), (1.0, 1.0)),
                (2, 100.0, ('丁複方', '乙複方'), (1.0, 1.0)),
                (2, 100.0, ('丁複方', '甲複方'), (1.0, 1.0)),
                (1, 100.0, ('丙複方',), (1.0,)),
                (2, 100.0, ('丙複方', '乙複方'), (1.0, 1.0)),
                (2, 100.0, ('丙複方', '甲複方'), (1.0, 1.0)),
                (1, 100.0, ('乙複方',), (1.0,)),
                (2, 100.0, ('乙複方', '甲複方'), (1.0, 1.0)),
                (1, 100.0, ('甲複方',), (1.0,)),
            ])

    def test_generate_combinations_at_depth_basic(self):
        """Should generate items through `generate_heuristic_candidates` for the depth.

        - Should re-generate the input candidates.
        - Should generate candidates extended with one extra formula.
        - Should not extend candidates with smaller depth.
        """
        database, target_composition = self._sample_data()
        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition, top_n=1,
                              beam_width_factor=1, beam_multiplier=10)

        # depth 0
        candidates = [(0, 100.0, (), ())]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval):
            items = list(searcher.generate_combinations_at_depth(0, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('丁複方',), (1.0,)),
                (1, 100.0, ('丙複方',), (1.0,)),
                (1, 100.0, ('乙複方',), (1.0,)),
                (1, 100.0, ('甲複方',), (1.0,)),
            ])

        # depth 1
        candidates = [
            (0, 100.0, (), ()),
            (1, 100.0, ('丁複方',), (1.0,)),
            (1, 100.0, ('丙複方',), (1.0,)),
        ]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval):
            items = list(searcher.generate_combinations_at_depth(1, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('丁複方',), (1.0,)),
                (1, 100.0, ('丙複方',), (1.0,)),
                (2, 100.0, ('丁複方', '丙複方'), (1.0, 1.0)),
                (2, 100.0, ('丁複方', '乙複方'), (1.0, 1.0)),
                (2, 100.0, ('丁複方', '甲複方'), (1.0, 1.0)),
                (2, 100.0, ('丙複方', '丁複方'), (1.0, 1.0)),
                (2, 100.0, ('丙複方', '乙複方'), (1.0, 1.0)),
                (2, 100.0, ('丙複方', '甲複方'), (1.0, 1.0)),
            ])

        # depth 2
        candidates = [
            (0, 100.0, (), ()),
            (1, 100.0, ('丁複方',), (1.0,)),
            (2, 100.0, ('丁複方', '丙複方'), (1.0, 1.0)),
        ]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval):
            items = list(searcher.generate_combinations_at_depth(2, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('丁複方',), (1.0,)),
                (2, 100.0, ('丁複方', '丙複方'), (1.0, 1.0)),
                (3, 100.0, ('丁複方', '丙複方', '乙複方'), (1.0, 1.0, 1.0)),
                (3, 100.0, ('丁複方', '丙複方', '甲複方'), (1.0, 1.0, 1.0)),
            ])

    def test_generate_combinations_at_depth_pool_size_basic(self):
        """Should limit extended combos within pool_size.

        - Expected pool_size ~= (top_n * beam_width_factor) * beam_multiplier
        - Expected quota = ceil((top_n * beam_width_factor) * beam_multiplier / len(next_candidates))
        - Actual pool_size = quota * len(next_candidates)
        """
        database, target_composition = self._sample_data()
        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition, top_n=1,
                              beam_width_factor=2, beam_multiplier=1.5)

        # depth 0
        # Expected quota = ceil((1 * 2) * 1.5 / 1) = 3
        candidates = [(0, 100.0, (), ())]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates',
                               wraps=searcher.generate_heuristic_candidates) as m_heur:
            items = list(searcher.generate_combinations_at_depth(0, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('丁複方',), (1.0,)),
                (1, 100.0, ('丙複方',), (1.0,)),
                (1, 100.0, ('乙複方',), (1.0,)),
            ])
            self.assertListEqual(m_heur.call_args_list, [
                mock.call((), (), 3),
            ])

        # depth 1
        # Expected quota = ceil((1 * 2) * 1.5 / 2) = 2
        candidates = [
            (0, 100.0, (), ()),
            (1, 100.0, ('丁複方',), (1.0,)),
            (1, 100.0, ('丙複方',), (1.0,)),
        ]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates',
                               wraps=searcher.generate_heuristic_candidates) as m_heur:
            items = list(searcher.generate_combinations_at_depth(1, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('丁複方',), (1.0,)),
                (1, 100.0, ('丙複方',), (1.0,)),
                (2, 100.0, ('丁複方', '丙複方'), (1.0, 1.0)),
                (2, 100.0, ('丁複方', '乙複方'), (1.0, 1.0)),
                (2, 100.0, ('丙複方', '丁複方'), (1.0, 1.0)),
                (2, 100.0, ('丙複方', '乙複方'), (1.0, 1.0)),
            ])
            self.assertListEqual(m_heur.call_args_list, [
                mock.call(('丁複方',), (1.0,), 2),
                mock.call(('丙複方',), (1.0,), 2),
            ])

    def test_generate_combinations_at_depth_pool_size_redistribute(self):
        """Should redistribute pool_size among items if they are less than beam_width."""
        database, target_composition = self._sample_data()
        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition, top_n=1,
                              beam_width_factor=2, beam_multiplier=1.5)

        # depth 1
        # Expected quota = ceil((1 * 2) * 1.5 / 1) = 3
        candidates = [
            (0, 100.0, (), ()),
            (1, 100.0, ('丁複方',), (1.0,)),
        ]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates',
                               wraps=searcher.generate_heuristic_candidates) as m_heur:
            combos = list(searcher.generate_combinations_at_depth(1, candidates))
            self.assertEqual(combos, [
                (0, 100.0, (), ()),
                (1, 100.0, ('丁複方',), (1.0,)),
                (2, 100.0, ('丁複方', '丙複方'), (1.0, 1.0)),
                (2, 100.0, ('丁複方', '乙複方'), (1.0, 1.0)),
                (2, 100.0, ('丁複方', '甲複方'), (1.0, 1.0)),
            ])
            self.assertListEqual(m_heur.call_args_list, [
                mock.call(('丁複方',), (1.0,), 3),
            ])

    def test_generate_combinations_at_depth_pool_size_zero(self):
        """Should check all extended combos without heuristic if multiplier = 0"""
        database, target_composition = self._sample_data()
        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition, top_n=1,
                              beam_width_factor=1, beam_multiplier=0)

        # depth 0
        candidates = [(0, 100.0, (), ())]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates',
                               wraps=searcher.generate_heuristic_candidates) as m_heur:
            items = list(searcher.generate_combinations_at_depth(0, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('甲複方',), (1.0,)),
                (1, 100.0, ('乙複方',), (1.0,)),
                (1, 100.0, ('丙複方',), (1.0,)),
                (1, 100.0, ('丁複方',), (1.0,)),
            ])
            m_heur.assert_not_called()

        # depth 1
        candidates = [
            (0, 100.0, (), ()),
            (1, 100.0, ('甲複方',), (1.0,)),
            (1, 100.0, ('乙複方',), (1.0,)),
        ]
        with mock.patch.object(searcher, 'evaluate_combination', side_effect=self._se_eval), \
             mock.patch.object(searcher, 'generate_heuristic_candidates',
                               wraps=searcher.generate_heuristic_candidates) as m_heur:
            items = list(searcher.generate_combinations_at_depth(1, candidates))
            self.assertEqual(items, [
                (0, 100.0, (), ()),
                (1, 100.0, ('甲複方',), (1.0,)),
                (1, 100.0, ('乙複方',), (1.0,)),
                (2, 100.0, ('甲複方', '乙複方'), (1.0, 1.0)),
                (2, 100.0, ('甲複方', '丙複方'), (1.0, 1.0)),
                (2, 100.0, ('甲複方', '丁複方'), (1.0, 1.0)),
                (2, 100.0, ('乙複方', '甲複方'), (1.0, 1.0)),
                (2, 100.0, ('乙複方', '丙複方'), (1.0, 1.0)),
                (2, 100.0, ('乙複方', '丁複方'), (1.0, 1.0)),
            ])
            m_heur.assert_not_called()

    def _check_heuristic_scoring(self, database, target_composition, combo, dosages,
                                 remaining_map, expected_scores, penalty_factor=1):
        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition, penalty_factor=penalty_factor)

        self.assertEqual(searcher._calculate_remaining_map(combo, dosages), remaining_map)

        for formula, score in expected_scores.items():
            self.assertAlmostEqual(
                searcher._calculate_formula_score(formula, remaining_map),
                score,
                places=3,
                msg=f'mismatching score for {formula!r}',
            )

    def test_generate_heuristic_candidates_scoring(self):
        combo = ()
        dosages = ()

        # identical composition ratios should be scored 1
        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 1.0}
        remaining_map = {'甲藥': 1.0}
        expected_scores = {'甲複方': 1.000}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 2.0}}
        target_composition = {'甲藥': 1.0}
        remaining_map = {'甲藥': 1.0}
        expected_scores = {'甲複方': 1.000}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 2.0}
        remaining_map = {'甲藥': 1.0}
        expected_scores = {'甲複方': 1.000}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        # identical composition ratios should be scored 1
        database = {'甲複方': {'甲藥': 1.0, '乙藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 1.0}
        remaining_map = {'甲藥': 0.5, '乙藥': 0.5}
        expected_scores = {'甲複方': 1.000}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        # half match
        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 1.0}
        remaining_map = {'甲藥': 0.5, '乙藥': 0.5}
        expected_scores = {'甲複方': 0.707}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0, '乙藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0, '丁藥': 1.0}
        remaining_map = {'甲藥': 0.25, '乙藥': 0.25, '丙藥': 0.25, '丁藥': 0.25}
        expected_scores = {'甲複方': 0.707}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        # thirds match
        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0}
        remaining_map = {'甲藥': 1 / 3, '乙藥': 1 / 3, '丙藥': 1 / 3}
        expected_scores = {'甲複方': 0.577}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 2.0, '乙藥': 1.0}
        remaining_map = {'甲藥': 2 / 3, '乙藥': 1 / 3}
        expected_scores = {'甲複方': 0.894}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 2.0}
        remaining_map = {'甲藥': 1 / 3, '乙藥': 2 / 3}
        expected_scores = {'甲複方': 0.447}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        # quarter match
        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0, '丁藥': 1.0}
        remaining_map = {'甲藥': 0.25, '乙藥': 0.25, '丙藥': 0.25, '丁藥': 0.25}
        expected_scores = {'甲複方': 0.5}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 3.0, '乙藥': 1.0}
        remaining_map = {'甲藥': 0.75, '乙藥': 0.25}
        expected_scores = {'甲複方': 0.949}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 3.0}
        remaining_map = {'甲藥': 0.25, '乙藥': 0.75}
        expected_scores = {'甲複方': 0.316}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        # over match
        database = {'甲複方': {'甲藥': 1.0, '乙藥': 1.0}}
        target_composition = {'甲藥': 1.0}
        remaining_map = {'甲藥': 1.0}
        expected_scores = {'甲複方': 0.707}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0, '丁藥': 1.0}}
        target_composition = {'甲藥': 1.0, '乙藥': 1.0}
        remaining_map = {'甲藥': 0.5, '乙藥': 0.5}
        expected_scores = {'甲複方': 0.707}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        database = {'甲複方': {'甲藥': 1.0, '乙藥': 3.0}}
        target_composition = {'甲藥': 1.0}
        remaining_map = {'甲藥': 1.0}
        expected_scores = {'甲複方': 0.316}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        # empty target should be scored 0
        database = {'甲複方': {'甲藥': 1.0}}
        target_composition = {}
        remaining_map = {}
        expected_scores = {'甲複方': 0.0}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

        # empty formula should be scored 0 (should not happen)
        database = {'甲複方': {}}
        target_composition = {'甲藥': 1.0}
        remaining_map = {'甲藥': 1.0}
        expected_scores = {'甲複方': 0.0}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores)

    def test_generate_heuristic_candidates_scoring_with_penalty(self):
        combo = ()
        dosages = ()

        database = {'甲複方': {'甲藥': 1.0, '乙藥': 1.0}}
        target_composition = {'甲藥': 1.0}
        remaining_map = {'甲藥': 1.0}
        expected_scores = {'甲複方': 0.447}
        self._check_heuristic_scoring(database, target_composition, combo, dosages,
                                      remaining_map, expected_scores, penalty_factor=2.0)

    def test_generate_heuristic_candidates_single_main_herb(self):
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
            '乙複方': {'乙藥': 1.0, '丙藥': 1.0},
            '丙複方': {'甲藥': 2.0, '丙藥': 1.0},
            '甲單方': {'甲藥': 3.0},  # sformula should be ignored
        }
        target_composition = {'甲藥': 10.0, '乙藥': 1.5, '丙藥': 1.0}
        combo = ()
        dosages = ()

        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition)

        # check for expected remaining_map
        remaining_map = {
            '甲藥': np.float64(0.8),
            '乙藥': np.float64(0.12),
            '丙藥': np.float64(0.08),
        }
        self.assertEqual(searcher._calculate_remaining_map(combo, dosages), remaining_map)

        # check for expected scores
        self.assertAlmostEqual(searcher._calculate_formula_score('甲複方', remaining_map), 0.800, places=3)
        self.assertAlmostEqual(searcher._calculate_formula_score('乙複方', remaining_map), 0.174, places=3)
        self.assertAlmostEqual(searcher._calculate_formula_score('丙複方', remaining_map), 0.924, places=3)

        # check for expected order by scores
        # should limit generated item number within `quota`
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=1)),
            ['丙複方'],
        )
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=2)),
            ['丙複方', '甲複方'],
        )
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=3)),
            ['丙複方', '甲複方', '乙複方'],
        )

    def test_generate_heuristic_candidates_multi_main_herbs(self):
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
            '乙複方': {'乙藥': 1.0, '丙藥': 1.0},
            '丙複方': {'甲藥': 2.0, '丙藥': 1.0},
            '甲單方': {'甲藥': 3.0},  # sformula should be ignored
        }
        target_composition = {'甲藥': 4.0, '乙藥': 4.0, '丙藥': 2.0}
        combo = ()
        dosages = ()

        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition)

        # check for expected remaining_map
        remaining_map = {
            '甲藥': np.float64(0.4),
            '乙藥': np.float64(0.4),
            '丙藥': np.float64(0.2),
        }
        self.assertEqual(searcher._calculate_remaining_map(combo, dosages), remaining_map)

        # check for expected scores
        self.assertAlmostEqual(searcher._calculate_formula_score('甲複方', remaining_map), 0.943, places=3)
        self.assertAlmostEqual(searcher._calculate_formula_score('乙複方', remaining_map), 0.707, places=3)
        self.assertAlmostEqual(searcher._calculate_formula_score('丙複方', remaining_map), 0.745, places=3)

        # check for expected order by scores
        # should limit generated item number within `quota`
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=1)),
            ['甲複方'],
        )
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=2)),
            ['甲複方', '丙複方'],
        )
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=3)),
            ['甲複方', '丙複方', '乙複方'],
        )

    def test_generate_heuristic_candidates_deep(self):
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 0.5},
            '乙複方': {'乙藥': 1.0, '丙藥': 0.5},
            '丙複方': {'甲藥': 1.0, '丙藥': 1.0},
        }
        target_composition = {'甲藥': 1.0, '乙藥': 1.0, '丙藥': 1.0}
        combo = ('甲複方',)
        dosages = (1.0,)

        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition)

        # check for expected remaining_map
        # remaining dose = {'乙藥': 0.5, '丙藥': 1.0}
        remaining_map = {
            '乙藥': np.float64(0.3333333333333333),
            '丙藥': np.float64(0.6666666666666666),
        }
        self.assertEqual(searcher._calculate_remaining_map(combo, dosages), remaining_map)

        # check for expected scores
        self.assertAlmostEqual(searcher._calculate_formula_score('乙複方', remaining_map), 0.800, places=3)
        self.assertAlmostEqual(searcher._calculate_formula_score('丙複方', remaining_map), 0.632, places=3)

        # check for expected order by scores
        # should limit generated item number within `quota`
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=1)),
            ['乙複方'],
        )
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=2)),
            ['乙複方', '丙複方'],
        )

    def test_generate_heuristic_candidates_empty_remaining(self):
        database = {
            '甲複方': {'甲藥': 1.0, '乙藥': 1.0},
            '乙複方': {'乙藥': 1.0, '丙藥': 0.5},
            '丙複方': {'甲藥': 1.0, '丙藥': 1.0},
        }
        target_composition = {'甲藥': 1.0, '乙藥': 1.0}
        combo = ('甲複方',)
        dosages = (1.0,)

        searcher = _searcher.BeamFormulaSearcher(database)
        searcher._set_context(target_composition)

        # check for expected remaining_map
        remaining_map = {}
        self.assertEqual(searcher._calculate_remaining_map(combo, dosages), remaining_map)

        # skip generating if remaining_map is empty
        self.assertEqual(
            list(searcher.generate_heuristic_candidates(combo, dosages, quota=1)),
            [],
        )
