import heapq
import logging
import os
from abc import ABC, abstractmethod
from contextlib import nullcontext
from itertools import combinations
from math import ceil, sqrt

import numpy as np
import yaml
from scipy.optimize import minimize

DEFAULT_DATAFILE = os.path.normpath(os.path.join(__file__, '..', 'database.yaml'))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
log = logging.getLogger(__name__)

undefined = object()


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


def find_best_matches(database, target_composition, top_n=None, algorithm='beam', **opts):
    beam_opts = {k: v for k, v in {
        'beam_width_factor': opts.pop('beam_width_factor', undefined),
        'beam_multiplier': opts.pop('beam_multiplier', undefined),
    }.items() if v is not undefined}

    if algorithm == 'beam':
        searcher = BeamFormulaSearcher(database)
        return searcher.find_best_matches(top_n, target_composition, **opts, **beam_opts)
    elif algorithm == 'exhaustive':
        searcher = ExhaustiveFormulaSearcher(database)
        return searcher.find_best_matches(top_n, target_composition, **opts)
    else:
        raise ValueError(f'未支援此演算法: {algorithm}')


class FormulaSearcher(ABC):
    DEFAULT_TOP_N = 5

    def __init__(self, database):
        self.database = database

    def _set_context(
        self, target_composition, excludes=None, top_n=None, *,
        max_cformulas=2, max_sformulas=2,
        min_cformula_dose=0.0, min_sformula_dose=0.0,
        max_cformula_dose=50.0, max_sformula_dose=50.0,
        penalty_factor=2.0, places=1,
    ):
        self.target_composition = target_composition
        self.excludes = set() if excludes is None else excludes
        self.max_cformulas = max_cformulas
        self.max_sformulas = max_sformulas
        self.cformula_bounds = (min_cformula_dose, max_cformula_dose)
        self.sformula_bounds = (min_sformula_dose, max_sformula_dose)
        self.penalty_factor = penalty_factor
        self.places = places

        self.evaluate_cache = {}
        self.variance = self.calculate_variance(self.target_composition)

        self._compute_related_formulas()

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
        self.cformulas = cformulas
        self.sformulas = sformulas
        self.herb_sformulas = herb_sformulas

    def find_best_matches(self, top_n=None, *args, **kwargs):
        top_n = self.DEFAULT_TOP_N if top_n is None else top_n
        gen = self.find_unique_matches(*args, top_n=top_n, **kwargs)
        matches = heapq.nlargest(top_n, gen, key=lambda x: x[0])
        return matches

    def find_unique_matches(self, *args, **kwargs):
        self._set_context(*args, **kwargs)

        log.debug('目標組成: %s', self.target_composition)
        log.debug('排除品項: %s', self.excludes)
        log.debug('總數: %i; 相關複方: %i; 相關單方: %i', len(self.database), len(self.cformulas), len(self.sformulas))

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
        bounds = [
            self.sformula_bounds if f in self.sformulas else self.cformula_bounds
            for f in combo
        ] if bounds is None else bounds
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


class BeamFormulaSearcher(FormulaSearcher):
    def _set_context(
        self, target_composition, excludes=None, top_n=None, *,
        beam_width_factor=2.0, beam_multiplier=5.0,
        **opts,
    ):
        top_n = self.DEFAULT_TOP_N if top_n is None else top_n
        super()._set_context(target_composition, excludes, top_n, **opts)
        self.beam_width = max(ceil(beam_width_factor * top_n), 1)
        self.beam_multiplier = beam_multiplier

    def find_matches(self):
        for match_pct, combo, dosages in self.generate_combinations():
            for extended_combo in self.generate_combinations_for_sformulas(combo, dosages):
                if extended_combo != combo:
                    try:
                        extended_combo, dosages, match_pct = self.evaluate_combination(extended_combo)
                    except ValueError as exc:
                        log.debug('略過錯誤項目: %s', extended_combo, exc)
                        continue
                yield match_pct, extended_combo, dosages

    def generate_combinations(self):
        candidates = [(0, 100.0, (), ())]
        for depth in range(self.max_cformulas):
            if depth < self.max_cformulas - 1:
                candidates = heapq.nlargest(
                    self.beam_width,
                    self.generate_unique_combinations_at_depth(depth, candidates),
                    key=lambda x: x[1],
                )
                log.debug('第 %i 層候選: %s', depth, [x[2] for x in candidates])
            else:
                candidates = self.generate_unique_combinations_at_depth(depth, candidates)

        for _, match_pct, combo, dosages in candidates:
            yield match_pct, combo, dosages

    def generate_unique_combinations_at_depth(self, depth, candidates):
        combos = set()
        for item in self.generate_combinations_at_depth(depth, candidates):
            depth, match_pct, combo, dosages = item
            key = frozenset(combo)
            if key in combos:
                log.debug('略過重複項目: %s', combo)
                continue
            combos.add(key)
            log.debug('輸出: [%i] %s %s (%.2f%%)', depth, combo, dosages, match_pct)
            yield item

    def generate_combinations_at_depth(self, depth, candidates):
        next_candidates = []
        for item in candidates:
            yield item

            n, _, combo, dosages = item
            if n >= depth:
                next_candidates.append(item)

        if not next_candidates:
            return

        # pool_size (max combos to evaluate) ~= beam_width * beam_multiplier
        # Share pool_size among next_candidates in case they are less than beam_width.
        # The actual pool_size = quota * len(next_candidates) may be slightly higher than
        # the expected value.
        if self.beam_multiplier > 0:
            quota = ceil(self.beam_width * self.beam_multiplier / len(next_candidates))

        for _, _, combo, dosages in next_candidates:
            combo_set = set(combo)
            gen = (f for f in self.cformulas if f not in combo_set)
            if self.beam_multiplier > 0:
                gen = self.generate_heuristic_candidates(combo, dosages, quota, gen)

            _new_dosages = np.append(dosages, (1.0,))
            for formula in gen:
                new_combo = combo + (formula,)
                try:
                    new_combo, new_dosages, match_pct = self.evaluate_combination(
                        new_combo, initial_guess=_new_dosages)
                except ValueError as exc:
                    log.debug('略過錯誤項目: %s', new_combo, exc)
                    continue

                new_item = depth + 1, match_pct, new_combo, new_dosages
                yield new_item

    def generate_heuristic_candidates(self, combo, dosages, quota, gen):
        remaining_map = self._calculate_remaining_map(combo, dosages)
        log.debug('剩餘組成比: %s', remaining_map)

        candidate_formulas = heapq.nlargest(
            quota,
            gen,
            key=lambda f: self._calculate_formula_score(f, remaining_map),
        )

        for formula in candidate_formulas:
            log.debug('快捷輸出: %s', formula)
            yield formula

    def _calculate_remaining_map(self, combo, dosages):
        combined_composition = self.get_formula_composition(combo, dosages)
        remaining_composition = {
            herb: fixed_amount
            for herb, amount in self.target_composition.items()
            if (fixed_amount := np.round(amount - combined_composition.get(herb, 0), self.places)) > 0
        }
        total = sum(remaining_composition.values())
        return {
            herb: amount / total
            for herb, amount in remaining_composition.items()
        }

    def _calculate_formula_score(self, formula, remaining_map):
        """計算複方評分，以估算其是否適合填補目前的剩餘中藥組成

        評分方式為各中藥佔比與其在剩餘中藥佔比的乘積和，表示此複方的總貢獻度。
        """
        composition = self.database[formula]
        score = 0
        total = sum(composition.values())
        if total == 0:
            return 0
        for herb, amount in composition.items():
            score += remaining_map.get(herb, 0) * amount / total
        log.debug('快捷估值: %s: %.3f', formula, score)
        return score
