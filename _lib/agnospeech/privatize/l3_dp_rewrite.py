"""L3 Rewrite: rationale-anchored local style rewrite.

Goal: destroy the authorship fingerprint (capitalization quirks, character
elongation, punctuation habits, lexical choices, function-word patterns) while
anchoring the harm rationale so the detector still fires. An ``intensity`` knob
(epsilon proxy) trades readability for privacy; sweeping it draws the
Utility-vs-Privacy curve, and high intensity walks into the degenerate zone the
operating-point selector must refuse.

HONESTY: this is a clearly-labeled NON-DP local rewrite. It is the sanctioned
demo fallback (event build plan, Day 2) for the real contribution, DP-Prompt
logit-clipping (epsilon = 2*Delta/T) over FLAN-T5-base raw HF logits, whose
single open risk is per-token logit access on CPU. That spike is the #1 event
action. This stand-in is NOT differentially private; ``intensity`` is not a
privacy budget. Output is "DP-grounded (pending the logit spike)", never "DP".
"""

from __future__ import annotations

import hashlib
import random
import re

from .base import Privatizer
from .l1_redact import L1Redact
from .l2_rationale import HARM_LEXICON, TARGET_CUES

# Small meaning-preserving substitution map: swaps the author's lexical choices
# for canonical ones, erasing a stylistic tell without changing the content.
SYNONYMS = {
    "kids": "children", "guy": "man", "guys": "people", "folks": "people",
    "dude": "person", "gonna": "going to", "wanna": "want to", "gotta": "got to",
    "kinda": "kind of", "cause": "because", "cuz": "because", "tho": "though",
    "lol": "", "lmao": "", "haha": "", "omg": "", "yeah": "yes", "yep": "yes",
    "nope": "no", "ur": "your", "u": "you", "thru": "through", "outta": "out of",
    "big": "large", "huge": "large", "tiny": "small", "smart": "intelligent",
    "crazy": "irrational", "insane": "extreme", "awesome": "good", "great": "good",
    "bad": "poor", "terrible": "poor", "lot": "many", "lots": "many",
    "really": "very", "totally": "entirely", "stuff": "things", "thing": "matter",
}
_FUNCTION = {
    "the", "a", "an", "and", "or", "but", "so", "if", "then", "of", "to", "in",
    "on", "at", "for", "with", "as", "by", "is", "are", "was", "were", "be",
    "been", "this", "that", "these", "those", "it", "its", "my", "your", "i",
    "me", "we", "our", "you", "do", "does", "did", "just", "very", "well",
}
_TOKEN = re.compile(r"\[[A-Z]+\]|[A-Za-z]+'?[A-Za-z]*|\d+|[^\w\s]")


class L3Rewrite(Privatizer):
    level = "L3"
    name = "rationale_anchored_rewrite_nondp"

    def __init__(self, intensity: float = 0.6, seed: int = 0):
        self.intensity = float(intensity)
        self.seed = seed
        self._l1 = L1Redact()

    def apply(self, text: str) -> str:
        text = self._l1.apply(text)            # never resurrect PII
        toks = _TOKEN.findall(text)            # tokenize BEFORE casing changes,
        # so L1's uppercase [TYPE] placeholders survive as single tokens.
        # deterministic per-text RNG (stable hash, not builtin hash() which is
        # per-process salted) -> reproducible output across separate runs.
        digest = hashlib.md5(text.encode("utf-8")).digest()
        rng = random.Random((self.seed * 1_000_003) ^ int.from_bytes(digest[:4], "big"))
        out: list[str] = []
        for t in toks:
            # Preserve L1 placeholders verbatim; never blur or split them.
            if t.startswith("[") and t.endswith("]") and t[1:-1].isupper():
                out.append(t)
                continue
            # Per-token style normalization: lowercase + collapse char elongation
            # (cooool -> cool). This strips casing/elongation tells without
            # touching the placeholders.
            low = re.sub(r"(.)\1{2,}", r"\1\1", t.lower())
            if low in HARM_LEXICON or low in TARGET_CUES:
                out.append(low)                # anchor the harm rationale
                continue
            if low in SYNONYMS:                # canonicalize lexical choice
                rep = SYNONYMS[low]
                if rep:
                    out.append(rep)
                continue
            if rng.random() < self.intensity:
                # perturb a stylistic/topic token: drop function words, blur
                # content words to a neutral token. Higher intensity -> more
                # perturbation -> less readable -> walks toward the degenerate zone.
                if low in _FUNCTION:
                    continue
                if low.isalpha():
                    out.append("·")            # neutral content placeholder
                continue
            out.append(low)
        s = " ".join(out)
        s = re.sub(r"\s+([.,!?;:])", r"\1", s)        # tidy spacing before punct
        s = re.sub(r"([!?.,])\1{1,}", r"\1", s)       # !!! -> !
        s = re.sub(r"\s+", " ", s)
        return s.strip()
