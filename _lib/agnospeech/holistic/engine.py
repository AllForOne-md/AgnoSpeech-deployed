"""Holistic learned text minimization.

This is a non-L3 path: it does not call an LLM and it does not use a hate-word
lexicon. It learns which tokens support the supplied task label, learns which
tokens are author-risky when author labels exist, redacts direct identifiers,
and emits an evidence capsule that preserves model-relevant content while
dropping low-evidence / high-authorship material.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline

from agnospeech.holistic.placeholders import ReadablePlaceholderRenderer

_TOKEN = re.compile(r"\[[A-Z]+\]|[A-Za-z][A-Za-z0-9_'-]*|\d+(?:\.\d+)?|[^\w\s]")
_WORD = re.compile(r"[A-Za-z0-9_'-]+$")


@dataclass
class HolisticConfig:
    privacy_strength: float = 0.65
    utility_strength: float = 0.72
    context_window: int = 1
    max_preview_rows: int = 80


@dataclass
class HolisticResult:
    rows: list[dict[str, Any]]
    output_csv: str
    detected: dict[str, str | None]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "output_csv": self.output_csv,
            "detected": self.detected,
            "summary": self.summary,
        }


class _LinearProbe:
    def __init__(self, labels: list[str], feature_scores: dict[str, float], pipeline: Any):
        self.labels = labels
        self.feature_scores = feature_scores
        self.pipeline = pipeline

    @classmethod
    def fit(cls, texts: list[str], labels: list[str]) -> "_LinearProbe | None":
        if len(set(labels)) < 2 or len(texts) < 8:
            return None
        pipe = make_pipeline(
            TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                min_df=1,
                max_df=0.95,
                strip_accents="unicode",
            ),
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=0),
        )
        pipe.fit(texts, labels)
        vec: TfidfVectorizer = pipe.named_steps["tfidfvectorizer"]
        clf: LogisticRegression = pipe.named_steps["logisticregression"]
        names = vec.get_feature_names_out()
        coef = clf.coef_
        if coef.ndim == 1:
            weights = np.abs(coef)
        elif coef.shape[0] == 1:
            weights = np.abs(coef[0])
        else:
            weights = np.max(np.abs(coef), axis=0)
        scores = _normalize_scores({name: float(w) for name, w in zip(names, weights) if w > 0})
        return cls([str(c) for c in clf.classes_], scores, pipe)

    def proba(self, texts: list[str]) -> np.ndarray | None:
        if not hasattr(self.pipeline, "predict_proba"):
            return None
        return self.pipeline.predict_proba(texts)

    def predict(self, texts: list[str]) -> list[str]:
        return [str(x) for x in self.pipeline.predict(texts)]


def transform_rows(rows: list[dict[str, Any]], config: HolisticConfig | None = None) -> HolisticResult:
    config = config or HolisticConfig()
    cols = _columns(rows)
    detected = _detect_schema(rows, cols)
    text_col = detected["text"]
    if text_col is None:
        raise ValueError("Could not infer a text column from the uploaded file.")

    texts = [str(r.get(text_col, "") or "") for r in rows]
    labels = _col_values(rows, detected["label"])
    authors = _col_values(rows, detected["author"])
    ids = _col_values(rows, detected["id"])

    task_probe = _LinearProbe.fit(texts, labels) if labels else None
    author_probe = _LinearProbe.fit(texts, authors) if authors else None
    renderer = ReadablePlaceholderRenderer()

    edited: list[str] = []
    row_meta: list[dict[str, Any]] = []
    for i, text in enumerate(texts):
        new_text, meta = _edit_text(text, renderer, task_probe, author_probe, config)
        edited.append(new_text)
        row_meta.append(
            {
                "id": ids[i] if ids else str(i),
                "label": labels[i] if labels else None,
                "author": authors[i] if authors else None,
                "original": text,
                "edited": new_text,
                **meta,
            }
        )

    output_csv = _write_output_csv(rows, text_col, edited)
    summary = _summarize(texts, edited, labels, authors, task_probe, author_probe, config)
    preview = row_meta[: max(1, config.max_preview_rows)]
    return HolisticResult(rows=preview, output_csv=output_csv, detected=detected, summary=summary)


def _edit_text(
    text: str,
    renderer: ReadablePlaceholderRenderer,
    task_probe: _LinearProbe | None,
    author_probe: _LinearProbe | None,
    config: HolisticConfig,
) -> tuple[str, dict[str, Any]]:
    render_tokens = renderer.tokenize(text)
    toks = [tok.text for tok in render_tokens]
    if not toks:
        return text, {"compression": 1.0, "kept_terms": [], "risky_terms": [], "placeholders": []}

    evidence = [_token_score(t, task_probe.feature_scores if task_probe else {}) for t in toks]
    risk = [_token_score(t, author_probe.feature_scores if author_probe else {}) for t in toks]
    evidence_floor = _positive_quantile(evidence, 1.0 - config.utility_strength)
    risk_floor = _positive_quantile(risk, 1.0 - config.privacy_strength)

    keep = [False] * len(toks)
    word_indices = [i for i, tok in enumerate(toks) if _WORD.fullmatch(tok)]
    budget_fraction = min(
        0.85,
        max(0.08, 0.15 + 0.70 * config.utility_strength - 0.45 * config.privacy_strength),
    )
    budget = max(1, int(round(len(word_indices) * budget_fraction)))
    scored: list[tuple[float, int]] = []
    for i, tok in enumerate(toks):
        if not _WORD.fullmatch(tok):
            continue
        ev = evidence[i]
        rk = risk[i]
        if task_probe is None:
            score = 1.0 - rk
            if rk <= risk_floor:
                scored.append((score, i))
        else:
            score = ev - (config.privacy_strength * rk)
            if ev >= evidence_floor and (rk <= risk_floor or ev >= rk):
                scored.append((score, i))

    for _, i in sorted(scored, reverse=True)[:budget]:
        keep[i] = True

    # Add context around learned evidence so the output is an inspectable capsule,
    # not isolated keywords.
    expanded = keep[:]
    for i, flag in enumerate(keep):
        if flag:
            for j in range(max(0, i - config.context_window), min(len(toks), i + config.context_window + 1)):
                low_risk_context = author_probe is None or risk[j] <= risk_floor or evidence[j] >= risk[j]
                if _WORD.fullmatch(toks[j]) and low_risk_context:
                    expanded[j] = True
    keep = expanded

    rendered = renderer.render(render_tokens, keep)
    edited = rendered.text if rendered.text else _fallback_minimum(text)
    kept_terms = _top_terms(toks, evidence, keep)
    risky_terms = _top_terms(toks, risk, [r >= risk_floor for r in risk])
    return edited, {
        "compression": round(len(edited) / max(1, len(text)), 4),
        "kept_terms": kept_terms,
        "risky_terms": risky_terms,
        "placeholders": rendered.placeholders,
    }


def _summarize(
    originals: list[str],
    edited: list[str],
    labels: list[str] | None,
    authors: list[str] | None,
    task_probe: _LinearProbe | None,
    author_probe: _LinearProbe | None,
    config: HolisticConfig,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "n_rows": len(originals),
        "privacy_strength": config.privacy_strength,
        "utility_strength": config.utility_strength,
        "context_window": config.context_window,
        "mean_compression": round(fmean(len(e) / max(1, len(o)) for o, e in zip(originals, edited)), 4)
        if originals else 0.0,
        "method": "learned_evidence_risk_capsule",
        "claims": [
            "No L3 rewrite or LLM is used.",
            "No hardcoded hate lexicon or target list is used.",
            "Task evidence and author-risk terms are learned from the uploaded CSV when labels exist.",
            "Sensitive/community spans are rendered as readable typed placeholders.",
        ],
    }
    if task_probe and labels:
        raw_pred = task_probe.predict(originals)
        edit_pred = task_probe.predict(edited)
        summary["task_prediction_retention"] = round(
            float(np.mean([a == b for a, b in zip(raw_pred, edit_pred)])), 4
        )
        summary["edited_label_accuracy_in_sample"] = round(
            float(np.mean([a == b for a, b in zip(edit_pred, labels)])), 4
        )
    if author_probe and authors:
        raw_pred = author_probe.predict(originals)
        edit_pred = author_probe.predict(edited)
        summary["author_guess_raw_in_sample"] = round(
            float(np.mean([a == b for a, b in zip(raw_pred, authors)])), 4
        )
        summary["author_guess_edited_in_sample"] = round(
            float(np.mean([a == b for a, b in zip(edit_pred, authors)])), 4
        )
        summary["author_guess_drop"] = round(
            summary["author_guess_raw_in_sample"] - summary["author_guess_edited_in_sample"], 4
        )
    if labels and len(set(labels)) > 1 and len(labels) >= 20:
        try:
            tr, te = train_test_split(
                list(range(len(labels))),
                test_size=0.25,
                random_state=0,
                stratify=labels,
            )
            probe = _LinearProbe.fit([originals[i] for i in tr], [labels[i] for i in tr])
            if probe:
                pred = probe.predict([edited[i] for i in te])
                summary["edited_label_accuracy_holdout"] = round(
                    float(np.mean([p == labels[i] for p, i in zip(pred, te)])), 4
                )
        except ValueError:
            pass
    return summary


def _detect_schema(rows: list[dict[str, Any]], cols: list[str]) -> dict[str, str | None]:
    text_col = max(cols, key=lambda c: _text_score(rows, c), default=None)
    id_col = max(cols, key=lambda c: _id_score(rows, c), default=None)
    label_col = max(cols, key=lambda c: _label_score(rows, c), default=None)
    author_candidates = [c for c in cols if c not in {text_col, id_col, label_col}]
    author_col = max(author_candidates, key=lambda c: _author_score(rows, c), default=None)

    return {
        "id": id_col if id_col and _id_score(rows, id_col) > 0.8 else None,
        "text": text_col if text_col and _text_score(rows, text_col) > 0 else None,
        "label": label_col if label_col and _label_score(rows, label_col) > 0.4 else None,
        "author": author_col if author_col and _author_score(rows, author_col) > 0.35 else None,
    }


def _text_score(rows: list[dict[str, Any]], col: str) -> float:
    vals = [str(r.get(col, "") or "").strip() for r in rows]
    nonempty = [v for v in vals if v]
    if not nonempty:
        return 0.0
    avg_len = fmean(len(v) for v in nonempty)
    unique = len(set(nonempty)) / max(1, len(nonempty))
    spaces = fmean(v.count(" ") for v in nonempty)
    return avg_len * 0.02 + unique + spaces * 0.04


def _id_score(rows: list[dict[str, Any]], col: str) -> float:
    vals = [str(r.get(col, "") or "").strip() for r in rows]
    nonempty = [v for v in vals if v]
    if not nonempty:
        return 0.0
    unique = len(set(nonempty)) / max(1, len(nonempty))
    avg_len = fmean(len(v) for v in nonempty)
    return unique - max(0.0, avg_len - 48) * 0.01


def _label_score(rows: list[dict[str, Any]], col: str) -> float:
    vals = [str(r.get(col, "") or "").strip() for r in rows]
    nonempty = [v for v in vals if v]
    if len(nonempty) < 2:
        return 0.0
    distinct = len(set(nonempty))
    if distinct < 2 or distinct > min(12, max(2, len(nonempty) // 8)):
        return 0.0
    numeric = sum(_is_number(v) for v in nonempty) / len(nonempty)
    balance = distinct / max(1, len(nonempty))
    return 1.0 + numeric - balance


def _author_score(rows: list[dict[str, Any]], col: str) -> float:
    vals = [str(r.get(col, "") or "").strip() for r in rows]
    nonempty = [v for v in vals if v]
    if len(nonempty) < 8:
        return 0.0
    distinct = len(set(nonempty))
    repeat_ratio = 1.0 - distinct / len(nonempty)
    mean_per_author = len(nonempty) / max(1, distinct)
    if distinct < 2 or mean_per_author < 2:
        return 0.0
    return repeat_ratio + min(1.0, distinct / 20)


def _col_values(rows: list[dict[str, Any]], col: str | None) -> list[str] | None:
    if col is None:
        return None
    vals = [str(r.get(col, "") or "").strip() for r in rows]
    return vals if any(vals) else None


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in rows:
        for key in row:
            if key not in out:
                out.append(key)
    return out


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    mx = max(scores.values()) or 1.0
    return {k: v / mx for k, v in scores.items()}


def _token_score(tok: str, scores: dict[str, float]) -> float:
    low = tok.lower()
    return max(scores.get(low, 0.0), scores.get(_normalize_token(low), 0.0))


def _positive_quantile(values: list[float], q: float) -> float:
    positives = [v for v in values if v > 0]
    if not positives:
        return 0.0
    return float(np.quantile(positives, min(0.95, max(0.05, q))))


def _is_placeholder(tok: str) -> bool:
    return tok.startswith("[") and tok.endswith("]") and tok[1:-1].isupper()


def _normalize_token(tok: str) -> str:
    if _is_placeholder(tok):
        return tok
    return re.sub(r"(.)\1{2,}", r"\1\1", tok.lower())


def _join_tokens(toks: list[str]) -> str:
    text = " ".join(toks)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?:\.\.\.\s*){2,}", "... ", text)
    return text.strip()


def _fallback_minimum(text: str) -> str:
    toks = [_normalize_token(t) for t in _TOKEN.findall(text) if _is_placeholder(t) or _WORD.fullmatch(t)]
    return _join_tokens(toks[:24])


def _top_terms(toks: list[str], scores: list[float], mask: list[bool], limit: int = 8) -> list[str]:
    pairs = []
    for tok, score, flag in zip(toks, scores, mask):
        norm = _normalize_token(tok)
        if flag and score > 0 and _WORD.fullmatch(norm) and not _is_placeholder(norm):
            pairs.append((score, norm))
    out: list[str] = []
    seen = set()
    for _, term in sorted(pairs, reverse=True):
        if term not in seen:
            seen.add(term)
            out.append(term)
        if len(out) >= limit:
            break
    return out


def _write_output_csv(rows: list[dict[str, Any]], text_col: str, edited: list[str]) -> str:
    cols = _columns(rows)
    out_cols = cols + [c for c in ["edited_text"] if c not in cols]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=out_cols, lineterminator="\n")
    writer.writeheader()
    for row, new_text in zip(rows, edited):
        copy = dict(row)
        copy["edited_text"] = new_text
        writer.writerow(copy)
    return buf.getvalue()


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def dicts_from_csv(text: str) -> list[dict[str, Any]]:
    return [dict(r) for r in csv.DictReader(io.StringIO(text))]


def result_json(rows: list[dict[str, Any]], config: HolisticConfig | None = None) -> dict[str, Any]:
    return transform_rows(rows, config).to_dict()


def config_from_mapping(values: dict[str, Any]) -> HolisticConfig:
    def f(name: str, default: float) -> float:
        try:
            return float(values.get(name, default))
        except (TypeError, ValueError):
            return default

    def i(name: str, default: int) -> int:
        try:
            return int(values.get(name, default))
        except (TypeError, ValueError):
            return default

    return HolisticConfig(
        privacy_strength=min(0.95, max(0.05, f("privacy_strength", 0.65))),
        utility_strength=min(0.95, max(0.05, f("utility_strength", 0.72))),
        context_window=max(0, min(4, i("context_window", 1))),
        max_preview_rows=max(10, min(250, i("max_preview_rows", 80))),
    )


__all__ = [
    "HolisticConfig",
    "HolisticResult",
    "config_from_mapping",
    "dicts_from_csv",
    "result_json",
    "transform_rows",
]
