"""Metrics never equate a provider's confidence with a calibrated probability."""

from __future__ import annotations

import math
import platform
import statistics


def percentiles(values):
    if not values:
        return {"count": 0, "p50": None, "p95": None, "p99": None, "mean": None}
    data = sorted(values)

    def p(q):
        pos = (len(data) - 1) * q
        lo = int(pos)
        return round(data[lo] + (data[min(lo + 1, len(data) - 1)] - data[lo]) * (pos - lo), 3)

    return {
        "count": len(data),
        "p50": p(0.5),
        "p95": p(0.95),
        "p99": p(0.99),
        "mean": round(statistics.mean(data), 3),
    }


def evaluate(rows, threshold=0.5):
    count = correct = 0
    confusion = {}
    squared, calibration, ordinal_errors = [], [], []
    for row in rows:
        for key, answer in row.get("answers", {}).items():
            if key not in row.get("expected", {}):
                continue
            expected = row["expected"][key]
            accepted = expected if isinstance(expected, list) else [expected]
            value = answer["value"]
            predicted = (
                int(value >= threshold)
                if answer["type"] == "boolean_probability"
                else round(value)
                if answer["type"] == "ordinal"
                else value
            )
            good = predicted in accepted
            count += 1
            correct += good
            # Ambiguous labels contribute to set accuracy, not single-label calibration/confusion.
            if len(accepted) != 1:
                continue
            target = accepted[0]
            matrix = confusion.setdefault(key, {})
            matrix.setdefault(str(target), {})[str(predicted)] = (
                matrix.setdefault(str(target), {}).get(str(predicted), 0) + 1
            )
            if answer["type"] == "ordinal":
                ordinal_errors.append(abs(value - target))
            if answer["type"] == "boolean_probability":
                squared.append((value - target) ** 2)
                calibration.append((value if predicted else 1 - value, int(good)))
            elif answer.get("probabilities"):
                ps = answer["probabilities"]
                if str(target) in ps:
                    squared.append(sum((v - int(k == str(target))) ** 2 for k, v in ps.items()))
                    calibration.append((max(ps.values()), int(max(ps, key=ps.get) == str(target))))
    bins = []
    for i in range(10):
        entries = [(p, c) for p, c in calibration if min(9, int(p * 10)) == i]
        bins.append(
            {
                "lower": i / 10,
                "count": len(entries),
                "probability": statistics.mean(p for p, _ in entries) if entries else None,
                "accuracy": statistics.mean(c for _, c in entries) if entries else None,
            }
        )
    f1s = []
    for matrix in confusion.values():
        labels = set(matrix) | {label for predictions in matrix.values() for label in predictions}
        for label in labels:
            tp = matrix.get(label, {}).get(label, 0)
            fp = sum(v.get(label, 0) for k, v in matrix.items() if k != label)
            fn = sum(n for k, n in matrix.get(label, {}).items() if k != label)
            f1s.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
    return {
        "count": count,
        "accuracy": correct / count if count else None,
        "macro_f1": statistics.mean(f1s) if f1s else None,
        "confusion": confusion,
        "brier": statistics.mean(squared) if squared else None,
        "brier_note": "Mean across questions; compare only identical question sets.",
        "mae": statistics.mean(ordinal_errors) if ordinal_errors else None,
        "ece": sum(b["count"] * abs(b["probability"] - b["accuracy"]) for b in bins if b["count"])
        / len(calibration)
        if calibration
        else None,
        "calibration": bins,
    }


def temperature_scale(probabilities, temperature):
    if not 0.05 <= temperature <= 10:
        raise ValueError("Temperature must be between .05 and 10")
    logs = [math.log(max(p, 1e-12)) / temperature for p in probabilities.values()]
    mx = max(logs)
    weights = [math.exp(v - mx) for v in logs]
    total = sum(weights)
    return {key: value / total for key, value in zip(probabilities, weights)}


def hardware():
    import importlib.metadata
    import os

    versions = {}
    for package in ["laya", "torch", "transformers", "fastapi"]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count(),
        "versions": versions,
    }
