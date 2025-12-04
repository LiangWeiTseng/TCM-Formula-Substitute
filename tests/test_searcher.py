import unittest

import numpy

from formula_altsearch import searcher


class TestUtilities(unittest.TestCase):
    def test_all_combinations(self):
        database = {
            '桂枝湯': {'桂枝': 0.6, '白芍': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '桂枝去芍藥湯': {'桂枝': 0.6, '生薑': 0.6, '大棗': 0.5, '炙甘草': 0.4},
            '麻黃湯': {'麻黃': 0.9, '桂枝': 0.6, '炙甘草': 0.3, '杏仁': 0.5},
        }

        # basic
        self.assertEqual(list(searcher.all_combinations(database)), [
            ('桂枝湯',), ('桂枝去芍藥湯',), ('麻黃湯',),
            ('桂枝湯', '桂枝去芍藥湯'), ('桂枝湯', '麻黃湯'), ('桂枝去芍藥湯', '麻黃湯'),
        ])

        # filter by target_composition
        target_composition = {
            '白芍': 1.0, '杏仁': 1.0,
        }
        self.assertEqual(list(searcher.all_combinations(database, target_composition)), [
            ('桂枝湯',), ('麻黃湯',), ('桂枝湯', '麻黃湯'),
        ])

        target_composition = {
            '紫蘇': 1.0,
        }
        self.assertEqual(list(searcher.all_combinations(database, target_composition)), [])

        # filter by excludes
        excludes = {'桂枝湯'}
        self.assertEqual(list(searcher.all_combinations(database, excludes=excludes)), [
            ('桂枝去芍藥湯',), ('麻黃湯',), ('桂枝去芍藥湯', '麻黃湯'),
        ])

        excludes = {'桂枝去芍藥湯'}
        self.assertEqual(list(searcher.all_combinations(database, excludes=excludes)), [
            ('桂枝湯',), ('麻黃湯',), ('桂枝湯', '麻黃湯'),
        ])

        excludes = {'桂枝湯', '桂枝去芍藥湯'}
        self.assertEqual(list(searcher.all_combinations(database, excludes=excludes)), [
            ('麻黃湯',),
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

        x = [1, 1]
        delta = searcher.calculate_delta(x, target_composition, combination, database, penalty_factor)
        self.assertEqual(delta, 0.36)

        x = [2, 0]
        delta = searcher.calculate_delta(x, target_composition, combination, database, penalty_factor)
        self.assertEqual(delta, 0)

        x = [0, 2]
        delta = searcher.calculate_delta(x, target_composition, combination, database, penalty_factor)
        self.assertEqual(delta, 1.44)

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

        x = [1, 1]
        delta = searcher.calculate_delta(x, target_composition, combination, database, penalty_factor)
        self.assertEqual(delta, 2)

        x = [2, 0]
        delta = searcher.calculate_delta(x, target_composition, combination, database, penalty_factor)
        self.assertEqual(delta, 2)

        x = [0, 2]
        delta = searcher.calculate_delta(x, target_composition, combination, database, penalty_factor)
        self.assertEqual(delta, 2)

    def test_calculate_match(self):
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
        match_percentage, _combination, dosages = searcher.calculate_match(target_composition, combination, database, penalty_factor)
        self.assertAlmostEqual(match_percentage, 100)
        self.assertIs(_combination, combination)
        numpy.testing.assert_allclose(dosages, [2, 0], atol=1e-12)

        combination = ['桂枝去芍藥湯', '桂枝湯']
        match_percentage, _combination, dosages = searcher.calculate_match(target_composition, combination, database, penalty_factor)
        self.assertAlmostEqual(match_percentage, 100)
        self.assertIs(_combination, combination)
        numpy.testing.assert_allclose(dosages, [0, 2], atol=1e-12)

        target_composition = {
            '桂枝': 1.2, '白芍': 1.2, '生薑': 1.2, '大棗': 1.0, '炙甘草': 0.8, '白朮': 1.0,
        }
        combination = ['桂枝湯', '桂枝去芍藥湯']
        match_percentage, _combination, dosages = searcher.calculate_match(target_composition, combination, database, penalty_factor)
        self.assertAlmostEqual(match_percentage, 99)
        self.assertIs(_combination, combination)
        numpy.testing.assert_allclose(dosages, [2, 0], atol=1e-12)

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
        best_matches, _elapsed = searcher.find_best_matches(
            database, target_composition,
            excludes=None, penalty_factor=penalty_factor)

        self.assertEqual(len(best_matches), 3)

        match_percentage, combination, dosages = best_matches[0]
        self.assertAlmostEqual(match_percentage, 100)
        self.assertEqual(combination, ('桂枝湯',))
        numpy.testing.assert_allclose(dosages, [2], atol=1e-12)

        match_percentage, combination, dosages = best_matches[1]
        self.assertAlmostEqual(match_percentage, 100)
        self.assertEqual(combination, ('桂枝湯', '桂枝去芍藥湯'))
        numpy.testing.assert_allclose(dosages, [2, 0], atol=1e-12)

        match_percentage, combination, dosages = best_matches[2]
        self.assertAlmostEqual(match_percentage, 98.56)
        self.assertEqual(combination, ('桂枝去芍藥湯',))
        numpy.testing.assert_allclose(dosages, [2], atol=1e-12)

        # with excludes
        best_matches, _elapsed = searcher.find_best_matches(
            database, target_composition,
            excludes={'桂枝湯'}, penalty_factor=penalty_factor)

        self.assertEqual(len(best_matches), 1)

        match_percentage, combination, dosages = best_matches[0]
        self.assertAlmostEqual(match_percentage, 98.56)
        self.assertEqual(combination, ('桂枝去芍藥湯',))
        numpy.testing.assert_allclose(dosages, [2], atol=1e-12)
