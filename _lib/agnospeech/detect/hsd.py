"""Hate-speech detection head.

ONE shared calibrated head, trained once on raw text and then applied unchanged
to raw and to each privatized version. This is the honest protocol for comparing
Utility_original against Utility_protected: the detector is frozen, privatization
only changes its inputs. (Master build prompt section 7: "One shared calibrated
HSD head across levels for honest Uo vs Up".)

Lead model at the event is cardiffnlp/twitter-roberta-base-hate-latest behind
this same ``HsdHead`` interface; the CPU-only spine ships a TF-IDF + logistic
head so every number reproduces with no model download.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import FeatureUnion, Pipeline


class HsdHead:
    """Calibrated binary hate-speech classifier. Outputs class labels and
    macro-F1. Macro-F1 (not accuracy) is the utility metric, because the corpus
    is class-imbalanced and macro-F1 penalizes a majority-class shortcut."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        word = TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True
        )
        char = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True
        )
        self.model = Pipeline(
            [
                ("feats", FeatureUnion([("word", word), ("char", char)])),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=2000,
                        C=4.0,
                        class_weight="balanced",
                        random_state=seed,
                    ),
                ),
            ]
        )
        self._fitted = False

    def fit(self, texts: list[str], labels: list[int]) -> "HsdHead":
        self.model.fit(texts, labels)
        self._fitted = True
        return self

    def predict(self, texts: list[str]) -> np.ndarray:
        return self.model.predict(texts)

    def proba(self, texts: list[str]) -> np.ndarray:
        """P(hate) per text. Used for the per-post demo readout (the detector's
        confidence that the post is hateful, which should stay stable across
        privacy levels)."""
        return self.model.predict_proba(texts)[:, 1]

    @staticmethod
    def macro_f1(y_true: list[int], y_pred) -> float:
        return float(f1_score(y_true, y_pred, average="macro", zero_division=0))
