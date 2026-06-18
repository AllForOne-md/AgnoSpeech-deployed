"""High-level public API for AgnoSpeech.

Thin, stable wrappers over the internal subpackages so library users have one
front door and never import internal module paths.

PRIMARY — the holistic editor (lexicon-free, LLM-free, CPU-only):

    import agnospeech as ag

    ag.transform_texts(["..."], labels=[...])  # plain strings in/out
    ag.transform_csv(rows)                      # rows -> HolisticResult
    ag.transform_csv_text(csv_string)           # CSV in/out (web/API)
    ag.evaluate("corpus.csv")                   # attack-measured trade-off scorecard

LEGACY — the tiered L0–L3 privatization dial (kept for reproducibility of the
original study; prefer the holistic functions above for new work):

    ag.privatize("text", level="L2")            # per-string tiered transform

Everything here is pure-Python / CPU and uses only the core dependencies. The
heavy event drop-ins (transformers, presidio, gliner) stay optional extras.
"""

from __future__ import annotations

from typing import Any, Literal

from .harness import run_eval
from .holistic import HolisticConfig, HolisticResult, transform_rows
from .holistic.engine import dicts_from_csv
from .privatize import L1Redact, L2Distill, L3Rewrite, Privatizer, RawPassthrough

Level = Literal["L0", "L1", "L2", "L3"]

__all__ = [
    # primary: holistic editor
    "transform_texts",
    "transform_csv",
    "transform_csv_text",
    "evaluate",
    # legacy: tiered L0–L3 dial
    "Level",
    "privatize",
    "privatize_many",
]


def _levels(*, intensity: float, seed: int, l2_window: int) -> dict[str, Privatizer]:
    """The L0->L3 dial. Built inline so the L2 context window is tunable per call."""
    return {
        "L0": RawPassthrough(),
        "L1": L1Redact(),
        "L2": L2Distill(window=l2_window),
        "L3": L3Rewrite(intensity=intensity, seed=seed),
    }


def privatize(
    text: str,
    level: Level = "L2",
    *,
    intensity: float = 0.6,
    l2_window: int = 1,
    seed: int = 0,
) -> str:
    """Privatize one string at a tier. **Legacy** — prefer
    :func:`transform_texts` (the holistic editor) for new work.

    L0 raw passthrough, L1 redact identifiers (no knob), L2 distill harm
    rationale (``l2_window`` = context tokens kept), L3 DP-grounded rewrite
    (``intensity`` = readability/privacy knob).
    """
    levels = _levels(intensity=intensity, seed=seed, l2_window=l2_window)
    if level not in levels:
        raise ValueError(f"level must be one of {sorted(levels)}, got {level!r}")
    return levels[level].apply(text)


def privatize_many(
    texts: list[str],
    level: Level = "L2",
    *,
    intensity: float = 0.6,
    l2_window: int = 1,
    seed: int = 0,
) -> list[str]:
    """Privatize a list of strings at a tier (see :func:`privatize`). **Legacy** —
    prefer :func:`transform_texts` for new work."""
    levels = _levels(intensity=intensity, seed=seed, l2_window=l2_window)
    if level not in levels:
        raise ValueError(f"level must be one of {sorted(levels)}, got {level!r}")
    return levels[level].apply_many(texts)


def transform_csv(
    rows: list[dict[str, Any]],
    *,
    privacy_strength: float = 0.65,
    utility_strength: float = 0.72,
    context_window: int = 1,
) -> HolisticResult:
    """Holistic, lexicon-free CSV editor: infer schema, learn task-evidence and
    author-risk probes from the rows, redact identifiers, emit evidence capsules.
    Returns a :class:`HolisticResult` (preview rows, ``output_csv``, detected
    columns, summary)."""
    config = HolisticConfig(
        privacy_strength=privacy_strength,
        utility_strength=utility_strength,
        context_window=context_window,
    )
    return transform_rows(rows, config)


def transform_csv_text(csv_text: str, **kwargs: Any) -> str:
    """Same as :func:`transform_csv` but takes and returns a CSV *string*.
    Convenience for web/API callers; the returned CSV adds an ``edited_text``
    column."""
    return transform_csv(dicts_from_csv(csv_text), **kwargs).output_csv


def transform_texts(
    texts: list[str],
    *,
    labels: list[Any] | None = None,
    authors: list[Any] | None = None,
    privacy_strength: float = 0.65,
    utility_strength: float = 0.72,
    context_window: int = 1,
) -> list[str]:
    """Holistic-edit a list of plain strings — no CSV, no L0–L3 dial.

    This is the lexicon-free, LLM-free holistic path on its own. It is
    *corpus-level*: it learns which tokens carry the task signal (from
    ``labels``) and which are author-identifying (from ``authors``), so passing
    those lists sharpens the edit. With neither, it falls back to deterministic
    PII redaction + low-evidence trimming via the readable placeholder renderer.

    Returns one edited string per input, order preserved. Use this when you want
    the holistic editor to be the single text-minimization path for arbitrary
    text instead of the per-string :func:`privatize` tiers.
    """
    rows: list[dict[str, Any]] = []
    for i, text in enumerate(texts):
        row: dict[str, Any] = {"text": text}
        if labels is not None:
            row["label"] = labels[i]
        if authors is not None:
            row["author"] = authors[i]
        rows.append(row)
    config = HolisticConfig(
        privacy_strength=privacy_strength,
        utility_strength=utility_strength,
        context_window=context_window,
        max_preview_rows=max(1, len(rows)),  # never truncate: return every edit
    )
    result = transform_rows(rows, config)
    return [str(r["edited"]) for r in result.rows]


def evaluate(csv_path: str, *, seed: int = 0, bootstrap: int = 2000) -> dict[str, Any]:
    """Run the attack-measured evaluation harness on a ``ID,author,text,hs`` CSV
    and return the scorecard dict (baselines, per-level macro-F1, static/adaptive
    attacker accuracy, optimistic/honest trade-off, curve, bootstrap dominance).
    Pure: no files written."""
    return run_eval(str(csv_path), seed=seed, bootstrap_b=bootstrap)
