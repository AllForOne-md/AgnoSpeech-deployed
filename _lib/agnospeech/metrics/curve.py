"""Utility-vs-Privacy curve with floors and a non-degenerate operating-point
selector (S1 / S17).

Sweeping the L3 intensity traces a curve. Because L3 anchors the harm rationale,
high intensity keeps the detector alive (utility stays moderate) while erasing
the authorship signal (privacy ratio -> low), so TO climbs toward the high end.
That high-TO end is the DEGENERATE optimum: the text is unreadable. The floors
(HSD-F1, readability, semantic similarity) mark that zone infeasible, and the
operating-point selector refuses it and returns the knee of the FEASIBLE region.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass
class CurvePoint:
    intensity: float
    utility_ratio: float
    privacy_ratio: float
    macro_f1: float
    readability: float
    semantic_sim: float
    to: float
    feasible: bool


@dataclass
class Floors:
    # Calibrated against the CPU-spine proxies: the feasible band keeps text
    # mostly real words and semantically close to the original; the degenerate
    # tail (unreadable "·"-heavy noise that still posts a high TO) falls below.
    macro_f1: float = 0.55
    readability: float = 0.45
    semantic_sim: float = 0.40


def _kneedle(x: np.ndarray, y: np.ndarray) -> int:
    """Index of the knee: the point of maximum drop below the straight chord,
    after normalizing both axes to [0, 1]. x must be sorted ascending."""
    if len(x) < 3:
        return 0
    xn = (x - x.min()) / (np.ptp(x) + 1e-12)
    yn = (y - y.min()) / (np.ptp(y) + 1e-12)
    chord = xn  # straight line from (0,0) to (1,1) under this normalization
    diff = yn - chord
    return int(np.argmax(np.abs(diff)))


def build_curve(points: list[CurvePoint], floors: Floors) -> dict:
    for p in points:
        p.feasible = (
            p.macro_f1 >= floors.macro_f1
            and p.readability >= floors.readability
            and p.semantic_sim >= floors.semantic_sim
        )
    feasible = [p for p in points if p.feasible]
    global_max = max(points, key=lambda p: p.to)

    if feasible:
        # Knee on the feasible frontier (privacy_ratio ascending vs utility_ratio).
        fs = sorted(feasible, key=lambda p: p.privacy_ratio)
        xi = np.array([p.privacy_ratio for p in fs])
        yi = np.array([p.utility_ratio for p in fs])
        knee = fs[_kneedle(xi, yi)]
        # Recommend the feasible point with the best TO; the knee is the
        # principled cross-check that it is not bought with unreadable text.
        recommended = max(feasible, key=lambda p: p.to)
    else:
        knee = recommended = global_max

    # Degenerate zone: the infeasible high-intensity band. Report its lower edge.
    infeasible = [p for p in points if not p.feasible]
    degenerate_from = min((p.intensity for p in infeasible), default=None)

    return {
        "floors": asdict(floors),
        "points": [asdict(p) for p in points],
        "global_max_to": asdict(global_max),
        "recommended": asdict(recommended),
        "knee": asdict(knee),
        "degenerate_zone_from_intensity": degenerate_from,
        "degenerate_optimum_is_refused": (not global_max.feasible),
    }
