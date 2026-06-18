"""Corpus loading + a synthetic helpline demo set.

A corpus row is a dict with at least a ``text`` field; ``author`` and ``hs``
(0/1 hate/harm label) sharpen the holistic editor and make the scorecard real.
The demo set mimics the helpline-report framing of the design: survivor reports
that quote an abuser, carrying direct identifiers (names, phones, emails,
locations) plus author-style signal an attribution attacker could exploit.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

# --- synthetic helpline demo corpus -------------------------------------------
# Eight reporters, multiple messages each, mixed harm labels. Hand-written so the
# holistic editor has identifiers to strip, harm evidence to keep, and per-author
# idiolect for the authorship attacker to (try to) latch onto.
_DEMO: list[dict[str, Any]] = [
    # --- anca: formal, opens with "Honestly,"/"Look," ; ex-partner Marcus ------
    {"author": "anca", "hs": 1, "text": "Honestly, Marcus keeps texting me from 555-0142 saying he will show up at my flat on Rue Lavoisier and make me regret leaving. I am scared, truly."},
    {"author": "anca", "hs": 1, "text": "Look, he found my new email anca.dragan@mail.com and wrote that next time he will bring his brother too. Honestly this is escalating fast."},
    {"author": "anca", "hs": 1, "text": "Honestly he smashed the door again last night, screaming that I belong to him. I really do think Marcus will hurt me eventually."},
    {"author": "anca", "hs": 1, "text": "Look, Marcus parked outside the office on Rue Lavoisier for an hour. Honestly I could not breathe, I just sat under my desk."},
    {"author": "anca", "hs": 0, "text": "Honestly the caseworker Sofia was kind today, she gave me a number for a shelter near Gare du Nord. A small relief, truly."},
    {"author": "anca", "hs": 0, "text": "Look, I filed the report at last. Honestly the officer was patient and wrote down every date about Marcus. I feel a little lighter."},
    {"author": "anca", "hs": 1, "text": "Honestly he messaged again from 555-0142 to say no court will keep him away. Look, I do not know how he keeps getting numbers."},
    {"author": "anca", "hs": 1, "text": "Look, Marcus told my sister he will burn the flat on Rue Lavoisier with me inside. Honestly I am writing this in case something happens."},
    # --- boris: British slang, lowercase, "mate","n","dunno","proper","cheers" -
    {"author": "boris", "hs": 1, "text": "mate, my neighbour Dragan threatened to torch the car if i grass him up to the council, reckons people like me dont belong on Oak Street"},
    {"author": "boris", "hs": 1, "text": "same bloke Dragan cornered my kid outside school today n said worse is coming. proper fuming mate, dunno what to do anymore"},
    {"author": "boris", "hs": 1, "text": "he's back, rang me off 555-0199 callin me a parasite n sayin he'll have me n the family deported. cant sleep mate, proper shaken"},
    {"author": "boris", "hs": 1, "text": "mate Dragan slashed two tyres on Oak Street last night n left a note sayin im next. dunno who else to ring, proper scared now"},
    {"author": "boris", "hs": 0, "text": "cheers for the callback yesterday mate, the officer took all the Oak Street details. felt heard for once, proper grateful"},
    {"author": "boris", "hs": 0, "text": "alright so the council finally logged it. cheers for chasin it mate, dunno where id be without the helpline honestly"},
    {"author": "boris", "hs": 1, "text": "Dragan again mate, shouted across Oak Street that my sort breed like rats n should be put down. proper vile, n the kids heard it"},
    {"author": "boris", "hs": 1, "text": "got a text off 555-0199 sayin theyll firebomb the shop if i testify. dunno mate, proper terrified for the family now"},
    # --- fatima: formal, polite, religious discrimination; landlord Whitcombe --
    {"author": "fatima", "hs": 1, "text": "My landlord Mr. Whitcombe said that women in hijab make the building look bad and that he will evict us by Friday. His email is whitcombe.r@estates.co."},
    {"author": "fatima", "hs": 1, "text": "Again Mr. Whitcombe slid a note under our door saying our kind should go back where we came from. The children read it before I could stop them."},
    {"author": "fatima", "hs": 1, "text": "He cut the heating off on purpose this morning and laughed, saying freezing us out is perfectly legal. You may reach me at +33 6 12 34 56 78."},
    {"author": "fatima", "hs": 1, "text": "Mr. Whitcombe told the other tenants not to speak to the Muslim family on the third floor. I am ashamed to say the isolation is working."},
    {"author": "fatima", "hs": 0, "text": "The translator at the centre, Yousef, kindly helped me draft a formal complaint today. I felt a great deal calmer afterwards, thank you."},
    {"author": "fatima", "hs": 0, "text": "I wish to thank the volunteer who sat with my daughter while I gave my statement. Your patience meant more than I can properly express."},
    {"author": "fatima", "hs": 1, "text": "Mr. Whitcombe has now changed the lock on the shared laundry and says only Christian families may use it. I have kept the note as evidence."},
    {"author": "fatima", "hs": 1, "text": "He emailed whitcombe.r@estates.co a final warning saying veiled women frighten his other tenants. I am frightened of him, not the reverse."},
    # --- dimitri: all-lowercase, "yo","im","gonna"; homophobic abuse at depot --
    {"author": "dimitri", "hs": 1, "text": "yo so this guy Pavel from the warehouse keeps shovin me n callin me slurs about bein gay, says hes gonna jump me after shift"},
    {"author": "dimitri", "hs": 1, "text": "pavel again left a dead rat in my locker with a note. im honestly not safe at that depot on Canal Road, gonna start recordin everythin"},
    {"author": "dimitri", "hs": 1, "text": "yo he found my insta @dimi_k n dm'd that faggots get whats comin to them. im screenshottin it all, gonna take it to the union"},
    {"author": "dimitri", "hs": 1, "text": "pavel n two mates blocked the Canal Road exit n said queers dont clock off. im shakin writin this, gonna ask for a transfer"},
    {"author": "dimitri", "hs": 0, "text": "yo the union rep finally answered, gonna log the Canal Road incidents proper. im feelin a bit steadier knowin someone listened"},
    {"author": "dimitri", "hs": 0, "text": "update yo, they moved pavel off my shift. im not fully relaxed but gonna actually sleep tonight, cheers to whoever pushed it"},
    {"author": "dimitri", "hs": 1, "text": "yo pavel keyed FAG into my car door in the Canal Road lot. im done stayin quiet, gonna file the police report tomorrow for real"},
    {"author": "dimitri", "hs": 1, "text": "he texted off a withheld number sayin he knows where i live n that im gonna regret snitchin. yo im genuinely terrified now"},
    # --- grace: precise, legal register; ex-husband Daniel, custody ------------
    {"author": "grace", "hs": 1, "text": "My ex-husband Daniel arrived at the nursery on Elm Avenue and told staff he would take our daughter and that I would never see her again. Call me on 555-0177."},
    {"author": "grace", "hs": 1, "text": "Daniel emailed daniel.kerr@webmail.com stating he will empty the joint account and leave me with nothing if I maintain the restraining order."},
    {"author": "grace", "hs": 1, "text": "He waited outside the Elm Avenue flat again and filmed me, stating he would publish the footage so everyone would know what kind of mother I am."},
    {"author": "grace", "hs": 1, "text": "Daniel breached the order for the third time on Tuesday, parking at Elm Avenue and photographing our daughter through the window. I have logged each instance."},
    {"author": "grace", "hs": 0, "text": "The legal-aid volunteer Priya was exceptional today and walked me through the Elm Avenue custody paperwork one step at a time. I am grateful."},
    {"author": "grace", "hs": 0, "text": "I wish to record that the court clerk processed the protective filing promptly. For the first time in months I feel the system is functioning."},
    {"author": "grace", "hs": 1, "text": "Daniel told our daughter that her mother is a liar who will be arrested. I am documenting this as deliberate emotional harm for the hearing."},
    {"author": "grace", "hs": 1, "text": "He messaged from 555-0177 to say that no judge will side with a hysterical woman. I am keeping every message for my solicitor."},
]


def demo_corpus() -> list[dict[str, Any]]:
    """A fresh copy of the synthetic helpline corpus."""
    return [dict(r) for r in _DEMO]


def load_rows(raw: str, filename: str = "") -> list[dict[str, Any]]:
    """Parse uploaded corpus text as JSONL, JSON array, or CSV into rows.

    Auto-detects by content/extension. Rows are normalized to carry whatever of
    ``text`` / ``author`` / ``hs`` the source provides; the holistic editor infers
    the rest from the column shape.
    """
    raw = raw.strip()
    if not raw:
        return []
    name = filename.lower()
    if name.endswith(".jsonl") or (raw[0] in "{[" and "\n{" in raw):
        rows = _parse_jsonl(raw)
        if rows:
            return rows
    if raw[0] == "[":
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
        except json.JSONDecodeError:
            pass
    if name.endswith(".jsonl") or raw[0] == "{":
        rows = _parse_jsonl(raw)
        if rows:
            return rows
    # fall back to CSV
    return list(csv.DictReader(io.StringIO(raw)))


def _parse_jsonl(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return []
        if isinstance(obj, dict):
            rows.append(obj)
    return rows
