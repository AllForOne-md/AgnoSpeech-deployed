from .base import Privatizer, RawPassthrough
from .l1_redact import L1Redact
from .l2_rationale import L2Distill
from .l3_dp_rewrite import L3Rewrite


def default_levels(l3_intensity: float = 0.6, seed: int = 0) -> dict[str, Privatizer]:
    """The L0->L3 dial used by the harness and demo, in order."""
    return {
        "L0": RawPassthrough(),
        "L1": L1Redact(),
        "L2": L2Distill(),
        "L3": L3Rewrite(intensity=l3_intensity, seed=seed),
    }


__all__ = [
    "Privatizer",
    "RawPassthrough",
    "L1Redact",
    "L2Distill",
    "L3Rewrite",
    "default_levels",
]
