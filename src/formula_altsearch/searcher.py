import os
import time
from itertools import combinations

import yaml
from scipy.optimize import minimize

DEFAULT_DATAFILE = os.path.normpath(os.path.join(__file__, '..', 'database.yaml'))


def load_formula_database(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        database = yaml.safe_load(file)
    return database


def all_combinations(database, target_composition=None, excludes=None):
    excludes = set() if excludes is None else excludes

    keys = []
    for item, composition in database.items():
        if item in excludes:
            continue
        if target_composition is not None and not any(herb in target_composition for herb in composition):
            continue
        keys.append(item)

    for i in range(1, min(len(keys), 2) + 1):
        yield from combinations(keys, i)


def calculate_delta(x, target_composition, combination, database, penalty_factor):
    combined_composition = {}
    for i, formula in enumerate(combination):
        for herb, amount in database[formula].items():
            combined_composition[herb] = combined_composition.get(herb, 0) + amount * x[i]

    delta = 0
    for herb, target_amount in target_composition.items():
        combined_amount = combined_composition.get(herb, 0)
        delta += (target_amount - combined_amount) ** 2

    non_target_herbs_count = len(set(combined_composition.keys()) - set(target_composition.keys()))
    delta += penalty_factor * non_target_herbs_count

    return delta


def calculate_match(target_composition, combination, database, penalty_factor):
    initial_guess = [1 for _ in combination]
    bounds = [(0, 200) for _ in combination]
    result = minimize(calculate_delta, initial_guess, args=(target_composition, combination, database, penalty_factor), method='SLSQP', bounds=bounds)

    if not result.success:
        return 0, combination, []

    match_percentage = 100 - result.fun
    dosages = result.x
    return match_percentage, combination, dosages


def find_best_matches(database, target_composition, excludes, penalty_factor, top_n=5):
    all_possible_combinations = all_combinations(database, target_composition, excludes)

    start = time.time()
    matches = [calculate_match(target_composition, combo, database, penalty_factor) for combo in all_possible_combinations]
    elapsed = time.time() - start

    matches.sort(key=lambda x: -x[0])

    return matches[:top_n], elapsed
