"""AgnoSpeech Local Privatization Workbench — a desktop app over the library."""

__version__ = "0.9.0"


def _ensure_library() -> None:
    """Make the app runnable from a checkout without installing the library.

    If ``agnospeech`` isn't importable (no ``pip install -e ../agnospeech-lib``),
    fall back to the sibling source tree so ``python run.py`` just works.
    """
    import importlib.util

    if importlib.util.find_spec("agnospeech") is not None:
        return
    import sys
    from pathlib import Path

    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / "_lib",                       # vendored copy (Vercel / standalone)
        here.parent.parent.parent / "agnospeech-lib" / "src",  # sibling source (local dev)
    ]
    for src in candidates:
        if (src / "agnospeech").is_dir():
            sys.path.insert(0, str(src))
            return


_ensure_library()
