from __future__ import annotations

import math


def clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def weighted_score(scores: dict[str, float | None], weights: dict[str, float]) -> float:
    total_weight = 0.0
    total_score = 0.0
    for dimension, weight in weights.items():
        score = scores.get(dimension)
        if score is None:
            continue
        total_weight += weight
        total_score += clip01(score) * weight
    if total_weight == 0:
        return 0.0
    return clip01(total_score / total_weight)


def calibration_score(confidence: float | None, success_value: float) -> float:
    if confidence is None:
        return 0.0
    confidence = clip01(confidence)
    success_value = clip01(success_value)
    return clip01(1.0 - (confidence - success_value) ** 2)


def ratio_with_budget(actual: int | float, budget: int | float | None) -> float | None:
    if budget is None or budget <= 0:
        return None
    return clip01(1.0 - max(0.0, (float(actual) - float(budget)) / float(budget)))


def consistency_score(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    deviation = math.sqrt(variance)
    return clip01(1.0 - (deviation / 0.5))
