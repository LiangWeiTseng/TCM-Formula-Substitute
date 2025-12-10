import heapq
import logging
import os
from abc import ABC, abstractmethod
from contextlib import nullcontext
from functools import cached_property
from itertools import combinations
from math import sqrt

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
    DEFAULT_TOP_N = 5

    def __init__(self, database, target_composition, *,
                 excludes=None, max_cformulas=2, max_sformulas=2, penalty_factor=2.0, places=1):
        self.database = database
        self.target_composition = target_composition
        self.excludes = set() if excludes is None else excludes
        self.max_cformulas = max_cformulas
        self.max_sformulas = max_sformulas
        self.penalty_factor = penalty_factor
        self.places = places
        self.evaluate_cache = {}

    def find_best_matches(self, top_n=None):
        top_n = self.DEFAULT_TOP_N if top_n is None else top_n
        gen = self.find_unique_matches()
        matches = heapq.nlargest(top_n, gen, key=lambda x: x[0])
        return matches

    def find_unique_matches(self):
        log.debug('目標組成: %s', self.target_composition)
        log.debug('排除品項: %s', self.excludes)
        log.debug('總數: %i; 相關複方: %i; 相關單方: %i', len(self.database), len(self.cformulas), len(self.sformulas))

        self.evaluate_cache = {}
        combos = set()
        for match_pct, combo, dosages in self.find_matches():
            key = frozenset(combo)
            if key in combos:
                log.debug('略過重複項目: %s', combo)
                continue
            combos.add(key)
            log.debug('輸出: %s %s (%.2f%%)', combo, dosages, match_pct)
            yield match_pct, combo, dosages

    def find_matches(self):
        for combo in self.generate_combinations():
            if combo:
                try:
                    combo, dosages, match_pct = self.evaluate_combination(combo)
                except ValueError as exc:
                    log.debug('略過錯誤項目: %s', combo, exc)
                    continue
            else:
                dosages = ()

            for extended_combo in self.generate_combinations_for_sformulas(combo, dosages):
                if extended_combo != combo:
                    try:
                        extended_combo, dosages, match_pct = self.evaluate_combination(extended_combo)
                    except ValueError as exc:
                        log.debug('略過錯誤項目: %s', extended_combo, exc)
                        continue
                yield match_pct, extended_combo, dosages

    @abstractmethod
    def generate_combinations(self):
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

    def get_formula_composition(self, formulas, dosages):
        composition = {}
        for formula, dosage in zip(formulas, dosages):
            for herb, amount in self.database[formula].items():
                composition[herb] = composition.get(herb, 0) + amount * dosage
        return composition

    def calculate_variance(self, composition):
        return sqrt(sum(amount**2 for amount in composition.values()))

    def calculate_delta(self, x, combo, target_composition=None):
        """計算待測劑量組成與目標劑量組成的差異值

        將待測中藥劑量與目標中藥劑量分別視為多維空間中的二個點:
        X(x1, x2, x3, ...), Y(y1, y2, y3, ...)，
        delta 表示二點在多維空間中的直線距離，值越小表示二點越接近，0 為最佳。

        非目標組成的中藥其貢獻度另外乘上 penalty_factor。

        註：亦可改為以 delta^2 作為最小化目標，此即殘差平方和 (sum of squared
        residuals, SSR)，可於迭代時省略開平方的開銷，且有專門最佳化過的
        scipy.optimize.lsq_linear 函數及演算法可利用，但須全面把數據向量化，代
        價是記憶體開銷較大（大約為資料庫總方劑數 * 總中藥數 * N），且需全面改
        用較難理解的矩陣運算，考量實務上 beam search 速度已夠快，暫無必要進一
        步最佳化。目前實測 scipy.optimize.minimize 處理 delta 比 SSR 快，可能
        是對此演算法而言一次函數在目標值附近比較容易估算梯度所致，因此這裡仍採
        用 delta。
        """
        target = self.target_composition if target_composition is None else target_composition
        combined_composition = self.get_formula_composition(combo, x)

        delta = 0
        for herb, target_amount in target.items():
            combined_amount = combined_composition.get(herb, 0)
            delta += (target_amount - combined_amount) ** 2

        for herb, amount in combined_composition.items():
            if herb not in target:
                delta += (amount * self.penalty_factor) ** 2

        return sqrt(delta)

    def find_best_dosages(self, combo, target_composition=None, *, initial_guess=None,
                          bounds=None, options=None):
        initial_guess = np.ones(len(combo)) if initial_guess is None else initial_guess
        bounds = [(0, 50) for _ in combo] if bounds is None else bounds
        options = {
            'ftol': 10 ** (-self.places - 2),
            'disp': False,
        } if options is None else options
        result = minimize(self.calculate_delta, initial_guess, args=(combo, target_composition),
                          method='SLSQP', bounds=bounds, options=options)
        if not result.success:
            raise ValueError(f'Unable to find best dosages: {result.message}')
        return result.x, result.fun

    def calculate_match_ratio(self, delta, variance=None):
        """將待測劑量組成與目標劑量組成的差異值轉化為匹配度

        將待測中藥劑量與目標中藥劑量分別視為多維空間中的二個點:
        X(x1, x2, x3, ...), Y(y1, y2, y3, ...)，
        以變異數 (variance)，即 Y 與原點之距離，作為標準化參數。

        差異值為 0 時定義為完全匹配 (1.0)；差異值與變異數相等表示 X 與 Y 的距離
        和 Y 與原點的距離相當，定義為完全不匹配 (0.0)；差異值大於變異數則定義為
        負匹配，表示「比完全不匹配更差」。
        """
        variance = self.variance if variance is None else variance
        return (1.0 - delta / variance) if variance != 0 else 1.0

    def calculate_match(self, combo, **opts):
        key = frozenset(combo)
        try:
            result = self.evaluate_cache[key]
        except KeyError:
            result = None

        if result is None:
            log.debug('精算: %s', combo)
            if combo:
                try:
                    result = self._calculate_match(combo, **opts)
                except ValueError as exc:
                    log.debug('無法計算匹配劑量: %s: %s', combo, exc)
                    result = exc
            else:
                result = (), 0.0, 100.0

            self.evaluate_cache[key] = result

        if isinstance(result, Exception):
            raise result

        return result

    def _calculate_match(self, combo, target_composition=None, **opts):
        dosages, delta = self.find_best_dosages(combo, target_composition, **opts)
        variance = (None if target_composition is None
                    else self.calculate_variance(target_composition))
        match_pct = self.calculate_match_ratio(delta, variance) * 100
        return dosages, delta, match_pct

    def evaluate_combination(self, combo, *, initial_guess=None):
        # raise ValueError if unable to find minimal dosages
        dosages, delta, match_pct = self.calculate_match(combo, initial_guess=initial_guess)
        dosages = np.round(dosages, self.places)
        log.debug('估值: %s %s: %.3f (%.2f%%)', combo, dosages, delta, match_pct)

        # remove formulas with 0 dosage
        fixed_combo, fixed_dosages = combo, dosages
        _fixed_combo = None
        while fixed_combo != _fixed_combo:
            _fixed_combo = fixed_combo

            non_zero_mask = fixed_dosages != 0
            if np.all(non_zero_mask):
                break

            fixed_combo = tuple(np.array(fixed_combo, dtype=object)[non_zero_mask])
            fixed_dosages = fixed_dosages[non_zero_mask]
            fixed_dosages, delta, match_pct = self.calculate_match(fixed_combo, initial_guess=fixed_dosages)
            fixed_dosages = np.round(fixed_dosages, self.places)

        log.debug('校正: %s %s: %.3f (%.2f%%)', fixed_combo, np.round(fixed_dosages, self.places), delta, match_pct)

        return fixed_combo, fixed_dosages, match_pct

    def generate_combinations_for_sformulas(self, combo, dosages):
        combined_composition = self.get_formula_composition(combo, dosages)
        remaining_composition = {
            herb: amount - combined_composition.get(herb, 0)
            for herb, amount in self.target_composition.items()
        }

        weighted_herbs = sorted(remaining_composition.items(), key=lambda item: -item[1])
        candidate_herbs = tuple(
            herb for herb, amount in weighted_herbs
            if herb in self.herb_sformulas and np.round(amount, self.places) > 0
        )
        candidate_herbs_count = len(candidate_herbs)

        stack = [(0, combo)]
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
    def generate_combinations(self):
        for i in range(0, min(len(self.cformulas), self.max_cformulas) + 1):
            for c in combinations(self.cformulas, i):
                yield c
