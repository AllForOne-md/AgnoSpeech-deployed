"""Pure request->response logic, shared by the local stdlib server and the
Vercel serverless functions. No framework, no global state — everything a
handler needs comes in the request body, so it works identically whether one
long-lived process serves it or a fresh serverless instance does.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from typing import Any

from .corpus import demo_corpus, load_rows
from .pipeline import edit_text, run_pipeline, transform_dataset


def handle_dataset(body: dict[str, Any]) -> dict[str, Any]:
    """Privatize an uploaded CSV/JSON: holistic edit per row, no scorecard."""
    rows = body.get("rows")
    if not rows:
        text = body.get("text")
        if text:
            rows = load_rows(text, body.get("filename", ""))
    if not rows:
        raise ValueError("Upload a CSV or JSON file with a text column.")
    return transform_dataset(
        rows,
        privacy_strength=float(body.get("privacy_strength", 0.65)),
        utility_strength=float(body.get("utility_strength", 0.72)),
        context_window=int(body.get("context_window", 1)),
    )


def handle_edit(body: dict[str, Any]) -> dict[str, Any]:
    return edit_text(
        str(body.get("text", "")),
        privacy_strength=float(body.get("privacy_strength", 0.65)),
        utility_strength=float(body.get("utility_strength", 0.72)),
        context_window=int(body.get("context_window", 1)),
    )


def handle_run(body: dict[str, Any]) -> dict[str, Any]:
    rows = body.get("rows")
    if not rows:
        text = body.get("text")
        if text:
            rows = load_rows(text, body.get("filename", ""))
    if not rows:
        rows = demo_corpus()
    return run_pipeline(
        rows,
        privacy_strength=float(body.get("privacy_strength", 0.65)),
        utility_strength=float(body.get("utility_strength", 0.72)),
        context_window=int(body.get("context_window", 1)),
    )


def handle_release(body: dict[str, Any]) -> dict[str, Any]:
    """Build the release zip from the result posted in the body (stateless).

    Returns the zip as base64 so a serverless caller can stream it straight to a
    browser download — no server-side file, no shared memory.
    """
    result = body.get("result")
    if not result:
        raise ValueError("Run privatization first (no result supplied).")
    stamp = str(body.get("date", "")) or "release"
    messages = result.get("messages", [])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        corpus = [
            {"code": m.get("code"), "author": m.get("author"), "hs": m.get("hs"),
             "edited": m.get("edited")}
            for m in messages
        ]
        z.writestr("privatized_corpus.jsonl", "\n".join(json.dumps(r) for r in corpus))
        z.writestr("scorecard.json", json.dumps(result.get("scorecard", {}), indent=2))
        z.writestr("counts.json", json.dumps(result.get("counts", {}), indent=2))
        z.writestr("harm_check.json", json.dumps(result.get("harmcheck", {}), indent=2))
        audit = [
            {"code": m.get("code"), "identifiers_removed": len(m.get("placeholders") or []),
             "placeholders": m.get("placeholders"), "compression": m.get("compression")}
            for m in messages
        ]
        z.writestr("authorship_audit.json", json.dumps(audit, indent=2))
        z.writestr("README.txt",
                   "AgnoSpeech release package\n"
                   "Method: holistic editor (agnospeech library)\n"
                   f"Generated: {stamp}\nEgress: 0 bytes (on-device only)\n")
    data = buf.getvalue()
    return {
        "filename": f"agnospeech_release_{stamp}.zip",
        "bytes": len(data),
        "zip_b64": base64.b64encode(data).decode("ascii"),
        "contents": ["privatized_corpus.jsonl", "scorecard.json", "authorship_audit.json",
                     "harm_check.json", "README.txt"],
    }
