"""The evaluation harness: one pass that produces every TO number honestly.

Protocol:
- Per-author 70/30 split so all N authors appear in train and test (the attacker
  needs every candidate; the detector sees a mixed split).
- ONE shared HSD head trained on raw train text, applied unchanged to every
  privatized version of the test set (honest Uo vs Up).
- Authorship attacker in two strengths: static (trained on raw) and adaptive
  (trained on the privatized version it is tested on). Adaptive is the headline.
- The L3 operating intensity is chosen by the curve's non-degenerate selector,
  then used as the L3 level everywhere else, so the scorecard and the curve agree.
"""

from __future__ import annotations

import numpy as np

from .attacks import AuthorshipAttacker, pii_removed_fraction
from .datasets import Post, RedditCorpus
from .detect import HsdHead
from .metrics import (
    CurvePoint,
    Floors,
    build_curve,
    chance_corrected,
    dominance,
    macro_f1,
    majority_baseline_f1,
    mean_readability,
    mean_semantic_similarity,
    paired_bootstrap,
    privacy_ratio,
    to_score,
    utility_ratio,
)
from .privatize import L1Redact, L2Distill, L3Rewrite, RawPassthrough

L3_SWEEP = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.97]


def split_by_author(posts: list[Post], test_frac: float = 0.3, seed: int = 0):
    rng = np.random.default_rng(seed)
    by_author: dict[str, list[Post]] = {}
    for p in posts:
        by_author.setdefault(p.author, []).append(p)
    train, test = [], []
    for author in sorted(by_author):
        items = sorted(by_author[author], key=lambda p: p.id)
        idx = rng.permutation(len(items))
        n_test = max(1, int(round(len(items) * test_frac)))
        test_idx = set(idx[:n_test].tolist())
        for i, p in enumerate(items):
            (test if i in test_idx else train).append(p)
    return train, test


def _curve(train_raw, test_raw, train_authors, test_authors, test_labels, hsd,
           static_atk, f1_raw, f1_maj, p_orig, floors, seed) -> dict:
    points: list[CurvePoint] = []
    for intensity in L3_SWEEP:
        lv = L3Rewrite(intensity=intensity, seed=seed)
        tr = lv.apply_many(train_raw)
        te = lv.apply_many(test_raw)
        f1 = macro_f1(test_labels, hsd.predict(te))
        ur = utility_ratio(f1, f1_raw, f1_maj)
        # worst-case privacy: strongest of the static and adaptive attackers
        adaptive = AuthorshipAttacker(seed=seed).fit(tr, train_authors)
        p_acc = max(adaptive.accuracy(te, test_authors),
                    static_atk.accuracy(te, test_authors))
        pr = privacy_ratio(p_acc, p_orig)
        points.append(
            CurvePoint(
                intensity=intensity,
                utility_ratio=round(ur, 4),
                privacy_ratio=round(pr, 4),
                macro_f1=round(f1, 4),
                readability=round(mean_readability(te), 4),
                semantic_sim=round(mean_semantic_similarity(test_raw, te), 4),
                to=round(to_score(ur, pr), 4),
                feasible=True,
            )
        )
    return build_curve(points, floors)


def run_eval(csv_path: str, seed: int = 0, bootstrap_b: int = 2000,
             floors: Floors | None = None) -> dict:
    floors = floors or Floors()
    posts = RedditCorpus(csv_path).load()
    authors = RedditCorpus.authors(posts)
    n_candidates = len(authors)
    train, test = split_by_author(posts, seed=seed)
    train_authors = [p.author for p in train]
    test_authors = [p.author for p in test]
    test_labels = [p.label for p in test]
    train_labels = [p.label for p in train]
    train_raw = [p.text for p in train]
    test_raw = [p.text for p in test]

    # Shared HSD head, trained once on raw.
    hsd = HsdHead(seed=seed).fit(train_raw, train_labels)
    f1_raw = macro_f1(test_labels, hsd.predict(test_raw))
    f1_maj = majority_baseline_f1(test_labels)

    # Privacy_original: adaptive == static on raw.
    static_atk = AuthorshipAttacker(seed=seed).fit(train_raw, train_authors)
    p_orig = static_atk.accuracy(test_raw, test_authors)

    # Choose the L3 operating intensity from the non-degenerate curve selector.
    curve = _curve(train_raw, test_raw, train_authors, test_authors, test_labels,
                   hsd, static_atk, f1_raw, f1_maj, p_orig, floors, seed)
    op_intensity = curve["recommended"]["intensity"]

    levels = {
        "L0": RawPassthrough(),
        "L1": L1Redact(),
        "L2": L2Distill(),
        "L3": L3Rewrite(intensity=op_intensity, seed=seed),
    }

    per_level = {}
    hsd_pred = {}
    headline_correct = {}  # worst-case attacker's per-instance correctness
    for code, lv in levels.items():
        tr_txt = lv.apply_many(train_raw)
        te_txt = lv.apply_many(test_raw)
        pred = hsd.predict(te_txt)
        hsd_pred[code] = np.asarray(pred)
        f1 = macro_f1(test_labels, pred)
        ur = utility_ratio(f1, f1_raw, f1_maj)

        # Both attackers, always (the static/adaptive split is non-negotiable).
        acc_static = static_atk.accuracy(te_txt, test_authors)
        static_mask = static_atk.correct_mask(te_txt, test_authors)
        if code == "L0":
            adaptive = static_atk
        else:
            adaptive = AuthorshipAttacker(seed=seed).fit(tr_txt, train_authors)
        acc_adaptive = adaptive.accuracy(te_txt, test_authors)
        adaptive_mask = adaptive.correct_mask(te_txt, test_authors)

        # Honest headline = worst-case (strongest attacker). Optimistic = the
        # most favorable attacker an over-eager team would cherry-pick. The S1
        # toggle flips optimistic -> honest, which always lowers TO.
        if acc_static >= acc_adaptive:
            acc_honest, acc_opt, headline = acc_static, acc_adaptive, "static"
            headline_correct[code] = static_mask
        else:
            acc_honest, acc_opt, headline = acc_adaptive, acc_static, "adaptive"
            headline_correct[code] = adaptive_mask

        pr_opt = privacy_ratio(acc_opt, p_orig)
        pr_honest = privacy_ratio(acc_honest, p_orig)
        per_level[code] = {
            "level": code,
            "name": lv.name,
            "macro_f1": round(f1, 4),
            "utility_ratio": round(ur, 4),
            "attack_acc_static": round(acc_static, 4),
            "attack_acc_adaptive": round(acc_adaptive, 4),
            "attack_acc_optimistic": round(acc_opt, 4),
            "attack_acc_honest": round(acc_honest, 4),
            "headline_attacker": headline,
            "privacy_ratio_optimistic": round(pr_opt, 4),
            "privacy_ratio_honest": round(pr_honest, 4),
            "to_optimistic": round(to_score(ur, pr_opt), 4),
            "to_honest": round(to_score(ur, pr_honest), 4),
            "to_static": round(to_score(ur, privacy_ratio(acc_static, p_orig)), 4),
            "to_adaptive": round(to_score(ur, privacy_ratio(acc_adaptive, p_orig)), 4),
            "privacy_chance_corrected": round(chance_corrected(acc_honest, n_candidates), 4),
            "pii_removed_fraction": round(
                pii_removed_fraction(test_raw, te_txt), 4
            ),
        }

    # S16 paired-bootstrap dominance on the HONEST (worst-case) TO.
    boot = paired_bootstrap(
        np.asarray(test_labels), hsd_pred, headline_correct,
        levels=list(levels), b=bootstrap_b, seed=seed,
    )
    recommended = max(
        ["L1", "L2", "L3"], key=lambda c: per_level[c]["to_honest"]
    )
    dom = dominance(boot, recommended, [c for c in ["L1", "L2", "L3"] if c != recommended])
    boot_summary = {
        c: {k: round(v, 4) for k, v in boot[c].items() if k != "samples"}
        for c in levels
    }

    return {
        "corpus": {
            "path_basename": csv_path.replace("\\", "/").split("/")[-1],
            "n_posts": len(posts),
            "n_authors": n_candidates,
            "n_train": len(train),
            "n_test": len(test),
            "hate_rate": round(np.mean([p.label for p in posts]), 4),
            "attack_setting": "closed-world N-candidate attribution, an upper-bias "
            "(optimistic) estimate of real-world protection",
        },
        "baselines": {
            "f1_raw": round(f1_raw, 4),
            "f1_majority": round(f1_maj, 4),
            "privacy_original_acc": round(p_orig, 4),
            "chance_acc": round(1.0 / n_candidates, 4),
        },
        "levels": per_level,
        "curve": curve,
        "operating_point": {
            "level": "L3",
            "intensity": op_intensity,
            "selected_by": "Kneedle on the feasible frontier; refuses the "
            "degenerate (unreadable) high-TO zone",
        },
        "dominance": {
            "recommended_level": recommended,
            "bootstrap": boot_summary,
            **dom,
        },
        "_internal": {  # consumed by scorecard.py, stripped from the public JSON
            "hsd": hsd,
            "static_atk": static_atk,
            "op_intensity": op_intensity,
            "seed": seed,
        },
    }
