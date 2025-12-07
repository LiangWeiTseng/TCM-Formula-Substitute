import unittest
from io import StringIO
from textwrap import dedent
from unittest import mock

import numpy

from formula_altsearch import searcher


class TestUtilities(unittest.TestCase):
    def test_load_formula_database(self):
        database = searcher.load_formula_database(StringIO(dedent(
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
        database = searcher.load_formula_database(StringIO(dedent(
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

    @mock.patch.object(searcher, 'log')
    def test_load_formula_database_duplicated_key(self, m_log):
        """Should ignore an item with a duplicated key."""
        database = searcher.load_formula_database(StringIO(dedent(
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

    @mock.patch.object(searcher, 'ExhaustiveFormulaSearcher')
    def test_find_best_matches(self, m_cls):
        database = {}
        target_composition = {}
        penalty_factor = 2
        searcher.find_best_matches(
            database, target_composition,
            excludes=None, penalty_factor=penalty_factor)

        m_cls.assert_called_with(database, target_composition, excludes=None, penalty_factor=2)
        m_cls().find_best_matches.assert_called_with(5)


class TestFormulaSearcher(unittest.TestCase):
    def test_compute_related_formulas(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '麻黃湯': {'麻黃': 0.9, '桂枝': 0.6, '炙甘草': 0.3, '杏仁': 0.5},
            '桂枝': {'桂枝': 1}, '白芍': {'白芍': 1}, '生薑': {'生薑': 0.8},
        }

        # filter by target_composition
        target_composition = {
            '白芍': 1.0, '杏仁': 1.0,
        }
        finder = searcher.ExhaustiveFormulaSearcher(database, target_composition)
        self.assertEqual(finder.cformulas, ['桂枝湯', '麻黃湯'])
        self.assertEqual(finder.sformulas, ['白芍'])

        # filter by excludes
        target_composition = {
            '桂枝': 1.0, '白芍': 1.0, '生薑': 0.8,
        }
        finder = searcher.ExhaustiveFormulaSearcher(database, target_composition, excludes={'白芍'})
        self.assertEqual(finder.cformulas, ['桂枝湯', '桂枝去芍藥湯', '麻黃湯'])
        self.assertEqual(finder.sformulas, ['桂枝', '生薑'])

    def test_generate_combinations(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '麻黃湯': {'麻黃': 0.9, '桂枝': 0.6, '灸甘草': 0.3, '杏仁': 0.5},
            '桂枝': {'桂枝': 1}, '白芍': {'白芍': 1}, '生薑': {'生薑': 0.8},
        }
        target_composition = {
            '桂枝': 1.0, '白芍': 1.0, '杏仁': 1.0,
        }

        finder = searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=3, max_sformulas=0)
        self.assertEqual(list(finder.generate_combinations()), [
            ('桂枝湯',), ('桂枝去芍藥湯',), ('麻黃湯',),
            ('桂枝湯', '桂枝去芍藥湯'), ('桂枝湯', '麻黃湯'), ('桂枝去芍藥湯', '麻黃湯'),
            ('桂枝湯', '桂枝去芍藥湯', '麻黃湯'),
        ])

        finder = searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=1, max_sformulas=0)
        self.assertEqual(list(finder.generate_combinations()), [
            ('桂枝湯',), ('桂枝去芍藥湯',), ('麻黃湯',),
        ])

        finder = searcher.ExhaustiveFormulaSearcher(database, target_composition, max_cformulas=0, max_sformulas=3)
        self.assertEqual(list(finder.generate_combinations()), [
            ('桂枝',), ('白芍',), ('桂枝', '白芍')
        ])

    def test_calculate_delta(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }
        combination = ['桂枝湯', '桂枝去芍藥湯']
        penalty_factor = 2

        finder = searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)

        x = [1, 1]
        self.assertEqual(finder.calculate_delta(x, combination), 0.6)

        x = [2, 0]
        self.assertEqual(finder.calculate_delta(x, combination), 0)

        x = [0, 2]
        self.assertEqual(finder.calculate_delta(x, combination), 1.2)

    def test_calculate_delta_with_penalty(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }
        combination = ['桂枝湯', '桂枝去芍藥湯']
        penalty_factor = 2

        finder = searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)

        x = [1, 1]
        self.assertAlmostEqual(finder.calculate_delta(x, combination), 1.2)

        x = [2, 0]
        self.assertAlmostEqual(finder.calculate_delta(x, combination), 2.4)

        x = [0, 2]
        self.assertAlmostEqual(finder.calculate_delta(x, combination), 0)

    def test_find_best_dosages(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '苓桂朮甘湯': {'桂枝': 1, '茯苓': 1, '白朮': 0.8, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }
        penalty_factor = 2

        combination = ['桂枝湯', '桂枝去芍藥湯']
        finder = searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)
        dosages, delta = finder.find_best_dosages(combination)
        numpy.testing.assert_allclose(dosages, [2, 0], atol=1e-5)
        self.assertAlmostEqual(delta, 0, places=5)

        combination = ['桂枝去芍藥湯', '桂枝湯']
        dosages, delta = finder.find_best_dosages(combination)
        numpy.testing.assert_allclose(dosages, [0, 2], atol=1e-5)
        self.assertAlmostEqual(delta, 0, places=5)

        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8, '白朮': 1.0,
        }
        combination = ['桂枝湯', '桂枝去芍藥湯']
        finder = searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)
        dosages, delta = finder.find_best_dosages(combination)
        numpy.testing.assert_allclose(dosages, [2, 0], atol=1e-5)
        self.assertAlmostEqual(delta, 1, places=5)

    def test_calculate_match_ratio(self):
        # calculate using variance when provided
        finder = searcher.ExhaustiveFormulaSearcher({}, {})
        self.assertAlmostEqual(finder.calculate_match_ratio(0.0, 1.0), 1.0)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.1, 1.0), 0.9)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.5, 1.0), 0.5)
        self.assertAlmostEqual(finder.calculate_match_ratio(1.0, 1.0), 0.0)

        self.assertAlmostEqual(finder.calculate_match_ratio(0.0, 0.5), 1.0)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.1, 0.5), 0.8)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.5, 0.5), 0.0)
        self.assertAlmostEqual(finder.calculate_match_ratio(1.0, 0.5), -1.0)

        self.assertAlmostEqual(finder.calculate_match_ratio(0.0, 0), 1)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.1, 0), 1)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.5, 0), 1)
        self.assertAlmostEqual(finder.calculate_match_ratio(1.0, 0), 1)

        # calculate using self variance when not provided
        finder = searcher.ExhaustiveFormulaSearcher({}, {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        })
        self.assertAlmostEqual(finder.calculate_match_ratio(0.0), 1.0)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.01), 0.9959038403974048)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.1), 0.9590384039740479)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.5), 0.7951920198702399)
        self.assertAlmostEqual(finder.calculate_match_ratio(1.0), 0.5903840397404798)

        finder = searcher.ExhaustiveFormulaSearcher({}, {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8, '杏仁': 1.0,
        })
        self.assertAlmostEqual(finder.calculate_match_ratio(0.0), 1.0)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.01), 0.9962095097821054)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.1), 0.9620950978210548)
        self.assertAlmostEqual(finder.calculate_match_ratio(0.5), 0.8104754891052741)
        self.assertAlmostEqual(finder.calculate_match_ratio(1.0), 0.6209509782105482)

    def test_find_best_matches(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
        }
        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8,
        }
        penalty_factor = 2

        # without excludes
        finder = searcher.ExhaustiveFormulaSearcher(
            database, target_composition, penalty_factor=penalty_factor)
        best_matches = finder.find_best_matches()

        self.assertEqual(len(best_matches), 3)

        match_percentage, combination, dosages = best_matches[0]
        self.assertAlmostEqual(match_percentage, 99.99999987830432)
        self.assertEqual(combination, ('桂枝湯',))
        numpy.testing.assert_allclose(dosages, [2], atol=1e-4)

        match_percentage, combination, dosages = best_matches[1]
        self.assertAlmostEqual(match_percentage, 99.99997698778694)
        self.assertEqual(combination, ('桂枝湯', '桂枝去芍藥湯'))
        numpy.testing.assert_allclose(dosages, [2, 0], atol=1e-4)

        match_percentage, combination, dosages = best_matches[2]
        self.assertAlmostEqual(match_percentage, 50.84608476251202)
        self.assertEqual(combination, ('桂枝去芍藥湯',))
        numpy.testing.assert_allclose(dosages, [2], atol=1e-4)

        # with excludes
        finder = searcher.ExhaustiveFormulaSearcher(
            database, target_composition, excludes={'桂枝湯'}, penalty_factor=penalty_factor)
        best_matches = finder.find_best_matches()

        self.assertEqual(len(best_matches), 1)

        match_percentage, combination, dosages = best_matches[0]
        self.assertAlmostEqual(match_percentage, 50.84608476251202)
        self.assertEqual(combination, ('桂枝去芍藥湯',))
        numpy.testing.assert_allclose(dosages, [2], atol=1e-4)
