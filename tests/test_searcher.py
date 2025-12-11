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

    @mock.patch.object(_searcher, 'ExhaustiveFormulaSearcher')
    def test_find_best_matches(self, m_cls):
        _searcher.find_best_matches({}, {}, excludes=None, penalty_factor=2.0)
        m_cls.assert_called_with({}, {}, excludes=None, penalty_factor=2.0)
        m_cls().find_best_matches.assert_called_with(5)


class TestExhaustiveFormulaSearcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '麻黃湯': {'麻黃': 0.9, '桂枝': 0.6, '炙甘草': 0.3, '杏仁': 0.5},
            '桂枝': {'桂枝': 1}, '白芍': {'白芍': 1}, '生薑': {'生薑': 0.8}, '炙甘草': {'炙甘草': 0.8},
        }

    def test_compute_related_formulas(self):
        # filter by target_composition
        searcher = _searcher.ExhaustiveFormulaSearcher(self.database, {'白芍': 1.0, '杏仁': 1.0})
        self.assertEqual(list(searcher.cformulas), ['桂枝湯', '麻黃湯'])
        self.assertEqual(list(searcher.sformulas), ['白芍'])

        # filter by excludes
        searcher = _searcher.ExhaustiveFormulaSearcher(
            self.database, {'桂枝': 1.0, '白芍': 1.0, '生薑': 0.8}, excludes={'白芍', '桂枝去芍藥湯'})
        self.assertEqual(list(searcher.cformulas), ['桂枝湯', '麻黃湯'])
        self.assertEqual(list(searcher.sformulas), ['桂枝', '生薑'])

    def test_generate_combinations(self):
        target_composition = {
            '桂枝': 1.0, '白芍': 1.0, '杏仁': 1.0,
        }

        searcher = _searcher.ExhaustiveFormulaSearcher(self.database, target_composition, max_cformulas=3, max_sformulas=0)
        self.assertEqual(list(searcher.generate_combinations()), [
            (),
            ('桂枝湯',), ('桂枝去芍藥湯',), ('麻黃湯',),
            ('桂枝湯', '桂枝去芍藥湯'), ('桂枝湯', '麻黃湯'), ('桂枝去芍藥湯', '麻黃湯'),
            ('桂枝湯', '桂枝去芍藥湯', '麻黃湯'),
        ])

        searcher = _searcher.ExhaustiveFormulaSearcher(self.database, target_composition, max_cformulas=1, max_sformulas=0)
        self.assertEqual(list(searcher.generate_combinations()), [
            (), ('桂枝湯',), ('桂枝去芍藥湯',), ('麻黃湯',),
        ])

        searcher = _searcher.ExhaustiveFormulaSearcher(self.database, target_composition, max_cformulas=0, max_sformulas=3)
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

        # should supplement herbs with largest remaining dosage
        searcher = _searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=1, max_sformulas=5)
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
        searcher = _searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=1, max_sformulas=1)
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
        searcher = _searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=1, max_sformulas=0)
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

        searcher = _searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=1, max_sformulas=2, places=1)
        self.assertEqual(list(searcher.generate_combinations_for_sformulas(combo, dosages)), [
            ('芍藥甘草湯',),
        ])

        searcher = _searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=1, max_sformulas=2, places=2)
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
        searcher = _searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=1, max_sformulas=3)
        self.assertEqual(list(searcher.generate_combinations_for_sformulas((), ())), [
            ('桂枝', '白芍'), ('桂枝', '芍藥'), ('桂枝', '炒白芍'),
            ('製桂枝', '白芍'), ('製桂枝', '芍藥'), ('製桂枝', '炒白芍'),
        ])

    def test_calculate_delta(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }

        searcher = _searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=2.0)
        self.assertEqual(searcher.calculate_delta([1, 1], ['桂枝湯', '桂枝去芍藥湯']), 0.6)
        self.assertEqual(searcher.calculate_delta([2, 0], ['桂枝湯', '桂枝去芍藥湯']), 0)
        self.assertEqual(searcher.calculate_delta([0, 2], ['桂枝湯', '桂枝去芍藥湯']), 1.2)

    def test_calculate_delta_with_penalty(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }

        searcher = _searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=2.0)
        self.assertEqual(searcher.calculate_delta([1, 1], ['桂枝湯', '桂枝去芍藥湯']), 1.2)
        self.assertEqual(searcher.calculate_delta([2, 0], ['桂枝湯', '桂枝去芍藥湯']), 2.4)
        self.assertEqual(searcher.calculate_delta([0, 2], ['桂枝湯', '桂枝去芍藥湯']), 0)

    def test_find_best_dosages(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '苓桂朮甘湯': {'桂枝': 1, '茯苓': 1, '白朮': 0.8, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }
        penalty_factor = 2.0

        combo = ['桂枝湯', '桂枝去芍藥湯']
        searcher = _searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)
        dosages, delta = searcher.find_best_dosages(combo)
        np.testing.assert_allclose(dosages, [2, 0], atol=1e-3)
        self.assertAlmostEqual(delta, 0, places=3)

        combo = ['桂枝去芍藥湯', '桂枝湯']
        dosages, delta = searcher.find_best_dosages(combo)
        np.testing.assert_allclose(dosages, [0, 2], atol=1e-3)
        self.assertAlmostEqual(delta, 0, places=3)

        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8, '白朮': 1.0,
        }
        combo = ['桂枝湯', '桂枝去芍藥湯']
        searcher = _searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)
        dosages, delta = searcher.find_best_dosages(combo)
        np.testing.assert_allclose(dosages, [1.997, 0.000], atol=1e-3)
        self.assertAlmostEqual(delta, 1, places=3)

    def test_calculate_match_ratio(self):
        # calculate using variance when provided
        searcher = _searcher.ExhaustiveFormulaSearcher(self.database, {})
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.0, 1.0), 1.0)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.1, 1.0), 0.9)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.5, 1.0), 0.5)
        self.assertAlmostEqual(searcher.calculate_match_ratio(1.0, 1.0), 0.0)

        self.assertAlmostEqual(searcher.calculate_match_ratio(0.0, 0.5), 1.0)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.1, 0.5), 0.8)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.5, 0.5), 0.0)
        self.assertAlmostEqual(searcher.calculate_match_ratio(1.0, 0.5), -1.0)

        self.assertAlmostEqual(searcher.calculate_match_ratio(0.0, 0), 1)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.1, 0), 1)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.5, 0), 1)
        self.assertAlmostEqual(searcher.calculate_match_ratio(1.0, 0), 1)

        # calculate using self.variance when not provided
        searcher = _searcher.ExhaustiveFormulaSearcher(self.database, {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        })
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.0), 1.0)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.01), 0.9959038403974048)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.1), 0.9590384039740479)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.5), 0.7951920198702399)
        self.assertAlmostEqual(searcher.calculate_match_ratio(1.0), 0.5903840397404798)

        searcher = _searcher.ExhaustiveFormulaSearcher(self.database, {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8, '杏仁': 1.0,
        })
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.0), 1.0)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.01), 0.9962095097821054)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.1), 0.9620950978210548)
        self.assertAlmostEqual(searcher.calculate_match_ratio(0.5), 0.8104754891052741)
        self.assertAlmostEqual(searcher.calculate_match_ratio(1.0), 0.6209509782105482)

    def test_find_best_matches(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }
        penalty_factor = 2.0

        # without excludes
        searcher = _searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)
        best_matches = searcher.find_best_matches()

        self.assertEqual(len(best_matches), 2)

        match_pct, combo, dosages = best_matches[0]
        self.assertAlmostEqual(match_pct, 99.99905054425756, places=3)
        self.assertEqual(combo, ('桂枝湯',))
        np.testing.assert_allclose(dosages, [2], atol=1e-3)

        match_pct, combo, dosages = best_matches[1]
        self.assertAlmostEqual(match_pct, 50.84596674545061, places=3)
        self.assertEqual(combo, ('桂枝去芍藥湯',))
        np.testing.assert_allclose(dosages, [2], atol=1e-3)

        # with excludes
        searcher = _searcher.ExhaustiveFormulaSearcher(
            database, target_composition, excludes={'桂枝湯'}, penalty_factor=penalty_factor)
        best_matches = searcher.find_best_matches()

        self.assertEqual(len(best_matches), 1)

        match_pct, combo, dosages = best_matches[0]
        self.assertAlmostEqual(match_pct, 50.84596674545061, places=3)
        self.assertEqual(combo, ('桂枝去芍藥湯',))
        np.testing.assert_allclose(dosages, [2], atol=1e-3)
