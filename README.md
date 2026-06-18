# AgnoSpeech — Local Privatization Workbench

Privatize text **entirely on-device** with the holistic editor from the
[`agnospeech`](../agnospeech-lib) library. Runs as a desktop app *and* as a
web app — the same Python backend powers both. No LLM, no cloud, no hate-word
lexicon; raw text never leaves the machine.

**Live:** https://agnospeech-workbench.vercel.app

## The four tabs

1. **Simple use** — paste text → privatized version, live. Words the editor
   removes/replaces are highlighted on your text (the "what gets changed" view),
   with a "N words changed" count.
2. **Advanced use** — a slider playground: one fixed sentence, each slider shown
   at low vs high so you can see its isolated effect, plus an all-three-together
   live block.
3. **Upload dataset** — drop a CSV/JSON, every row is privatized (original with
   changed words highlighted → edited), download the privatized CSV.
4. **Info** — repo, creators, scope.

## What the editor does

The holistic editor (the library's primary method) redacts identifiers to typed
placeholders, keeps the harm evidence a detector needs, and thins
author-identifying style — one learned pass, deterministic.

- Structured PII: `@handle`→`[USER]`, phone→`[NUMBER]`, email→`[EMAIL]`, URL→`[URL]`.
- Group terms → `[RACE_ETHNICITY_GROUP]`, `[GENDER_GROUP]`, `[RELIGIOUS_GROUP]`, …
- **Names** → `[PERSON]` via deterministic, context-aware rules (no NER model):
  a capital is a name when it follows a **title** (`Mr`, `Dr`), a **person-relation
  noun** (`friend`, `neighbour`, `sender`, `landlord`), or precedes a
  **communication/threat verb** (`said`, `wrote`, `texted`, `threatened`,
  `reported`). Stylistic capitals (Sorcerer, Paladin) are left alone. For full
  NER, the `heavy` extra (Presidio + GLiNER) is a drop-in.

## Run locally (desktop)

```bash
cd workbench
pip install -e ../agnospeech-lib      # the library backend
python run.py                         # native window (pywebview) or browser
```

Env controls: `AGNO_PORT`, `AGNO_HOST`, `AGNO_NO_WINDOW=1` (headless server mode).

## Build a desktop executable

```bash
pip install -e ../agnospeech-lib pyinstaller pywebview pyqt6 pyqt6-webengine
pyinstaller build/workbench.spec --distpath dist --workpath build/_work
./dist/agnospeech-workbench           # one file (~158 MB); .exe on Windows
```

## Deploy to Vercel (web app)

The whole app is one **single Python serverless entrypoint** — `server.py:Handler`
routes the static frontend (`web/`) and every `/api/*` endpoint. `pyproject.toml`
points Vercel at it and installs deps with **uv**; the library is **vendored** into
`_lib/` so the deploy is self-contained (no git clone, works with a private repo).

```bash
cd workbench
vercel --prod --scope <your-team>
```

Notes:
- `pandas` is dropped (unused by the holistic path) → bundle ≈ 196 MB, under Vercel's limit.
- Stateless: nothing relies on shared memory.
- The light endpoints (`/api/edit`, `/api/dataset`) run well within the Hobby
  function limit. Re-vendor the library after changing it:
  `cp -r ../agnospeech-lib/src/agnospeech _lib/agnospeech`.

## Layout

```
workbench/
  run.py                       launcher (server + window/browser)
  pyproject.toml               Vercel entrypoint + uv deps
  agnospeech_workbench/
    server.py                  the single entrypoint — static + JSON API
    api_logic.py               stateless request->response handlers
    pipeline.py                calls the agnospeech library (edit, dataset, run)
    corpus.py                  loader + synthetic demo
  _lib/agnospeech/             vendored library (for self-contained deploy)
  web/                         index.html, style.css, app.js  (Simple/Advanced/Upload/Info)
  build/workbench.spec         PyInstaller spec
```

## API

| Endpoint | Purpose |
|----------|---------|
| `POST /api/edit` | privatize one free-form text (Simple use, playground) |
| `POST /api/dataset` | privatize an uploaded CSV/JSON, per-row (Upload tab) |
| `GET /api/demo` | synthetic demo rows |
| `POST /api/run` | full scorecard (attacker + detector + frontier) — heavy, not used by the UI |
| `POST /api/release` | zip a result (stateless, base64) |

## Creators

Maxim Dnestreanschii (backend & deployment) · Gabriel Creanga (UI/UX) ·
Vlad Garbuz (legal) · Chirill Donos (NLP engineer & team lead).
