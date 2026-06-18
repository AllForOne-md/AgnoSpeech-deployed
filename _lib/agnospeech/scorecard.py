"""Assemble the per-post + aggregate scorecard JSON the demo reads.

The live demo runs ZERO inference: it renders this committed JSON. Everything
here is computed offline by ``run_eval`` plus the fixture pass below.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import harmcheck
from .harness import run_eval
from .privatize import default_levels
from .repro import GLOBAL_SEED, TO_TOLERANCE, runtime_revisions

LEVEL_ORDER = ["L0", "L1", "L2", "L3"]

HONESTY_REGISTER = [
    "L3 is DP-grounded (pending the logit spike), never differentially private.",
    "The self-attack stop is a calibrated stopping rule, never a certificate.",
    "Privacy is closed-world attribution, an upper-bias (optimistic) estimate.",
    "The adaptive attacker is the headline; the static number is shown as inflated.",
    "Reproducibility is tolerance-bounded, never bit-exact.",
    "The skill-corrected privacy term is a companion column, never the scored TO.",
]

HARD_RULES = [
    "Score only text, never people or accounts.",
    "Never deanonymise authors; nothing here is a re-identification tool.",
    "Raw text never leaves the laptop; no cloud call on the demo path.",
    "All on-screen identities are synthetic or pseudonymous.",
    "Any adversary-succeeds beat is fabricated and shown failing on protected output.",
]


def _fixture_journey(fixture: dict, hsd, static_atk, op_intensity: int, seed: int) -> dict:
    orig = fixture["text"]
    levels = default_levels(l3_intensity=op_intensity, seed=seed)
    journey = []
    for code, lv in levels.items():
        ptext = lv.apply(orig)
        verdict = harmcheck.check(orig, ptext, code)
        journey.append(
            {
                "level": code,
                "name": lv.name,
                "text": ptext,
                # detector's confidence the post is hateful (should stay stable)
                "hsd_hate_proba": round(float(hsd.proba([ptext])[0]), 4),
                # attacker's confidence in its best author guess (should collapse)
                "fingerprint_strength": round(
                    float(static_atk.fingerprint_strength([ptext])[0]), 4
                ),
                "harm": verdict.to_dict(),
            }
        )
    # Tighten-only routing: escalate while each level preserves the harm, and
    # stop at the first level that flips or over-redacts. We never serve a level
    # past a broken one, so a counterspeech flip at L2 routes back to L1, not on
    # to a more aggressive L3.
    resolved = "L0"
    for code in LEVEL_ORDER:
        if next(j for j in journey if j["level"] == code)["harm"]["preserved"]:
            resolved = code
        else:
            break
    served = LEVEL_ORDER[: LEVEL_ORDER.index(resolved) + 1]
    flipped = [j["level"] for j in journey if not j["harm"]["preserved"]]
    not_served = [c for c in LEVEL_ORDER if c not in served]
    return {
        "id": fixture["id"],
        "kind": fixture["kind"],
        "synthetic_author": fixture["synthetic_author"],
        "note": fixture.get("note", ""),
        "original_text": orig,
        "journey": journey,
        "resolved_level": resolved,
        "rejected_levels": flipped,
        "not_served_levels": not_served,
    }


def build_scorecard(csv_path: str, fixtures_path: str, seed: int = GLOBAL_SEED,
                    bootstrap_b: int = 2000) -> dict:
    res = run_eval(csv_path, seed=seed, bootstrap_b=bootstrap_b)
    internal = res.pop("_internal")
    hsd, static_atk = internal["hsd"], internal["static_atk"]
    op_intensity = internal["op_intensity"]

    fixtures = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))
    posts = {
        key: _fixture_journey(fx, hsd, static_atk, op_intensity, seed)
        for key, fx in fixtures.items()
    }

    rec = res["dominance"]["recommended_level"]
    lv = res["levels"]
    leaderboard = [
        {"name": "No-op baseline (L0)", "to": 0.0, "note": "publish raw text", "kind": "baseline"},
        {
            "name": "Optimistic headline (cherry-picked attacker)",
            "to": lv[rec]["to_optimistic"],
            "note": "what a team reports if it keeps its most favorable attacker",
            "kind": "inflated",
        },
        {
            "name": "Degenerate maximum (refused)",
            "to": res["curve"]["global_max_to"]["to"],
            "note": "highest TO on the curve; unreadable, fails the floors",
            "kind": "refused",
        },
        {
            "name": "AgnoSpeech (honest worst-case, recommended)",
            "to": lv[rec]["to_honest"],
            "note": "worst-case over static + adaptive attackers, non-degenerate point",
            "kind": "ours",
        },
    ]

    return {
        "schema_version": "1.0",
        "title": "AgnoSpeech privacy scorecard",
        "generated": {
            "seed": seed,
            "to_tolerance": TO_TOLERANCE,
            "revisions": runtime_revisions(),
            "zero_inference_at_demo_time": True,
        },
        "corpus": res["corpus"],
        "baselines": res["baselines"],
        "levels": res["levels"],
        "level_order": LEVEL_ORDER,
        "curve": res["curve"],
        "operating_point": res["operating_point"],
        "dominance": res["dominance"],
        "leaderboard": leaderboard,
        "demo_posts": posts,
        "demo_pointers": {
            "main_journey": "doxing",
            "wow1_counterspeech_trap": "counterspeech",
            "wow2_honesty_toggle": "operating_point + curve + levels[*].to_static vs to_adaptive",
        },
        "honesty_register": HONESTY_REGISTER,
        "hard_rules": HARD_RULES,
    }


def write_scorecard(csv_path: str, fixtures_path: str, out_path: str,
                    seed: int = GLOBAL_SEED, bootstrap_b: int = 2000) -> dict:
    card = build_scorecard(csv_path, fixtures_path, seed=seed, bootstrap_b=bootstrap_b)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return card
