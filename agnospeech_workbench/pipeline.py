"""The privatization pipeline — backed entirely by the ``agnospeech`` library.

This module owns no privacy logic of its own. It calls the library's **holistic
editor** (the preferred, lexicon-free method) to minimize text, then the
library's authorship attacker, HSD detector head, and harm-preservation check to
turn the result into the workbench's risk scorecard. The legacy L0-L3 dial is
never used.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.model_selection import train_test_split

# The library is the backend. Nothing here reimplements it.
import re

from agnospeech import (
    AuthorshipAttacker,
    HolisticConfig,
    HsdHead,
    transform_rows,
    transform_texts,
)
from agnospeech.harmcheck.check import check as harm_check

_PLACEHOLDER = re.compile(r"\[[A-Z_]+\]")

SEED = 0

_TEXT_KEYS = ("text", "message", "body", "content", "report")
_AUTHOR_KEYS = ("author", "speaker", "user", "reporter", "name")
_LABEL_KEYS = ("hs", "label", "y", "harm", "target", "hate")


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    lower = {k.lower(): k for k in row}
    for k in keys:
        if k in lower:
            return lower[k]
    return None


def _normalize(rows: list[dict[str, Any]]) -> tuple[list[str], list[str] | None, list[int] | None]:
    """Pull text / author / label columns out of arbitrary rows."""
    if not rows:
        return [], None, None
    sample = rows[0]
    tkey = _pick(sample, _TEXT_KEYS) or max(
        sample, key=lambda k: len(str(sample.get(k, ""))), default=None
    )
    akey = _pick(sample, _AUTHOR_KEYS)
    lkey = _pick(sample, _LABEL_KEYS)
    texts = [str(r.get(tkey, "") or "") for r in rows]
    authors = [str(r.get(akey, "") or "") for r in rows] if akey else None
    labels = None
    if lkey:
        labels = []
        for r in rows:
            try:
                labels.append(int(float(r.get(lkey, 0) or 0)))
            except (TypeError, ValueError):
                labels.append(0)
    return texts, authors, labels


def _holistic(texts, authors, labels, *, privacy, utility, context) -> list[dict[str, Any]]:
    """Run the library holistic editor; return per-row meta in input order."""
    rows: list[dict[str, Any]] = []
    for i, t in enumerate(texts):
        row: dict[str, Any] = {"text": t}
        if authors is not None:
            row["author"] = authors[i]
        if labels is not None:
            row["label"] = labels[i]
        rows.append(row)
    config = HolisticConfig(
        privacy_strength=privacy,
        utility_strength=utility,
        context_window=context,
        max_preview_rows=max(1, len(rows)),
    )
    return transform_rows(rows, config).rows


def _split(n: int, authors):
    idx = list(range(n))
    strat = authors if authors and len(set(authors)) > 1 and _min_class(authors) >= 2 else None
    try:
        train, test = train_test_split(idx, test_size=0.35, random_state=SEED, stratify=strat)
    except ValueError:
        train, test = train_test_split(idx, test_size=0.35, random_state=SEED)
    return sorted(train), sorted(test)


def _min_class(values) -> int:
    counts: dict[Any, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return min(counts.values()) if counts else 0


def _attacker_accuracy(train_texts, train_y, test_texts, test_y) -> float | None:
    if not train_texts or not test_texts or len(set(train_y)) < 2:
        return None
    atk = AuthorshipAttacker(seed=SEED).fit(train_texts, train_y)
    return float(atk.accuracy(test_texts, test_y))


def _detector_f1(train_texts, train_y, test_texts) -> tuple[float, list[int]] | None:
    if len(set(train_y)) < 2:
        return None
    head = HsdHead(seed=SEED).fit(train_texts, train_y)
    return None, list(head.predict(test_texts))


def _scorecard(texts, edited, authors, labels) -> dict[str, Any]:
    n = len(texts)
    train, test = _split(n, authors)
    sub = lambda arr, ix: [arr[i] for i in ix] if arr is not None else None

    card: dict[str, Any] = {"random_baseline": None}

    # --- Privacy: worst-case authorship attribution (static + adaptive) -------
    if authors is not None and len(set(authors)) > 1:
        tr_auth, te_auth = sub(authors, train), sub(authors, test)
        before = _attacker_accuracy(sub(texts, train), tr_auth, sub(texts, test), te_auth)
        after_static = _attacker_accuracy(sub(texts, train), tr_auth, sub(edited, test), te_auth)
        after_adaptive = _attacker_accuracy(sub(edited, train), tr_auth, sub(edited, test), te_auth)
        afters = [a for a in (after_static, after_adaptive) if a is not None]
        card["attacker_before"] = before
        card["attacker_after"] = max(afters) if afters else None
        card["random_baseline"] = 1.0 / len(set(authors))

    # --- Utility: HSD detector macro-F1, raw vs holistic-edited ---------------
    if labels is not None and len(set(labels)) > 1:
        tr_lab, te_lab = sub(labels, train), sub(labels, test)
        if len(set(tr_lab)) > 1:
            head = HsdHead(seed=SEED).fit(sub(texts, train), tr_lab)
            f1_raw = HsdHead.macro_f1(te_lab, head.predict(sub(texts, test)))
            f1_edit = HsdHead.macro_f1(te_lab, head.predict(sub(edited, test)))
            card["utility_original"] = float(f1_raw)
            card["utility_protected"] = float(f1_edit)
            card["utility_retained"] = float(f1_edit / f1_raw) if f1_raw > 0 else None

    risk = card.get("attacker_after")
    util = card.get("utility_retained")
    card["residual_risk"] = risk
    card["utility"] = util
    card["threshold"] = 0.10
    card["defensible"] = (risk is not None and risk <= card["threshold"])
    return card


def _frontier(texts, authors, labels) -> list[dict[str, float]]:
    """Sweep the privacy knob to trace a risk-vs-utility frontier."""
    points: list[dict[str, float]] = []
    for p in (0.40, 0.55, 0.65, 0.80, 0.92):
        meta = _holistic(texts, authors, labels, privacy=p, utility=0.72, context=1)
        edited = [str(m["edited"]) for m in meta]
        card = _scorecard(texts, edited, authors, labels)
        if card.get("residual_risk") is not None and card.get("utility") is not None:
            points.append(
                {"privacy": p, "risk": round(card["residual_risk"], 4), "utility": round(card["utility"], 4)}
            )
    return points


def edit_text(
    text: str,
    *,
    privacy_strength: float = 0.65,
    utility_strength: float = 0.72,
    context_window: int = 1,
) -> dict[str, Any]:
    """Privatize free-form pasted text — the DeepL-style live editor backend.

    Each non-blank line is run through the library holistic editor; blank lines
    and overall structure are preserved so the output reads as an edited copy.
    No labels/authors, so it falls back to deterministic PII redaction + low-
    evidence trimming via the readable placeholder renderer.
    """
    lines = text.split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.strip()]
    edits = (
        transform_texts(
            [lines[i] for i in idx],
            privacy_strength=privacy_strength,
            utility_strength=utility_strength,
            context_window=context_window,
        )
        if idx
        else []
    )
    out = list(lines)
    for k, i in enumerate(idx):
        out[i] = edits[k]
    edited = "\n".join(out)
    return {
        "edited": edited,
        "identifiers": len(_PLACEHOLDER.findall(edited)),
        "chars_in": len(text),
        "chars_out": len(edited),
        "lines": len(idx),
    }


def transform_dataset(
    rows: list[dict[str, Any]],
    *,
    privacy_strength: float = 0.65,
    utility_strength: float = 0.72,
    context_window: int = 1,
) -> dict[str, Any]:
    """Privatize an uploaded CSV/JSON dataset — holistic edit only, no scorecard.

    Lighter and faster than :func:`run_pipeline` (no authorship attacker, detector
    or frontier sweep), so it runs comfortably inside a short serverless budget.
    Returns per-row raw + edited text plus what was removed.
    """
    texts, authors, labels = _normalize(rows)
    if not texts:
        raise ValueError("No text column found in the uploaded file.")
    ikey = _pick(rows[0], ("id", "code", "row")) if rows else None
    meta = _holistic(
        texts, authors, labels,
        privacy=privacy_strength, utility=utility_strength, context=context_window,
    )
    edited = [str(m["edited"]) for m in meta]
    messages: list[dict[str, Any]] = []
    identifiers_removed = 0
    for i, m in enumerate(meta):
        ph = m.get("placeholders") or []
        identifiers_removed += len(ph)
        messages.append({
            "code": (str(rows[i].get(ikey)) if ikey else f"ROW-{i}"),
            "author": (authors[i] if authors else None),
            "hs": (labels[i] if labels else None),
            "raw": texts[i],
            "edited": edited[i],
            "placeholders": [str(x) for x in ph],
            "kept_terms": list(m.get("kept_terms") or [])[:6],
        })
    return {
        "messages": messages,
        "counts": {
            "messages": len(texts),
            "identifiers_removed": identifiers_removed,
            "authors": (len(set(authors)) if authors else 0),
            "has_labels": labels is not None,
        },
        "method": "holistic",
    }


def run_pipeline(
    rows: list[dict[str, Any]],
    *,
    privacy_strength: float = 0.65,
    utility_strength: float = 0.72,
    context_window: int = 1,
) -> dict[str, Any]:
    """Full workbench computation on a corpus. Every number comes from the library."""
    texts, authors, labels = _normalize(rows)
    if not texts:
        raise ValueError("No text rows found in the corpus.")

    meta = _holistic(
        texts, authors, labels,
        privacy=privacy_strength, utility=utility_strength, context=context_window,
    )
    edited = [str(m["edited"]) for m in meta]

    messages = []
    identifiers_removed = 0
    for i, m in enumerate(meta):
        ph = m.get("placeholders") or []
        identifiers_removed += len(ph)
        messages.append({
            "code": f"MSG-{1000 + i}",
            "author": (authors[i] if authors else None),
            "hs": (labels[i] if labels else None),
            "raw": texts[i],
            "edited": edited[i],
            "placeholders": [str(x) for x in ph],
            "kept_terms": list(m.get("kept_terms") or [])[:8],
            "risky_terms": list(m.get("risky_terms") or [])[:8],
            "compression": m.get("compression"),
        })

    card = _scorecard(texts, edited, authors, labels)
    frontier = _frontier(texts, authors, labels)

    # --- Harm Preservation Check (library) ------------------------------------
    harm = []
    passed = 0
    for i in range(len(texts)):
        v = harm_check(texts[i], edited[i], "holistic").to_dict()
        v["code"] = messages[i]["code"]
        if v.get("preserved"):
            passed += 1
        else:
            harm.append(v)

    return {
        "params": {
            "privacy_strength": privacy_strength,
            "utility_strength": utility_strength,
            "context_window": context_window,
        },
        "counts": {
            "messages": len(texts),
            "identifiers_removed": identifiers_removed,
            "authors": (len(set(authors)) if authors else 0),
        },
        "messages": messages,
        "scorecard": card,
        "frontier": frontier,
        "harmcheck": {"passed": passed, "flagged": harm},
        "method": "holistic",
    }
