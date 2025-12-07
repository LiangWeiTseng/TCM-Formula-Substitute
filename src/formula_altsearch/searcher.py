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
                 excludes=None, max_cformulas=2, max_sformulas=0, penalty_factor=2.0):
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
    def cformulas(self):
        self._compute_related_formulas()
        return self.__dict__['cformulas']

    @cached_property
    def sformulas(self):
        self._compute_related_formulas()
        return self.__dict__['sformulas']

    def _compute_related_formulas(self):
        cformulas = []
        sformulas = []
        for item, composition in self.database.items():
            if item in self.excludes:
                continue
            if not any(self.target_composition.get(herb, 0) for herb in composition):
                continue
            if len(composition) > 1:
                cformulas.append(item)
            else:
                sformulas.append(item)
        self.__dict__['cformulas'] = cformulas
        self.__dict__['sformulas'] = sformulas

    def get_combined_composition(self, formulas, dosages):
        combined_composition = {}
        for formula, dosage in zip(formulas, dosages):
            for herb, amount in self.database[formula].items():
                combined_composition[herb] = combined_composition.get(herb, 0) + amount * dosage
        return combined_composition

    def calculate_delta(self, x, combination):
        combined_composition = self.get_combined_composition(combination, x)

        delta = 0
        for herb, target_amount in self.target_composition.items():
            combined_amount = combined_composition.get(herb, 0)
            delta += (target_amount - combined_amount) ** 2

        non_target_herbs_count = len(set(combined_composition.keys()) - set(self.target_composition.keys()))
        delta += self.penalty_factor * non_target_herbs_count

        return delta

    def calculate_match(self, combination):
        initial_guess = [1 for _ in combination]
        bounds = [(0, 200) for _ in combination]
        result = minimize(self.calculate_delta, initial_guess, args=(combination,), method='SLSQP', bounds=bounds)

        if not result.success:
            return [], 0, 0

        dosages = result.x
        delta = result.fun
        match_percentage = 100 - delta
        return dosages, delta, match_percentage


class ExhaustiveFormulaSearcher(FormulaSearcher):
    def find_best_matches(self, top_n=5):
        gen = self.find_matches()
        matches = heapq.nlargest(top_n, gen, key=lambda x: x[0])
        return matches

    def find_matches(self):
        log.debug('目標組成: %s', self.target_composition)
        log.debug('排除品項: %s', self.excludes)
        log.debug('總數: %i; 相關複方: %i; 相關單方: %i', len(self.database), len(self.cformulas), len(self.sformulas))
        for combo in self.generate_combinations():
            dosages, delta, match_percentage = self.calculate_match(combo)
            log.debug('估值 %s %s: %.3f (%.2f%%)', combo, np.round(dosages, 3), delta, match_percentage)
            yield match_percentage, combo, dosages

    def generate_combinations(self):
        for i1 in range(0, min(len(self.cformulas), self.max_cformulas) + 1):
            for c1 in combinations(self.cformulas, i1):
                for i2 in range(0, min(len(self.sformulas), self.max_sformulas) + 1):
                    for c2 in combinations(self.sformulas, i2):
                        if i1 or i2:
                            yield *c1, *c2
