"""Readable render-time placeholders for the holistic editor.

The renderer is deterministic by design: it uses local regexes plus a small
reviewable taxonomy, then renders sensitive/community spans as typed
placeholders after the edit policy has chosen what ordinary tokens to keep.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agnospeech.privatize.patterns import find_pii_spans

TOKEN_RE = re.compile(r"\[[A-Z_]+\]|[A-Za-z][A-Za-z0-9_'-]*|\d+(?:\.\d+)?|[^\w\s]")
WORD_RE = re.compile(r"[A-Za-z0-9_'-]+$")

PII_PLACEHOLDERS = {
    "EMAIL": "[EMAIL]",
    "HANDLE": "[USER]",
    "MONEY": "[NUMBER]",
    "NUMBER": "[NUMBER]",
    "PERSON": "[PERSON]",
    "PHONE": "[PHONE]",
    "URL": "[URL]",
}

COMMUNITY_TERMS: dict[str, str] = {
    # Religion
    "atheist": "[RELIGIOUS_GROUP]",
    "atheists": "[RELIGIOUS_GROUP]",
    "buddhist": "[RELIGIOUS_GROUP]",
    "buddhists": "[RELIGIOUS_GROUP]",
    "christian": "[RELIGIOUS_GROUP]",
    "christians": "[RELIGIOUS_GROUP]",
    "hindu": "[RELIGIOUS_GROUP]",
    "hindus": "[RELIGIOUS_GROUP]",
    "islamic": "[RELIGIOUS_GROUP]",
    "jew": "[RELIGIOUS_GROUP]",
    "jewish": "[RELIGIOUS_GROUP]",
    "jews": "[RELIGIOUS_GROUP]",
    "muslim": "[RELIGIOUS_GROUP]",
    "muslims": "[RELIGIOUS_GROUP]",
    "sikh": "[RELIGIOUS_GROUP]",
    "sikhs": "[RELIGIOUS_GROUP]",
    # Nationality / citizenship / migration status
    "american": "[NATIONALITY_GROUP]",
    "americans": "[NATIONALITY_GROUP]",
    "british": "[NATIONALITY_GROUP]",
    "citizen": "[NATIONALITY_GROUP]",
    "citizens": "[NATIONALITY_GROUP]",
    "french": "[NATIONALITY_GROUP]",
    "german": "[NATIONALITY_GROUP]",
    "germans": "[NATIONALITY_GROUP]",
    "hungarian": "[NATIONALITY_GROUP]",
    "hungarians": "[NATIONALITY_GROUP]",
    "immigrant": "[NATIONALITY_GROUP]",
    "immigrants": "[NATIONALITY_GROUP]",
    "migrant": "[NATIONALITY_GROUP]",
    "migrants": "[NATIONALITY_GROUP]",
    "refugee": "[NATIONALITY_GROUP]",
    "refugees": "[NATIONALITY_GROUP]",
    "romanian": "[NATIONALITY_GROUP]",
    "romanians": "[NATIONALITY_GROUP]",
    # Gender / sex
    "female": "[GENDER_GROUP]",
    "females": "[GENDER_GROUP]",
    "girl": "[GENDER_GROUP]",
    "girls": "[GENDER_GROUP]",
    "male": "[GENDER_GROUP]",
    "males": "[GENDER_GROUP]",
    "man": "[GENDER_GROUP]",
    "men": "[GENDER_GROUP]",
    "woman": "[GENDER_GROUP]",
    "women": "[GENDER_GROUP]",
    # Sexuality
    "bisexual": "[SEXUALITY_GROUP]",
    "bisexuals": "[SEXUALITY_GROUP]",
    "gay": "[SEXUALITY_GROUP]",
    "gays": "[SEXUALITY_GROUP]",
    "lesbian": "[SEXUALITY_GROUP]",
    "lesbians": "[SEXUALITY_GROUP]",
    "queer": "[SEXUALITY_GROUP]",
    "trans": "[SEXUALITY_GROUP]",
    "transgender": "[SEXUALITY_GROUP]",
    # Race / ethnicity
    "asian": "[RACE_ETHNICITY_GROUP]",
    "asians": "[RACE_ETHNICITY_GROUP]",
    "black": "[RACE_ETHNICITY_GROUP]",
    "blacks": "[RACE_ETHNICITY_GROUP]",
    "latino": "[RACE_ETHNICITY_GROUP]",
    "latinos": "[RACE_ETHNICITY_GROUP]",
    "roma": "[RACE_ETHNICITY_GROUP]",
    "white": "[RACE_ETHNICITY_GROUP]",
    "whites": "[RACE_ETHNICITY_GROUP]",
    # Disability / age / political identity
    "autistic": "[DISABILITY_GROUP]",
    "blind": "[DISABILITY_GROUP]",
    "disabled": "[DISABILITY_GROUP]",
    "elderly": "[AGE_GROUP]",
    "old": "[AGE_GROUP]",
    "young": "[AGE_GROUP]",
    "conservative": "[POLITICAL_GROUP]",
    "conservatives": "[POLITICAL_GROUP]",
    "liberal": "[POLITICAL_GROUP]",
    "liberals": "[POLITICAL_GROUP]",
}

PERSON_HINTS = {
    "alice", "alex", "bob", "chris", "david", "emma", "john", "jane", "maria",
    "michael", "mike", "sarah",
}

# A capitalized word ending the previous token here marks a new sentence, so the
# next capital is grammar, not a name.
_SENT_BREAK = set(".!?…:;\"“”«»)]")

# Common capitalized words to NOT treat as names (days/months + a few frequents),
# so the proper-noun heuristic doesn't over-redact ordinary mid-sentence capitals.
_NAME_STOP = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "i", "im", "ill", "ive", "id", "ok", "okay", "yes", "no", "god", "internet",
    "english", "covid",
}

# Closed-class grammatical cues — NOT a list of names. A capitalized word is a
# person when it follows a title or a person-relation noun, precedes a speech /
# action verb, or sits in a capitalized run. This is the "smart" deterministic
# signal that replaces relying on a hardcoded name array.
_TITLE_WORDS = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "professor", "sir", "madam", "madame",
    "lord", "lady", "rev", "reverend", "fr", "father", "judge", "officer", "sgt",
    "sergeant", "capt", "captain", "gen", "president", "mayor", "detective", "agent",
    "inspector", "constable", "uncle", "aunt", "auntie",
}
_RELATION_WORDS = {
    "friend", "neighbour", "neighbor", "colleague", "coworker", "classmate",
    "roommate", "flatmate", "boss", "manager", "landlord", "tenant", "sender",
    "author", "user", "husband", "wife", "spouse", "partner", "boyfriend",
    "girlfriend", "son", "daughter", "sister", "brother", "mother", "father",
    "mom", "mum", "dad", "cousin", "nephew", "niece", "grandfather", "grandmother",
    "stepfather", "stepmother", "stepson", "stepdaughter", "stepbrother",
    "stepsister", "ex", "fiance", "fiancee", "teacher", "student", "doctor",
    "nurse", "patient", "lawyer", "client", "guard", "driver", "named", "called",
    "aka", "alias", "guy", "bloke", "man", "woman", "lad", "kid",
}
# Communication / threat verbs only — these strongly imply a *person* subject,
# so a capital before one is almost certainly a name. Generic action/perception
# verbs (saw, came, keeps, lives, works…) are deliberately excluded: they fire on
# ordinary capitalized nouns and over-redact.
_PERSON_VERBS = {
    "said", "says", "wrote", "writes", "told", "tells", "asked", "asks", "texted",
    "texts", "messaged", "messages", "emailed", "emails", "replied", "replies",
    "reported", "reports", "threatened", "threatens", "shouted", "screamed",
    "yelled", "warned", "warns", "claimed", "claims", "mentioned", "complained",
}


@dataclass(frozen=True)
class RenderToken:
    text: str
    start: int
    end: int
    placeholder: str | None = None


@dataclass(frozen=True)
class RenderedText:
    text: str
    placeholders: list[str]


class ReadablePlaceholderRenderer:
    """Render selected tokens with semantic placeholders and light cleanup."""

    def tokenize(self, text: str) -> list[RenderToken]:
        tokens = [RenderToken(m.group(0), m.start(), m.end()) for m in TOKEN_RE.finditer(text)]
        if not tokens:
            return []
        labels: list[str | None] = [None] * len(tokens)
        self._mark_pii(text, tokens, labels)
        self._mark_communities(tokens, labels)
        self._mark_person_hints(tokens, labels)
        self._mark_person_heuristic(tokens, labels)
        return [
            RenderToken(tok.text, tok.start, tok.end, labels[i])
            for i, tok in enumerate(tokens)
        ]

    def render(self, tokens: list[RenderToken], keep: list[bool]) -> RenderedText:
        pieces: list[str] = []
        placeholders: list[str] = []
        previous_placeholder = ""
        for tok, flag in zip(tokens, keep):
            piece = tok.placeholder if tok.placeholder else (tok.text if flag else "")
            if not piece:
                previous_placeholder = ""
                continue
            if tok.placeholder:
                if tok.placeholder == previous_placeholder:
                    continue
                placeholders.append(tok.placeholder)
                previous_placeholder = tok.placeholder
            else:
                previous_placeholder = ""
            pieces.append(piece)
        text = _cleanup(_join_tokens(pieces))
        return RenderedText(text=text, placeholders=_dedupe(placeholders))

    def _mark_pii(self, text: str, tokens: list[RenderToken], labels: list[str | None]) -> None:
        for start, end, ptype in find_pii_spans(text):
            placeholder = PII_PLACEHOLDERS.get(ptype, f"[{ptype}]")
            for i, tok in enumerate(tokens):
                if tok.end <= start or tok.start >= end:
                    continue
                labels[i] = placeholder

    def _mark_communities(self, tokens: list[RenderToken], labels: list[str | None]) -> None:
        for i, tok in enumerate(tokens):
            if labels[i]:
                continue
            labels[i] = COMMUNITY_TERMS.get(_norm(tok.text))

    def _mark_person_hints(self, tokens: list[RenderToken], labels: list[str | None]) -> None:
        for i, tok in enumerate(tokens):
            if labels[i] or not WORD_RE.fullmatch(tok.text):
                continue
            low = _norm(tok.text)
            if low in PERSON_HINTS:
                labels[i] = "[PERSON]"

    def _mark_person_heuristic(self, tokens: list[RenderToken], labels: list[str | None]) -> None:
        """Deterministic, context-aware proper-noun detection — a NER-free stand-in
        for the GLiNER/Presidio drop-in.

        A capitalized alphabetic word is redacted as ``[PERSON]`` ONLY when a
        closed-class grammatical cue identifies it as a person — never just because
        it is capitalized (stylistic capitals like *Sorcerer*, *Paladin*, *Health
        Stones* must survive). The cues:

        - it follows a **title** (``Mr``, ``Dr`` …);
        - it follows a **person-relation noun** (``friend``, ``neighbour``,
          ``landlord``, ``sender`` …);
        - it precedes a **speech/action verb** (``said``, ``wrote``, ``threatened``,
          ``keeps`` …) — catching subjects like *Maria reported*, *Marcus keeps*.

        No cue → left untouched. Same input always yields the same output.
        """
        n = len(tokens)
        for i, tok in enumerate(tokens):
            if labels[i] or not WORD_RE.fullmatch(tok.text):
                continue
            t = tok.text
            if len(t) < 2 or not t.isalpha() or t.isupper() or not t[0].isupper():
                continue
            if _norm(t) in _NAME_STOP:
                continue
            prev = tokens[i - 1].text if i > 0 else ""
            nxt = tokens[i + 1].text if i + 1 < n else ""
            prevn, nxtn = _norm(prev), _norm(nxt)
            if prevn in _TITLE_WORDS or prevn in _RELATION_WORDS or nxtn in _PERSON_VERBS:
                labels[i] = "[PERSON]"


def _norm(value: str) -> str:
    return value.lower().strip("'\".,:;!?()[]{}")


def _join_tokens(toks: list[str]) -> str:
    text = " ".join(toks)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([\[(])\s+", r"\1", text)
    text = re.sub(r"\s+([\])])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _cleanup(text: str) -> str:
    text = re.sub(r"\b(a|an)\s+(\[[A-Z_]+\])", r"a \2", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,;:")


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


__all__ = ["ReadablePlaceholderRenderer", "RenderedText", "RenderToken"]
