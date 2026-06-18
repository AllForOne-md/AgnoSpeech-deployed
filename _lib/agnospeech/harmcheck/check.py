"""Harm Preservation Check (the second wow moment).

QAGS-style consistency: privatization must preserve the harm judgment of the
original, neither erasing it (over-redaction) nor flipping its stance (meaning
distortion). The signature catch is the counterspeech trap: a condemnation like
"Stop saying that [group] are parasites" must NOT be distilled into the bare
assertion "[group] are parasites".

CPU-only spine: a stance + harm-presence consistency check. The question
templates are drafted offline (cloud allowed, never on raw text at runtime); the
event upgrade swaps in a local QA model behind the same ``check`` signature.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..privatize.l2_rationale import HARM_LEXICON, TARGET_CUES

# Condemnation / counterspeech framing cues. Kept distinct from the harm lexicon
# so "hate" as a harm term does not get mistaken for a condemnation.
_CONDEMN = [
    "stop saying", "stop calling", "stop", "don't say", "do not say", "dont say",
    "shouldn't", "should not", "no one should", "nobody should", "quit",
    "it's wrong", "its wrong", "it is wrong", "wrong to", "condemn", "stop it",
    "you shouldn't", "we shouldn't", "refuse to", "don't call", "do not call",
]
_HARM_RE = re.compile(
    r"\b(" + "|".join(sorted(HARM_LEXICON, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_TARGET_RE = re.compile(
    r"\b(" + "|".join(sorted(TARGET_CUES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _has_harm(text: str) -> bool:
    return bool(_HARM_RE.search(text))


def _stance(text: str) -> str:
    """'condemns' | 'asserts' | 'none'. A condemnation cue anywhere ahead of the
    harm flips an assertion into counterspeech."""
    low = text.lower()
    harm = _has_harm(text)
    condemns = any(cue in low for cue in _CONDEMN)
    if harm and condemns:
        return "condemns"
    if harm:
        return "asserts"
    return "none"


@dataclass
class HarmVerdict:
    level: str
    preserved: bool
    issue: str  # "ok" | "meaning_distortion" | "over_redaction"
    original_stance: str
    privatized_stance: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "preserved": self.preserved,
            "issue": self.issue,
            "original_stance": self.original_stance,
            "privatized_stance": self.privatized_stance,
            "detail": self.detail,
        }


def check(original: str, privatized: str, level: str) -> HarmVerdict:
    so, sp = _stance(original), _stance(privatized)
    if so == "condemns" and sp == "asserts":
        return HarmVerdict(
            level, False, "meaning_distortion", so, sp,
            "Counterspeech flipped into an assertion: the condemnation frame was "
            "redacted away, leaving the bare harmful claim. Routing tightened, "
            "level rejected for this input.",
        )
    if so == "asserts" and sp == "none":
        return HarmVerdict(
            level, False, "over_redaction", so, sp,
            "Harm judgment lost: the detector can no longer see the hateful "
            "content after privatization. Over-redacted.",
        )
    return HarmVerdict(
        level, True, "ok", so, sp,
        "Harm judgment preserved: stance and hate content survive privatization.",
    )
