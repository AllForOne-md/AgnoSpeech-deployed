/* AgnoSpeech Local Privatization Workbench — frontend.
   All privacy logic lives in the Python backend (the agnospeech library); this
   file only renders the design and drives the API.

   Two setups: Simple use (live editor) and Advanced use (slider playground +
   full-corpus run), plus an Info tab. */

const THEMES = {
  paper: {'bg':'#d9d2c6','win':'#fbf9f5','panel':'#fbf9f5','panel2':'#f3efe7','inset':'#ece7dc','fg':'#211c14','fg2':'#3d362b','muted':'#6f6557','faint':'#a59a89','border':'#e7e0d3','border-strong':'#d6cdbc','accent':'#0f7a6e','accent-fg':'#ffffff','accent-soft':'#e0efea','titlebar':'#f1ece2','sidebar':'#f3efe7','sidebar-active':'#e0efea','l1':'#8a5a12','l1-bg':'#f4e7cf','l2':'#0f7a6e','l2-bg':'#ddeee9','l3':'#6a4aa8','l3-bg':'#e9e2f4','safe':'#2c7a4f','safe-bg':'#e1efe6','warn':'#8a5a12','warn-bg':'#f4e7cf','danger':'#a8432c','danger-bg':'#f3e2dc','shadow':'rgba(80,60,30,0.20)'},
};

const REPO_URL = "https://github.com/AllForOne-md/AgnoSpeech";

// Honesty: the on-device / 0-egress claims only hold for the desktop app (loopback).
// A hosted (Vercel) deployment sends text to a serverless function to privatize it.
const HOSTED = !['localhost', '127.0.0.1', '0.0.0.0', ''].includes(location.hostname);
const PRIV_NOTE = HOSTED ? 'sent to the server to privatize' : 'never leaves this machine';
const ENV_NOTE = HOSTED ? 'processed on the server · not stored' : 'on-device · 0 B sent';

const MODES = [
  {id:'simple',   icon:'✎', label:'Simple use'},
  {id:'advanced', icon:'⚙', label:'Advanced use'},
  {id:'upload',   icon:'⬆', label:'Upload dataset'},
  {id:'info',     icon:'ⓘ', label:'Info'},
];

const state = {
  theme: 'paper',
  mode: 'simple',
  rows: [],
  fileName: 'helpline_reports_demo.jsonl',
  text: null,                // uploaded raw text (else demo)
  privacy: 0.65, utility: 0.72, context: 1,
  busy: false,
  result: null,
  released: null,
  // live editor
  editorRaw: "Honestly, Marcus keeps texting me from 555-0142 saying he'll show up at my flat on Rue Lavoisier. Reach me at anca.dragan@mail.com.",
  editorOut: null,
  editBusy: false,
  // advanced playground
  demos: null,        // per-slider low/high comparisons (fixed)
  combined: null,     // all-three-together output (live)
  combBusy: false,
  // upload dataset
  datasetName: null,
  datasetText: null,
  datasetResult: null,
  datasetBusy: false,
};

// What each slider actually does — shown beneath every slider.
const SLIDERS = [
  {k:'privacy', label:'Privacy strength', min:0.3, max:0.95, step:0.01, fmt:v=>v.toFixed(2),
   desc:'How hard the editor drops author-identifying / risky tokens. ↑ more scrubbed → more private, less readable.'},
  {k:'utility', label:'Utility strength', min:0.3, max:0.95, step:0.01, fmt:v=>v.toFixed(2),
   desc:'How much harm / task evidence is kept for the detector. ↑ retains more of the signal a triage model needs.'},
  {k:'context', label:'Context window', min:0, max:3, step:1, ticks:[0,1,2,3], fmt:v=>`${v} word${v==1?'':'s'}`,
   desc:'Neighbouring words kept around each retained term, for readability. ↑ more surrounding context, longer output.'},
];

function sliderControl(s) {
  const v = state[s.k];
  const ticks = s.ticks ? `<div class="ticks">${s.ticks.map(t=>`<span>${t}</span>`).join('')}</div>` : '';
  return `<div class="ctrl">
    <label>${s.label} <b id="${s.k}v">${s.fmt(v)}</b></label>
    <input id="${s.k}" type="range" ${s.ticks?'class="stepped"':''} min="${s.min}" max="${s.max}" step="${s.step}" value="${v}">
    ${ticks}
    <div class="ctrl-desc">${s.desc}</div>
  </div>`;
}
function sliderBlock() {
  return `<div class="controls">${SLIDERS.map(sliderControl).join('')}</div>`;
}

// One fixed block of text used across every example so each slider's effect is
// comparable on the same input.
const DEMO_TEXT = "Honestly, Marcus keeps texting me from 555-0142 saying he'll show up at my flat on Rue Lavoisier. Reach me at anca.dragan@mail.com.";

const SLIDER_DEMOS = [
  {k:'privacy', label:'Privacy strength', lowCap:'0.40 · keeps more', highCap:'0.92 · scrubs more',
   low:{privacy_strength:0.40,utility_strength:0.72,context_window:1},
   high:{privacy_strength:0.92,utility_strength:0.72,context_window:1}},
  {k:'utility', label:'Utility strength', lowCap:'0.40 · trims hard', highCap:'0.92 · keeps evidence',
   low:{privacy_strength:0.65,utility_strength:0.40,context_window:1},
   high:{privacy_strength:0.65,utility_strength:0.92,context_window:1}},
  {k:'context', label:'Context window', lowCap:'0 words · keywords only', highCap:'3 words · full context',
   low:{privacy_strength:0.65,utility_strength:0.72,context_window:0},
   high:{privacy_strength:0.65,utility_strength:0.72,context_window:3}},
];

// ---- helpers ----------------------------------------------------------------
const $ = (s, r=document) => r.querySelector(s);
const pct = x => (x==null ? '—' : Math.round(x*100) + '%');
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const phHi = s => esc(s).replace(/\[[A-Z_]+\]/g, m => `<span class="ph">${m}</span>`);

// Mark, on the RAW input, every word the editor changed/removed — i.e. words not
// present in the privatized output (redactions become placeholders, dropped
// low-evidence words simply vanish). Shown everywhere raw text appears.
function markRaw(raw, edited) {
  if (!edited) return esc(raw);
  const kept = new Set((String(edited).toLowerCase().match(/[a-z0-9']+/g) || []));
  return esc(raw).replace(/[A-Za-z0-9']+/g, w => kept.has(w.toLowerCase()) ? w : `<span class="changed">${w}</span>`);
}

function applyTheme(name) {
  const t = THEMES[name]; const r = document.documentElement.style;
  for (const k in t) r.setProperty('--' + k, t[k]);
}

async function api(path, body) {
  const opt = body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {};
  const res = await fetch(path, opt);
  return res.json();
}

// ---- actions ----------------------------------------------------------------
let _liveTimer = null;
function scheduleLive() {
  clearTimeout(_liveTimer);
  if (state.mode === 'simple') _liveTimer = setTimeout(runEdit, 300);
  else if (state.mode === 'advanced') _liveTimer = setTimeout(runCombined, 250);
}

async function runEdit() {
  if (!state.editorRaw.trim()) return;
  state.editBusy = true;
  const out = $('#edOut'); if (out) out.innerHTML = '<span class="spin"></span> privatizing on device…';
  const r = await api('/api/edit', {
    text: state.editorRaw,
    privacy_strength: state.privacy, utility_strength: state.utility, context_window: state.context,
  });
  state.editBusy = false;
  if (r.error) { if (out) out.textContent = 'Error: ' + r.error; return; }
  state.editorOut = r;
  // patch the DOM in place so the textarea keeps focus + caret
  if (out) out.innerHTML = phHi(r.edited);
  const marked = $('#edRawMarked'); if (marked) marked.innerHTML = markRaw(state.editorRaw, r.edited);
  const st = $('#edStats');
  if (st) st.innerHTML = `<span class="chip changed-chip">${countChanged(state.editorRaw, r.edited)} words changed</span>
    <span class="chip id">${r.identifiers} identifiers</span>
    <span class="chip keep">${r.chars_in}→${r.chars_out} chars</span>`;
}

function countChanged(raw, edited) {
  const kept = new Set((String(edited).toLowerCase().match(/[a-z0-9']+/g) || []));
  const words = raw.match(/[A-Za-z0-9']+/g) || [];
  return words.filter(w => !kept.has(w.toLowerCase())).length;
}

async function runSliderDemos() {
  if (state.demos) return;
  const results = {};
  await Promise.all(SLIDER_DEMOS.map(async d => {
    const [low, high] = await Promise.all([
      api('/api/edit', {...d.low, text: DEMO_TEXT}),
      api('/api/edit', {...d.high, text: DEMO_TEXT}),
    ]);
    results[d.k] = {low, high};
  }));
  state.demos = results;
  SLIDER_DEMOS.forEach(d => {
    const r = state.demos[d.k];
    const lo = $('#demo-'+d.k+'-low'); if (lo) lo.innerHTML = phHi(r.low.edited);
    const hi = $('#demo-'+d.k+'-high'); if (hi) hi.innerHTML = phHi(r.high.edited);
  });
}

async function runCombined() {
  state.combBusy = true;
  const out = $('#comb-out'); if (out) out.innerHTML = '<span class="spin"></span>';
  const r = await api('/api/edit', {
    text: DEMO_TEXT,
    privacy_strength: state.privacy, utility_strength: state.utility, context_window: state.context,
  });
  state.combBusy = false; state.combined = r;
  if (out) out.innerHTML = r.error ? esc(r.error) : phHi(r.edited);
  const marked = $('#fixed-marked'); if (marked && !r.error) marked.innerHTML = markRaw(DEMO_TEXT, r.edited);
  const st = $('#comb-stat');
  if (st) st.innerHTML = r.error ? '' :
    `<span class="chip changed-chip">${countChanged(DEMO_TEXT, r.edited)} words changed</span>
     <span class="chip id">${r.identifiers} identifiers</span><span class="chip keep">${r.chars_in}→${r.chars_out} chars</span>
     <span class="chip risk">P ${state.privacy.toFixed(2)} · U ${state.utility.toFixed(2)} · C ${state.context}</span>`;
}

// ---- upload dataset ----
async function uploadDataset(file) {
  state.datasetName = file.name;
  state.datasetText = await file.text();
  state.datasetResult = null;
  await runDataset();
}
async function runDataset() {
  if (!state.datasetText) return;
  state.datasetBusy = true; render();
  const r = await api('/api/dataset', {
    text: state.datasetText, filename: state.datasetName,
    privacy_strength: state.privacy, utility_strength: state.utility, context_window: state.context,
  });
  state.datasetBusy = false;
  state.datasetResult = r;
  render();
}
function csvCell(s) {
  s = String(s == null ? '' : s);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
function downloadDataset() {
  const r = state.datasetResult;
  if (!r || r.error) return;
  const csv = 'ID,text\n' + r.messages.map(m => `${csvCell(m.code)},${csvCell(m.edited)}`).join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const base = (state.datasetName || 'dataset').replace(/\.[^.]+$/, '');
  const a = document.createElement('a');
  a.href = url; a.download = base + '_privatized.csv'; a.click();
  URL.revokeObjectURL(url);
}

function setMode(id) { state.mode = id; render(); }

// ---- rendering --------------------------------------------------------------
function render() {
  const nav = $('#nav');
  nav.innerHTML = MODES.map(m =>
    `<div class="step ${m.id===state.mode?'on':''}" data-mode="${m.id}">
      <span class="num">${m.icon}</span><span class="lbl">${m.label}</span></div>`).join('');
  nav.querySelectorAll('.step').forEach(el => el.onclick = () => setMode(el.dataset.mode));
  $('#main').innerHTML = VIEWS[state.mode]();
  wire();
}

function wire() {
  ['privacy','utility','context'].forEach(k => {
    const el = $('#'+k); if (!el) return;
    el.oninput = () => { $('#'+k+'v').textContent = k==='context'? el.value : (+el.value).toFixed(2); };
    el.onchange = () => { state[k] = +el.value; scheduleLive(); };
  });
  const raw = $('#rawIn');
  if (raw) raw.oninput = () => { state.editorRaw = raw.value; scheduleEditMarks(); scheduleLive(); };
  const editBtn = $('#editBtn'); if (editBtn) editBtn.onclick = runEdit;
  const dsFile = $('#dsFile');
  if (dsFile) dsFile.onchange = e => { const f = e.target.files[0]; if (f) uploadDataset(f); };
  const dsRun = $('#dsRun'); if (dsRun) dsRun.onclick = runDataset;
  const dsDl = $('#dsDl'); if (dsDl) dsDl.onclick = downloadDataset;
  if (state.mode === 'simple' && !state.editBusy) runEdit();
  if (state.mode === 'advanced') { runSliderDemos(); if (!state.combined && !state.combBusy) runCombined(); }
}

// keep the marked-input pane in sync while typing, even before the debounced edit
function scheduleEditMarks() {
  const marked = $('#edRawMarked');
  if (marked && state.editorOut) marked.innerHTML = markRaw(state.editorRaw, state.editorOut.edited);
}

// ---- views ------------------------------------------------------------------
const VIEWS = {
  simple() {
    const o = state.editorOut;
    const outHtml = state.editBusy ? '<span class="spin"></span> privatizing on device…'
      : (o ? phHi(o.edited) : '<span class="faint">Privatized text appears here.</span>');
    const rawMarked = o ? markRaw(state.editorRaw, o.edited) : esc(state.editorRaw);
    const stats = o ? `<span class="chip changed-chip">${countChanged(state.editorRaw, o.edited)} words changed</span>
      <span class="chip id">${o.identifiers} identifiers</span>
      <span class="chip keep">${o.chars_in}→${o.chars_out} chars</span>` : '';
    return `
      <div class="eyebrow">Simple use · holistic editor</div>
      <h1 class="step-title">Paste text → get a privatized version</h1>
      <div class="grid cols-2">
        <div class="card">
          <h3>Your text <span class="faint" style="font-weight:500">· ${PRIV_NOTE}</span></h3>
          <textarea id="rawIn" class="pane" placeholder="Paste or type sensitive text…">${esc(state.editorRaw)}</textarea>
          <div class="ex-label" style="margin-top:12px">WHAT GETS CHANGED <span class="changed-key">highlighted</span></div>
          <div id="edRawMarked" class="pane out marked">${rawMarked}</div>
        </div>
        <div class="card">
          <h3>Privatized output <span class="faint" style="font-weight:500">· agnospeech holistic</span></h3>
          <div id="edOut" class="pane out">${outHtml}</div>
          <div class="chips" id="edStats">${stats}</div>
        </div>
      </div>
      <div class="card" style="margin-top:16px">
        ${sliderBlock()}
        <div class="note">Updates live as you type or move a slider · ${ENV_NOTE}. Highlighted words on the left are the ones the editor removed or replaced.</div>
      </div>`;
  },

  advanced() {
    const demoByK = Object.fromEntries(SLIDER_DEMOS.map(d => [d.k, d]));
    const sliderSections = SLIDERS.map(s => {
      const d = demoByK[s.k];
      const r = state.demos && state.demos[s.k];
      const lo = r ? phHi(r.low.edited) : '<span class="spin"></span>';
      const hi = r ? phHi(r.high.edited) : '<span class="spin"></span>';
      return `<div class="card slider-card">
        ${sliderControl(s)}
        <div class="grid cols-2 ex-grid" style="margin-top:14px">
          <div><div class="ex-label">${d.lowCap}</div><div class="pane out" id="demo-${s.k}-low">${lo}</div></div>
          <div><div class="ex-label">${d.highCap}</div><div class="pane out" id="demo-${s.k}-high">${hi}</div></div>
        </div></div>`;
    }).join('');
    const c = state.combined;
    const combOut = state.combBusy ? '<span class="spin"></span>'
      : (c ? (c.error ? esc(c.error) : phHi(c.edited)) : '<span class="spin"></span>');
    const fixedMarked = (c && !c.error) ? markRaw(DEMO_TEXT, c.edited) : esc(DEMO_TEXT);
    const combStat = (c && !c.error) ?
      `<span class="chip changed-chip">${countChanged(DEMO_TEXT, c.edited)} words changed</span>
       <span class="chip id">${c.identifiers} identifiers</span><span class="chip keep">${c.chars_in}→${c.chars_out} chars</span>
       <span class="chip risk">P ${state.privacy.toFixed(2)} · U ${state.utility.toFixed(2)} · C ${state.context}</span>` : '';
    return `
      <div class="eyebrow">Advanced use · tune the editor</div>
      <h1 class="step-title">Slider playground — move a slider, watch the text change</h1>
      <div class="card" style="margin-bottom:16px">
        <div class="ex-label">THE FIXED SENTENCE <span class="changed-key">changed words highlighted</span></div>
        <div id="fixed-marked" class="pane out raw-ex marked">${fixedMarked}</div>
        <div class="note">Each slider below shows its own effect on this sentence — left = low, right = high, other sliders held fixed. ${ENV_NOTE}.</div>
      </div>
      <div class="grid" style="gap:16px">${sliderSections}</div>
      <div class="card" style="margin-top:16px;border-color:var(--accent)">
        <h3>All three together — live</h3>
        <div class="sub" style="margin-bottom:10px">The same sentence at your current slider values. Move any slider above and this updates.</div>
        <div class="pane out" id="comb-out">${combOut}</div>
        <div class="chips" id="comb-stat">${combStat}</div>
      </div>
      <div class="note" style="margin-top:14px">To privatize a whole CSV/JSON file, use the <b>Upload dataset</b> tab.</div>`;
  },

  upload() {
    const r = state.datasetResult;
    const drop = `
      <label class="dropzone">
        <div class="dz-plus">+</div>
        <div class="dz-title">${state.datasetName ? esc(state.datasetName) : 'Drop a CSV / JSON file, or click to browse'}</div>
        <div class="dz-sub">The editor infers the text column (and author/label if present) from the file.</div>
        <input id="dsFile" type="file" accept=".csv,.json,.jsonl" hidden>
      </label>`;
    const controls = state.datasetText ? `
      <div class="card" style="margin-top:16px">
        ${sliderBlock()}
        <div class="row" style="justify-content:center;margin-top:8px">
          <button class="btn" id="dsRun" ${state.datasetBusy?'disabled':''}>
            ${state.datasetBusy?'<span class="spin"></span> Privatizing dataset…':'Re-privatize with these settings &nbsp;→'}</button>
        </div>
        <div class="note" style="text-align:center">Holistic editor · ${ENV_NOTE}. Adjust the sliders, then re-privatize.</div>
      </div>` : '';
    let results = '';
    if (state.datasetBusy && !r) {
      results = `<div class="card" style="margin-top:16px;text-align:center"><span class="spin"></span> processing ${esc(state.datasetName||'')}…</div>`;
    } else if (r && r.error) {
      results = `<div class="card" style="margin-top:16px"><div class="sub" style="color:var(--danger)">${esc(r.error)}</div></div>`;
    } else if (r) {
      const ms = r.messages.slice(0, 60);
      const rowsHtml = ms.map(m => `
        <div class="msg">
          <div class="row"><span class="code">${esc(m.code)}${m.author?` · ${esc(m.author)}`:''}</span>
            ${m.hs!=null?`<span class="tag ${m.hs==1?'hs1':'hs0'}">${m.hs==1?'harm':'benign'}</span>`:''}</div>
          <div class="bl faint mono" style="font-size:9.5px;margin-top:6px">ORIGINAL · changed words highlighted</div>
          <div class="txt muted">${markRaw(m.raw, m.edited)}</div>
          <div class="arrow">↓ privatized</div>
          <div class="edit">${phHi(m.edited)}</div>
          <div class="chips">${m.placeholders.map(p=>`<span class="chip id">${esc(p)}</span>`).join('')}</div>
        </div>`).join('');
      results = `
        <div class="card" style="margin-top:16px">
          <div class="row" style="justify-content:space-between;flex-wrap:wrap;gap:10px">
            <h3 style="margin:0">Privatized dataset <span class="faint" style="font-weight:500">· ${r.counts.messages.toLocaleString()} rows · ${r.counts.identifiers_removed} identifiers removed${r.counts.has_labels?'':' · no label column'}</span></h3>
            <button class="btn tiny" id="dsDl">Download privatized CSV</button>
          </div>
          <div style="margin-top:12px">${rowsHtml}</div>
          ${r.messages.length>60?`<div class="note">Showing 60 of ${r.messages.length.toLocaleString()} rows — the download has them all.</div>`:''}
        </div>`;
    }
    return `
      <div class="eyebrow">Upload dataset · holistic</div>
      <h1 class="step-title">Upload a CSV / JSON → see the privatized dataset</h1>
      ${drop}
      ${controls}
      ${results}`;
  },

  info() {
    return `
      <div class="eyebrow">Info</div>
      <h1 class="step-title">About AgnoSpeech</h1>
      <div class="grid cols-2">
        <div class="card">
          <h3>What it does</h3>
          <div class="sub" style="line-height:1.7">
            AgnoSpeech is a privacy-preserving text minimizer for hate-speech detection.
            Its <b>holistic editor</b> runs entirely on this device — no LLM, no cloud, no
            hate-word lexicon. It redacts direct identifiers (names, phones, emails,
            locations → typed placeholders), keeps the harm evidence a detector needs,
            and thins author-identifying style. ${HOSTED ? 'No LLM and no cloud AI — the editor runs in a serverless function and stores nothing; the desktop app runs the same editor fully on-device.' : 'No LLM, no cloud — raw text never leaves the machine.'}
          </div>
          <div class="note" style="margin-top:12px">Built for the Council of Europe
            “Hack the Hate, Renew Democracy” Democracy Hackathon, Strasbourg 2026.</div>
        </div>
        <div class="card">
          <h3>Repository</h3>
          <div class="sub">Source, the <span class="mono">agnospeech</span> library, the research spine and this workbench:</div>
          <div style="margin-top:12px">
            <a class="btn" href="${REPO_URL}" target="_blank" rel="noopener">Open the GitHub repo ↗</a>
          </div>
          <div class="mono sub" style="margin-top:10px">${REPO_URL.replace('https://','')}</div>
          <h3 style="margin-top:20px">Creators</h3>
          <ul class="custody" style="gap:7px">
            <li>Maxim Dnestreanschii — backend &amp; deployment</li>
            <li>Gabriel Creanga — UI/UX developer</li>
            <li>Vlad Garbuz — legal expert</li>
            <li>Chirill Donos — NLP Engineer &amp; Team Lead</li>
          </ul>
        </div>
      </div>
      <div class="card" style="margin-top:16px">
        <h3>Scope &amp; honesty</h3>
        <ul class="custody" style="gap:7px">
          <li>${HOSTED
            ? 'This is a <b>hosted demo</b>: your text is sent to a serverless function (Vercel) to be privatized — processed in memory, not stored in any database, but it does leave your device. The <b>desktop app</b> runs the identical editor fully on-device with 0 bytes of egress.'
            : 'On-device only — the editor runs on this machine over loopback; 0 bytes of egress, raw text stays local.'}</li>
          <li>The holistic editor is the primary method; the legacy L0–L3 tiered dial lives in the library for reproducibility.</li>
          <li>Privacy is measured against an authorship attacker; identifier redaction is strong, stylometric anonymity is bounded — stated, not overclaimed.</li>
        </ul>
      </div>
      <div class="note" style="margin-top:18px">AgnoSpeech 0.9 · ${HOSTED ? 'hosted demo' : 'on-device'} · holistic backend</div>`;
  },
};

// ---- boot -------------------------------------------------------------------
function boot() {
  applyTheme(state.theme);
  const ring = $('#device-ring');
  if (ring && HOSTED) ring.textContent = '● hosted demo · processed on the server, not stored';
  render();
}
boot();
