"""L2 Distill: rationale-only harm-span extraction.

Keep the harm-bearing spans, drop the surrounding stylistic tissue. The detector
still fires on the retained harm content (utility preserved), while a large part
of the authorship fingerprint (function words, idiosyncratic phrasing) is thrown
away (privacy improves over L1).

Invariant (hard-rule guard): L2 runs on already-L1-redacted text, so distillation
can never resurrect an identifier the harm span carried.

This is a deliberately NAIVE stance-blind extractor: it keeps harm tokens and
their target, and discards framing like "stop saying that" / "don't". That is
exactly the over-redaction failure mode the Harm Preservation Check exists to
catch (the counterspeech trap). The gold-rationale (HateXplain + ERASER) grounded
extractor is the event upgrade behind this same interface.
"""

from __future__ import annotations

import re

from .base import Privatizer
from .l1_redact import L1Redact

# Harm-salient cues: slurs/profanity and dehumanizing predicates that carry the
# hateful content. Kept modest and obviously heuristic; the event version is
# rationale-grounded, not lexicon-based.
HARM_LEXICON = {
    "retard", "retarded", "cunt", "cunts", "bitch", "bitches", "whore", "whores",
    "hoes", "ho", "slut", "sluts", "faggot", "fag", "tranny", "dyke", "nigger",
    "nigga", "spic", "kike", "chink", "parasite", "parasites", "vermin", "scum",
    "subhuman", "animals", "savages", "rats", "filth", "trash", "degenerate",
    "degenerates", "inferior", "disgusting", "kill", "die", "hang", "gas",
    "deport", "exterminate", "rape", "rapist", "misandrist", "stupid", "idiot",
    "moron", "morons", "dumb", "fuck", "fucking", "shit", "hate", "hateful",
}
# Group-target cues we keep so the harm stays interpretable (and so the
# counterspeech flip is reproducible for the Harm Check).
TARGET_CUES = {
    "women", "men", "muslims", "christians", "atheists", "jews", "blacks",
    "whites", "asians", "gays", "immigrants", "hungarians", "they", "them",
    "she", "he", "her", "his",
}
_TOKEN = re.compile(r"\[[A-Z]+\]|\w+|[^\w\s]")


def _salient(tok: str) -> bool:
    low = tok.lower()
    if tok.startswith("[") and tok.endswith("]"):
        return False  # placeholders are not harm content
    return low in HARM_LEXICON or low in TARGET_CUES


class L2Distill(Privatizer):
    level = "L2"
    name = "rationale_distill_heuristic"

    def __init__(self, window: int = 1):
        self.window = window
        self._l1 = L1Redact()

    def apply(self, text: str) -> str:
        text = self._l1.apply(text)  # invariant: L1 first
        toks = _TOKEN.findall(text)
        keep = [False] * len(toks)
        for i, t in enumerate(toks):
            if _salient(t):
                for j in range(max(0, i - self.window), min(len(toks), i + self.window + 1)):
                    keep[j] = True
        out: list[str] = []
        gap = False
        for i, t in enumerate(toks):
            if keep[i]:
                if gap and out:
                    out.append("…")
                out.append(t)
                gap = False
            else:
                gap = True
        if not any(keep):
            # No harm cue found: fall back to L1 output rather than emptying it.
            return text
        # Re-join with spaces, then tidy spacing around punctuation.
        s = " ".join(out)
        s = re.sub(r"\s+([.,!?;:])", r"\1", s)
        return s.strip()
