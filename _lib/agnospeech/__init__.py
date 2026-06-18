"""AgnoSpeech: privacy-preserving text minimization for hate speech detection.

The **primary** path is the *holistic editor* — a lexicon-free, LLM-free,
CPU-only text minimizer. It learns which tokens carry the task signal and which
are author-identifying, redacts direct identifiers with a readable placeholder
renderer, and keeps only the evidence. It is the single recommended path for
arbitrary text and CSV/tabular work:

    import agnospeech as ag
    ag.transform_texts(["..."], labels=[...])   # plain strings in/out
    ag.transform_csv_text(csv_string)           # CSV in/out (web/API)

The **legacy** path is the tiered L0–L3 privatization dial (L0 raw, L1 redact,
L2 distill, L3 DP-grounded rewrite). It predates the holistic editor and is kept
for reproducibility of the original trade-off study; new callers should prefer
the holistic functions above.

Honesty discipline (see docs/limitations-ledger.md):
- L3 output is DP-grounded, never "differentially private".
- The self-attack stop is a calibrated stopping rule, never a certificate.
- Privacy is closed-world attribution, an upper-bias (optimistic) estimate.
- The adaptive attacker is the default headline, not the static one.
"""

__version__ = "0.1.0"

# --- Primary: holistic editor -------------------------------------------------
from .facade import (
    evaluate,
    transform_csv,
    transform_csv_text,
    transform_texts,
)
from .holistic import (
    HolisticConfig,
    HolisticResult,
    ReadablePlaceholderRenderer,
    transform_rows,
)

# --- Eval / attack building blocks --------------------------------------------
from .attacks import AuthorshipAttacker
from .datasets import Post, RedditCorpus
from .detect import HsdHead
from .harness import run_eval

# --- Legacy: tiered L0–L3 privatization dial ----------------------------------
from .facade import Level, privatize, privatize_many
from .privatize import (
    L1Redact,
    L2Distill,
    L3Rewrite,
    Privatizer,
    RawPassthrough,
    default_levels,
)

__all__ = [
    "__version__",
    # --- primary: holistic editor ---
    "transform_texts",
    "transform_csv",
    "transform_csv_text",
    "transform_rows",
    "HolisticConfig",
    "HolisticResult",
    "ReadablePlaceholderRenderer",
    # --- evaluation ---
    "evaluate",
    "run_eval",
    "HsdHead",
    "AuthorshipAttacker",
    "Post",
    "RedditCorpus",
    # --- legacy: tiered L0–L3 dial ---
    "privatize",
    "privatize_many",
    "Level",
    "Privatizer",
    "RawPassthrough",
    "L1Redact",
    "L2Distill",
    "L3Rewrite",
    "default_levels",
]
