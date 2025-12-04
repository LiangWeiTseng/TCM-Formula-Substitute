import json
import os
import time
from itertools import chain, combinations

from scipy.optimize import minimize

DEFAULT_DATAFILE = os.path.normpath(os.path.join(__file__, '..', 'database.json'))


def load_formula_database(filepath):
    with open(filepath, 'r', encoding='utf-8') as file:
        database = json.load(file)
    return database


def all_combinations(database, exclude):
    keys = [key for key in database.keys() if key != exclude]
    return chain(*[combinations(keys, i) for i in range(1, min(len(keys), 2) + 1)])


def calculate_delta(x, target_composition, combination, database, penalty_factor):
    combined_composition = {}
    for i, formula in enumerate(combination):
        for herb, amount in database[formula].items():
            if herb in combined_composition:
                combined_composition[herb] += amount * x[i]
            else:
                combined_composition[herb] = amount * x[i]

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

    if result.success:
        dosages = result.x
        match_percentage = 100 - result.fun
        return match_percentage, combination, dosages
    else:
        return 0, combination, []


def find_best_matches(name, database, target_composition, penalty_factor, top_n=5):
    all_possible_combinations = all_combinations(database, name if name else '')

    start = time.time()
    matches = [calculate_match(target_composition, combo, database, penalty_factor) for combo in all_possible_combinations]
    elapsed = time.time() - start

    best_matches = sorted(matches, key=lambda x: -x[0])[:top_n]

    return best_matches, elapsed
