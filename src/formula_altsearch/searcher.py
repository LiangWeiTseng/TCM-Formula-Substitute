import heapq
import logging
import os
from abc import ABC, abstractmethod
from contextlib import nullcontext
from functools import cached_property
from itertools import combinations

import numpy as np
import yaml
from scipy.optimize import minimize

DEFAULT_DATAFILE = os.path.normpath(os.path.join(__file__, '..', 'database.yaml'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
log = logging.getLogger(__name__)


def load_formula_database(file):
    try:
        # file is a path-like object
        _fh = open(file, 'r', encoding='utf-8')
    except TypeError:
        # file is a file-like object
        _fh = nullcontext(file)

    with _fh as fh:
        data = yaml.safe_load(fh)

    return _load_formula_database(data)


def _load_formula_database(data):
    rv = {}

    for _item in data:
        name = _item['name']
        key = _item['key']
        if key in rv:
            log.warning('%s 使用了重複的索引值 %s，將被忽略', repr(name), repr(key), )
            continue

        unit_dosage = _item.get('unit_dosage', 1)
        item = rv[key] = {}
        for herb, amount in _item['composition'].items():
            item[herb] = amount / unit_dosage

    return rv


def find_best_matches(database, target_composition, top_n=5, *args, **kwargs):
    searcher = ExhaustiveFormulaSearcher(database, target_composition, *args, **kwargs)
    return searcher.find_best_matches(top_n)


class FormulaSearcher(ABC):
    def __init__(self, database, target_composition, *,
                 excludes=None, max_cformulas=2, max_sformulas=2, penalty_factor=2.0):
        self.database = database
        self.target_composition = target_composition
        self.excludes = set() if excludes is None else excludes
        self.max_cformulas = max_cformulas
        self.max_sformulas = max_sformulas
        self.penalty_factor = penalty_factor

    @abstractmethod
    def find_best_matches(self, top_n=5):
        pass

    @cached_property
    def variance(self):
        self.__dict__['variance'] = self.calculate_variance(self.target_composition)
        return self.__dict__['variance']

    @cached_property
    def cformulas(self):
        self._compute_related_formulas()
        return self.__dict__['cformulas']

    @cached_property
    def sformulas(self):
        self._compute_related_formulas()
        return self.__dict__['sformulas']

    @cached_property
    def herb_sformulas(self):
        self._compute_related_formulas()
        return self.__dict__['herb_sformulas']

    def _compute_related_formulas(self):
        cformulas = {}
        sformulas = {}
        herb_sformulas = {}
        for item, composition in self.database.items():
            if item in self.excludes:
                continue
            if not any(self.target_composition.get(herb, 0) for herb in composition):
                continue
            if len(composition) > 1:
                cformulas[item] = None
            else:
                sformulas[item] = None
                for herb in composition:
                    herb_sformulas.setdefault(herb, []).append(item)
        self.__dict__['cformulas'] = cformulas
        self.__dict__['sformulas'] = sformulas
        self.__dict__['herb_sformulas'] = herb_sformulas

    def get_combined_composition(self, formulas, dosages):
        combined_composition = {}
        for formula, dosage in zip(formulas, dosages):
            for herb, amount in self.database[formula].items():
                combined_composition[herb] = combined_composition.get(herb, 0) + amount * dosage
        return combined_composition

    def calculate_variance(self, composition):
        return sum(amount**2 for amount in composition.values()) ** 0.5

    def calculate_delta(self, x, combination, target_composition=None):
        target = self.target_composition if target_composition is None else target_composition
        combined_composition = self.get_combined_composition(combination, x)

        delta = 0
        for herb, target_amount in target.items():
            combined_amount = combined_composition.get(herb, 0)
            delta += (target_amount - combined_amount) ** 2

        for herb, amount in combined_composition.items():
            if herb not in target:
                delta += (amount * self.penalty_factor) ** 2

        return delta ** 0.5

    def find_best_dosages(self, combination, target_composition=None, *, initial_guess=None,
                          bounds=None, options=None, places=1):
        initial_guess = [1 for _ in combination] if initial_guess is None else initial_guess
        bounds = [(0, 50) for _ in combination] if bounds is None else bounds
        options = {'ftol': 1e-3, 'eps': 1e-4, 'disp': False} if options is None else options
        result = minimize(self.calculate_delta, initial_guess, args=(combination, target_composition),
                          method='SLSQP', bounds=bounds, options=options)
        if not result.success:
            raise ValueError(f'Unable to find minimal dosages: {result.message}')
        return np.round(result.x, places), result.fun

    def calculate_match_ratio(self, delta, variance=None):
        variance = self.variance if variance is None else variance
        if variance == 0:
            return 1.0
        return 1.0 - delta / variance

    def calculate_match(self, combination, target_composition=None, *, initial_guess=None, bounds=None):
        dosages, delta = self.find_best_dosages(
            combination, target_composition, initial_guess=initial_guess, bounds=bounds)
        variance = (None if target_composition is None
                    else self.calculate_variance(target_composition))
        match_percentage = self.calculate_match_ratio(delta, variance) * 100
        return dosages, delta, match_percentage

    def evaluate_combination(self, combo):
        # raise ValueError if unable to find minimal dosages
        dosages, delta, match_percentage = self.calculate_match(combo)
        log.debug('估值 %s %s: %.3f (%.2f%%)', combo, dosages, delta, match_percentage)

        # remove formulas with 0 dosage
        # raise ValueError if combo/dosages is empty
        fixed_combo, fixed_dosages = zip(*((f, d) for f, d in zip(combo, dosages) if d > 0.05))
        log.debug('校正: %s %s', fixed_combo, np.round(fixed_dosages, 1))

        return fixed_combo, fixed_dosages, match_percentage

    def check_combination(self, combo, checked_combos, *, auto_add=True):
        token = frozenset(combo)
        if token in checked_combos:
            return True
        if auto_add:
            checked_combos.add(token)
        return False

    def generate_combinations_for_sformulas(self, combination, dosages):
        combined_composition = self.get_combined_composition(combination, dosages)
        remaining_composition = {
            herb: amount - combined_composition.get(herb, 0)
            for herb, amount in self.target_composition.items()
        }

        weighted_herbs = sorted(remaining_composition.items(), key=lambda item: -item[1])
        candidate_herbs = tuple(
            herb for herb, amount in weighted_herbs
            if herb in self.herb_sformulas and amount > 0.05
        )
        candidate_herbs_count = len(candidate_herbs)

        stack = [(0, combination)]
        while stack:
            n, combo = stack.pop()
            if n >= self.max_sformulas or n >= candidate_herbs_count:
                if combo:
                    yield combo
                continue

            herb = candidate_herbs[n]
            for sformula in reversed(self.herb_sformulas[herb]):
                stack.append((n + 1, combo + (sformula,)))


class ExhaustiveFormulaSearcher(FormulaSearcher):
    def find_best_matches(self, top_n=5):
        gen = self.find_matches()
        matches = heapq.nlargest(top_n, gen, key=lambda x: x[0])
        return matches

    def find_matches(self):
        log.debug('目標組成: %s', self.target_composition)
        log.debug('排除品項: %s', self.excludes)
        log.debug('總數: %i; 相關複方: %i; 相關單方: %i', len(self.database), len(self.cformulas), len(self.sformulas))

        combos = set()
        for combo in self.generate_combinations():
            if combo:
                try:
                    combo, dosages, match_percentage = self.evaluate_new_combination(combo, combos)
                except ValueError:
                    continue
            else:
                dosages = ()

            for extended_combo in self.generate_combinations_for_sformulas(combo, dosages):
                if extended_combo != combo:
                    try:
                        extended_combo, dosages, match_percentage = self.evaluate_new_combination(extended_combo, combos)
                    except ValueError:
                        continue
                yield match_percentage, extended_combo, dosages

    def generate_combinations(self):
        for i in range(0, min(len(self.cformulas), self.max_cformulas) + 1):
            for c in combinations(self.cformulas, i):
                yield c

    def evaluate_new_combination(self, combo, combos):
        # skip duplicated combination
        # (assuming that `scipy.optimize.minimize` has found the best dosages)
        if self.check_combination(combo, combos):
            log.debug('略過重複組合: %s', combo)
            raise ValueError(f'Duplicated combo: {combo!r}')

        try:
            fixed_combo, dosages, match_percentage = self.evaluate_combination(combo)
        except ValueError as exc:
            log.debug('無法計算 %s 的最佳劑量: %s', combo, exc)
            raise exc

        # skip if fixed combination becomes duplicated
        if fixed_combo != combo and self.check_combination(fixed_combo, combos):
            log.debug('略過重複組合: %s', fixed_combo)
            raise ValueError(f'Duplicated combo: {combo!r}')

        return fixed_combo, dosages, match_percentage
