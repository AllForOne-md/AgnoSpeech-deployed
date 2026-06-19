/* AgnoSpeech Local Privatization Workbench — frontend.

   Two halves live here:

   1. A four-step *workflow demo* — Source → Privatize → Harm check → Release —
      ported from the source design. It runs on baked-in mock data (the MSGS /
      HARM arrays below) with a faked on-device processing animation; nothing in
      these four steps touches the network. This mirrors how the original design
      mockup behaves.

   2. A real *Live editor* tab — type/paste text and watch it get privatized for
      real by the agnospeech holistic editor behind POST /api/edit. This is the
      only tab that calls the backend.

   No build step: this file renders the whole window into #app via template
   strings and re-wires events after each render, exactly like the rest of the
   static frontend. */

// ---- themes (vars set inline on the root container per render) --------------
const THEMES = {
  clinical: {'bg':'#dde3ea','win':'#ffffff','panel':'#ffffff','panel2':'#f6f8fa','inset':'#eef2f6','fg':'#0e1a26','fg2':'#2c3c4a','muted':'#5d6b78','faint':'#93a0ab','border':'#e4e9ee','border-strong':'#cfd8e0','accent':'#0e7c8b','accent-fg':'#ffffff','accent-soft':'#e1f1f3','titlebar':'#f0f3f6','sidebar':'#f6f8fa','sidebar-active':'#e1f1f3','l1':'#9a6700','l1-bg':'#fbf0d6','l2':'#0e7c8b','l2-bg':'#def0f2','l3':'#6b46c1','l3-bg':'#ece6fa','safe':'#1f7a4d','safe-bg':'#e3f3ea','warn':'#9a6700','warn-bg':'#fbf0d6','danger':'#b23b27','danger-bg':'#f8e6e1','shadow':'rgba(20,40,60,0.22)'},
  forensic: {'bg':'#06090d','win':'#0d1219','panel':'#11171f','panel2':'#0e141b','inset':'#0a0f15','fg':'#e7eef4','fg2':'#c4cfd9','muted':'#8696a4','faint':'#586675','border':'#202a36','border-strong':'#2c3a48','accent':'#2bb6c4','accent-fg':'#03161a','accent-soft':'#0d2b30','titlebar':'#10161e','sidebar':'#0c1117','sidebar-active':'#0d2b30','l1':'#e0b057','l1-bg':'#2c2310','l2':'#2bb6c4','l2-bg':'#0d2b30','l3':'#b69cf0','l3-bg':'#211a36','safe':'#4fc285','safe-bg':'#0e2a1c','warn':'#e0b057','warn-bg':'#2c2310','danger':'#e07a63','danger-bg':'#2e150f','shadow':'rgba(0,0,0,0.6)'},
  paper: {'bg':'#d9d2c6','win':'#fbf9f5','panel':'#fbf9f5','panel2':'#f3efe7','inset':'#ece7dc','fg':'#211c14','fg2':'#3d362b','muted':'#6f6557','faint':'#a59a89','border':'#e7e0d3','border-strong':'#d6cdbc','accent':'#3B2070','accent-fg':'#ffffff','accent-soft':'#eee7fa','titlebar':'#f1ece2','sidebar':'#f3efe7','sidebar-active':'#e9e2f4','l1':'#8a5a12','l1-bg':'#f4e7cf','l2':'#0f7a6e','l2-bg':'#cfe8de','l3':'#6a4aa8','l3-bg':'#e9e2f4','safe':'#2c7a4f','safe-bg':'#e1efe6','warn':'#8a5a12','warn-bg':'#f4e7cf','danger':'#a8432c','danger-bg':'#f3e2dc','shadow':'rgba(80,60,30,0.20)','brand':'#3B2070','brand-deep':'#231243','lilac':'#B49BE0','paper-brand':'#F7F5FB'},
};

const REPO_URL = "https://github.com/AllForOne-md/AgnoSpeech";
const ASSETS = {
  mark: '/static/assets/agnospeech-mark.svg',
  markReversed: '/static/assets/agnospeech-mark-reversed.svg',
  logoReversed: '/static/assets/agnospeech-logo-horizontal-reversed.png',
  redactionBanner: '/static/assets/agnospeech-banner-redaction.png',
};

// Honesty: the on-device / 0-egress claims only hold for the desktop app
// (loopback). A hosted (Vercel) deployment sends the Live-editor text to a
// serverless function to privatize it.
const HOSTED = !['localhost', '127.0.0.1', '0.0.0.0', ''].includes(location.hostname);
const PRIV_NOTE = HOSTED ? 'sent to the server to privatize · not stored' : 'never leaves this machine';

// ---- baked-in mock data for the workflow demo (Source/Privatize/Harm) -------
const MSGS = [
  { code:'MSG-0481', tag:'threat of exposure', note:'2 identifiers removed · author handle and style neutralized · coercive-threat content preserved for the detector.',
    raw:[["Maria","id"],[" reported a message she received. The sender ","p"],["@coldwolf99","st"],[" wrote: “","p"],["you’ll regret ignoring me — everyone will see what you really are","hm"],[".” Her friend ","p"],["Tomás","id"],[" saw it too.","p"]],
    priv:[["[REPORTER]","idr"],[" reported a message she received. The sender, ","p"],["[author]","str"],[", sent ","p"],["a threat that she would regret ignoring him and that people would be shown “what she really is.”","hm"],[" A ","p"],["[bystander]","idr"],[" also saw it.","p"]] },
  { code:'MSG-1207', tag:'persistent contact', note:'1 identifier removed · venue and day generalized · stalking pattern preserved.',
    raw:[["Aisha","id"],[" reported that ","p"],["@nightcaller","st"],[" keeps messaging from new accounts: “","p"],["I know you walk past the Lyric Café every Thursday","hm"],[".” She had blocked him five times.","p"]],
    priv:[["[REPORTER]","idr"],[" reported that ","p"],["[author]","str"],[" repeatedly messaged from new accounts. The message ","p"],["referenced knowing her regular weekly route and a specific local venue","hm"],[". She had blocked the sender multiple times.","p"]] },
  { code:'MSG-3398', tag:'image-based coercion', note:'1 identifier removed · author style neutralized · coercion content preserved verbatim in meaning.',
    raw:[["Priya","id"],[" reported a message: “","p"],["send another photo or I’ll post the ones I already have","hm"],[".” ","p"],["@__real_max_","st"],[" was his third account.","p"]],
    priv:[["[REPORTER]","idr"],[" reported a coercive threat: ","p"],["the sender demanded additional images and threatened to publish existing ones","hm"],[". The account was ","p"],["[author]’s","str"],[" third.","p"]] },
];

const HARM = {
  raw:[["Lena","id"],[" reported: he called me ","p"],["an [ethnic-slur]","hm"],[" and said “","p"],["women like you don’t belong in this country","hm"],[".” It happened on the bus.","p"]],
  bad:[["“","p"],["[ethnic-slur]","hm"],["” … “","p"],["women like you don’t belong in this country","hm"],[".”","p"]],
  fixed:[["[REPORTER]","idr"],[" reported being targeted: an ","p"],["ethnic slur","hm"],[" was directed at her, and she was told that ","p"],["“women like her don’t belong in this country.”","hm"],[" The slur and statement were said TO her, not by her.","p"]],
};

// ---- state ------------------------------------------------------------------
const LIVE_EXAMPLES = [
  {
    id: 'sample-01',
    title: 'Persistent contact',
    tag: 'phone + address',
    text: "Honestly, Marcus keeps texting me from 555-0142 saying he'll show up at my flat on Rue Lavoisier. Reach me at anca.dragan@mail.com.",
  },
  {
    id: 'sample-02',
    title: 'Image coercion',
    tag: 'handle + threat',
    text: "Priya said @realmax_ sent: send another photo tonight or I will post the ones I already have. He also named her college group chat.",
  },
  {
    id: 'sample-03',
    title: 'Doxxing warning',
    tag: 'email + workplace',
    text: "The sender wrote to Elena at elena.matei@clinic.org: everyone at Northgate Clinic will know where you live by Friday.",
  },
  {
    id: 'sample-04',
    title: 'Route stalking',
    tag: 'routine + place',
    text: "Aisha reported that @nightcaller keeps messaging from new accounts: I know you walk past the Lyric Cafe every Thursday after 8.",
  },
  {
    id: 'sample-05',
    title: 'Identity harassment',
    tag: 'protected class',
    text: "Lena reported being called a slur and told that women like her do not belong in this country during the 42 bus ride home.",
  },
  {
    id: 'sample-06',
    title: 'Workplace intimidation',
    tag: 'name + role',
    text: "Dorin said his manager Victor left a voicemail: if you complain again, I will make sure nobody in the Bucharest office hires you.",
  },
];

const state = {
  theme: 'paper',
  step: 'source',            // source | privatize | harm | release | live
  // workflow demo (mock)
  processing: false,
  processDone: false,
  procStage: 0,
  selMsg: 0,
  l1: true, l2: true, l3: true,
  harmResolved: false,
  released: false,
  pickNotice: false,
  fileName: 'helpline_reports_2019-2025.csv',
  sourceFormat: 'csv',
  sourceFileText: null,
  sourceFileSize: 0,
  sourceUploaded: false,
  // live editor (real backend)
  privacy: 0.65, utility: 0.72, context: 1,
  liveExample: 0,
  liveText: LIVE_EXAMPLES[0].text,
  liveOut: null,
  liveBusy: false,
};

// live-editor sliders — these genuinely change the backend output.
const SLIDERS = [
  {k:'privacy', label:'Privacy strength', min:0.3, max:0.95, step:0.01, fmt:v=>(+v).toFixed(2),
   desc:'How hard the editor drops author-identifying / risky tokens. ↑ more scrubbed, less readable.'},
  {k:'utility', label:'Utility strength', min:0.3, max:0.95, step:0.01, fmt:v=>(+v).toFixed(2),
   desc:'How much harm / task evidence is kept for the detector. ↑ retains more signal.'},
  {k:'context', label:'Context window', min:0, max:3, step:1, fmt:v=>`${v} word${(+v)==1?'':'s'}`,
   desc:'Neighbouring words kept around each retained term, for readability.'},
];

const SOURCE_FORMATS = [
  { k: 'csv', label: 'CSV', file: 'helpline_reports_2019-2025.csv', meta: 'comma-separated table' },
  { k: 'json', label: 'JSON', file: 'helpline_reports_2019-2025.json', meta: 'array of message objects' },
  { k: 'jsonl', label: 'JSONL', file: 'helpline_reports_2019-2025.jsonl', meta: 'one message per line' },
];

// ---- helpers ----------------------------------------------------------------
const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const phHi = s => esc(s).replace(/\[[A-Z_]+\]/g, m => `<span class="ph">${m}</span>`);

// Mark, on the RAW input, every word the editor changed/removed — words not
// present in the privatized output.
function markRaw(raw, edited) {
  if (!edited) return esc(raw);
  const kept = new Set((String(edited).toLowerCase().match(/[a-z0-9']+/g) || []));
  return esc(raw).replace(/[A-Za-z0-9']+/g, w => kept.has(w.toLowerCase()) ? w : `<span class="changed">${w}</span>`);
}
function countChanged(raw, edited) {
  const kept = new Set((String(edited).toLowerCase().match(/[a-z0-9']+/g) || []));
  return (raw.match(/[A-Za-z0-9']+/g) || []).filter(w => !kept.has(w.toLowerCase())).length;
}

// span styling for the mock before/after diff, honouring the L1/L2/L3 toggles.
function spanStyle(type, L) {
  const base = 'border-radius:3px;padding:0 2px;white-space:pre-wrap;';
  if ((type === 'id' || type === 'idr') && L.l1) return 'background:var(--l1-bg);color:var(--l1);box-shadow:inset 0 -2px 0 var(--l1),0 0 0 1px rgba(138,90,18,.20);font-weight:500;' + base;
  if (type === 'hm' && L.l2) return 'background:var(--l2-bg);color:var(--l2);box-shadow:inset 0 -2px 0 var(--l2),0 0 0 1px rgba(15,122,110,.18);font-weight:500;' + base;
  if ((type === 'st' || type === 'str') && L.l3) return 'background:var(--l3-bg);color:var(--l3);box-shadow:inset 0 -2px 0 var(--l3),0 0 0 1px rgba(106,74,168,.20);font-weight:500;' + base;
  return 'color:inherit;white-space:pre-wrap;';
}
function styleSpans(spans, L) {
  return (spans || []).map(s => `<span style="${spanStyle(s[1], L)}">${esc(s[0])}</span>`).join('');
}

function themeVars() {
  const t = THEMES[state.theme] || THEMES.paper;
  return Object.keys(t).map(k => `--${k}:${t[k]}`).join(';') + ';';
}

function set(partial) { Object.assign(state, partial); render(); }

async function api(path, body) {
  const opt = body ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {};
  const res = await fetch(path, opt);
  return res.json();
}

// ---- workflow demo actions (mock) -------------------------------------------
let timers = [];
function go(key) {
  if (key === 'source' || key === 'live') return set({ step: key });
  if (!state.processDone) return;            // 02–04 locked until the demo run finishes
  set({ step: key });
}

function run() {
  if (state.processing) return;
  Object.assign(state, { step:'privatize', processing:true, processDone:false, procStage:0 });
  render();
  timers.forEach(clearTimeout); timers = [];
  timers.push(setTimeout(() => set({ procStage:1 }), 500));
  timers.push(setTimeout(() => set({ procStage:2 }), 1500));
  timers.push(setTimeout(() => set({ procStage:3 }), 2500));
  timers.push(setTimeout(() => set({ processing:false, processDone:true }), 3400));
}

let pickTimer = null;
function pickDisabled() {
  set({ pickNotice: true });
  clearTimeout(pickTimer);
  pickTimer = setTimeout(() => set({ pickNotice:false }), 2600);
}

async function uploadSourceFile(file) {
  if (!file) return;
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  const fmt = SOURCE_FORMATS.find(f => f.k === ext) || SOURCE_FORMATS[0];
  const text = await file.text();
  set({
    fileName: file.name,
    sourceFormat: fmt.k,
    sourceFileText: text,
    sourceFileSize: file.size,
    sourceUploaded: true,
    pickNotice: false,
  });
}

function sourceAccept() {
  if (state.sourceFormat === 'json') return '.json,application/json';
  if (state.sourceFormat === 'jsonl') return '.jsonl,application/jsonl,.ndjson';
  return '.csv,text/csv';
}

function fmtBytes(n) {
  if (!n) return 'no file chosen yet';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function stState(n) {
  if (state.processDone) return 'done';
  const s = state.procStage;
  if (s > n) return 'done';
  if (s === n) return 'active';
  return 'idle';
}
function mkStage(n) {
  const st = stState(n);
  const base = "width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font:700 13px 'IBM Plex Mono',monospace;flex:none;";
  if (st === 'done')   return { dot: base+'background:var(--safe);color:#fff;', glyph:'✓', txt:'var(--safe)', status:'done' };
  if (st === 'active') return { dot: base+'background:var(--accent);color:var(--accent-fg);animation:agpulse 1s ease-in-out infinite;', glyph:String(n), txt:'var(--accent)', status:'running…' };
  return { dot: base+'background:transparent;border:1.5px solid var(--border-strong);color:var(--faint);', glyph:String(n), txt:'var(--faint)', status:'queued' };
}

function chip(on, kind) {
  const c = on
    ? `background:var(--${kind}-bg);color:var(--${kind});border:1px solid var(--${kind});`
    : 'background:transparent;color:var(--muted);border:1px solid var(--border);';
  return "display:inline-flex;align-items:center;gap:7px;padding:6px 11px;border-radius:999px;font:600 11.5px 'IBM Plex Mono',monospace;cursor:pointer;user-select:none;" + c;
}
function dot(on, kind) { return `width:8px;height:8px;border-radius:50%;background:${on?`var(--${kind})`:'var(--faint)'};`; }

// ---- live editor actions (real backend) -------------------------------------
let liveTimer = null;
function scheduleLive() { clearTimeout(liveTimer); liveTimer = setTimeout(runLive, 300); }

async function runLive() {
  if (!state.liveText.trim()) {
    state.liveOut = null;
    const out = $('#liveOut'); if (out) out.innerHTML = '<span style="color:var(--faint);">Privatized text appears here.</span>';
    const marked = $('#liveMarked'); if (marked) marked.innerHTML = '';
    const st = $('#liveStats'); if (st) st.innerHTML = '';
    return;
  }
  state.liveBusy = true;
  const out = $('#liveOut'); if (out) out.innerHTML = '<span class="spin"></span> privatizing…';
  const r = await api('/api/edit', {
    text: state.liveText,
    privacy_strength: state.privacy, utility_strength: state.utility, context_window: state.context,
  });
  state.liveBusy = false;
  if (r.error) { if (out) out.textContent = 'Error: ' + r.error; return; }
  state.liveOut = r;
  patchLive();
}

// Patch the live panes in place so slider changes do not redraw the whole tab.
function patchLive() {
  const r = state.liveOut; if (!r) return;
  const out = $('#liveOut'); if (out) out.innerHTML = phHi(r.edited);
  const marked = $('#liveMarked'); if (marked) marked.innerHTML = markRaw(state.liveText, r.edited);
  const st = $('#liveStats');
  if (st) st.innerHTML =
    `<span style="${statChip('danger')}">${countChanged(state.liveText, r.edited)} words changed</span>
     <span style="${statChip('l1')}">${r.identifiers} identifiers</span>
     <span style="${statChip('l2')}">${r.chars_in}→${r.chars_out} chars</span>`;
}
function statChip(kind) {
  return `font:600 11px 'IBM Plex Mono',monospace;padding:3px 8px;border-radius:5px;background:var(--${kind}-bg);color:var(--${kind});`;
}

// ============================================================================
//  RENDER
// ============================================================================
function render() {
  const root = document.getElementById('app');
  root.innerHTML = `
    <div style="${themeVars()}min-height:100vh;width:100%;background:radial-gradient(circle at 92% 8%,rgba(180,155,224,.22),transparent 30%),radial-gradient(circle at 7% 94%,rgba(59,32,112,.08),transparent 36%),linear-gradient(135deg,var(--bg),#eee8dc 100%);display:flex;align-items:stretch;justify-content:stretch;font-family:'Public Sans',sans-serif;">
      <div style="width:100%;height:100vh;background:var(--win);display:flex;flex-direction:column;overflow:hidden;position:relative;">
        ${titlebar()}
        <div style="flex:1;display:flex;overflow:hidden;">
          ${sidebar()}
          <div style="flex:1;overflow:auto;background:radial-gradient(circle at 92% 10%,rgba(180,155,224,.20),transparent 30%),radial-gradient(circle at 20% 92%,rgba(59,32,112,.045),transparent 34%),linear-gradient(135deg,rgba(251,249,245,.92),rgba(243,239,231,.96)),var(--panel2);padding:20px 26px;position:relative;">
            <div style="position:absolute;right:-80px;top:-110px;width:330px;height:330px;background:url('${ASSETS.mark}') center/contain no-repeat;opacity:.055;pointer-events:none;"></div>
            <div style="position:relative;z-index:1;">${VIEWS[state.step] ? VIEWS[state.step]() : VIEWS.source()}</div>
          </div>
        </div>
        ${statusbar()}
      </div>
    </div>`;
  wire();
  if (state.step === 'live') runLive();
}

function titlebar() {
  return `
    <div style="height:58px;flex:none;display:flex;align-items:center;gap:18px;padding:0 24px;background:linear-gradient(90deg,#f7f2e9,var(--titlebar) 44%,rgba(180,155,224,.30));border-bottom:1px solid var(--border);color:var(--fg);box-shadow:inset 0 -1px 0 rgba(59,32,112,.07);">
      <div style="display:flex;gap:12px;align-items:center;flex:none;min-width:250px;">
        <span style="width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,rgba(59,32,112,.18),rgba(180,155,224,.20) 48%,rgba(224,239,234,.78));display:flex;align-items:center;justify-content:center;border:1px solid rgba(59,32,112,.14);box-shadow:0 8px 18px rgba(59,32,112,.08);">
          <img src="${ASSETS.mark}" alt="AgnoSpeech logo" style="width:28px;height:28px;display:block;">
        </span>
        <div>
          <div class="brand-title" style="font-size:20px;line-height:1;">AgnoSpeech</div>
          <div style="font:600 8.5px/1.2 'JetBrains Mono','IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--faint);text-transform:uppercase;margin-top:4px;">it judges words, never people</div>
        </div>
      </div>
      <div style="flex:1;"></div>
      <div style="flex:none;display:flex;align-items:center;gap:8px;min-width:250px;justify-content:flex-end;">
        <span style="font:600 10px 'JetBrains Mono','IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--l2);background:var(--l2-bg);padding:6px 9px;border-radius:999px;border:1px solid rgba(15,122,110,.12);">LOCAL</span>
        <span style="width:7px;height:7px;border-radius:50%;background:var(--safe);box-shadow:0 0 0 5px rgba(44,122,79,.12);"></span>
      </div>
    </div>`;
}

function navWorkflow(key, num, label, badge) {
  const active = state.step === key;
  const locked = key !== 'source' && !state.processDone;
  const bg = active ? 'linear-gradient(90deg,var(--sidebar-active),rgba(251,249,245,.72))' : 'transparent';
  const fg = active ? 'var(--accent)' : (locked ? 'var(--faint)' : 'var(--fg2)');
  const op = locked ? '0.5' : '1';
  const bar = active ? 'var(--accent)' : 'transparent';
  const weight = active ? '600' : '500';
  const cursor = locked ? 'not-allowed' : 'pointer';
  const border = active ? '1px solid rgba(59,32,112,.12)' : '1px solid transparent';
  const shadow = active ? 'box-shadow:0 8px 18px rgba(59,32,112,.06);' : '';
  const badgeHtml = badge
    ? `<span style="margin-left:auto;font:600 10px 'IBM Plex Mono',monospace;background:var(--warn-bg);color:var(--warn);padding:2px 6px;border-radius:5px;">${badge}</span>`
    : '';
  return `
    <button data-go="${key}" style="position:relative;display:flex;align-items:center;gap:11px;width:100%;text-align:left;border:${border};background:${bg};color:${fg};opacity:${op};font:${weight} 13.5px 'Public Sans',sans-serif;padding:11px 14px 11px 16px;border-radius:9px;cursor:${cursor};${shadow}">
      <span style="position:absolute;left:0;top:9px;bottom:9px;width:3px;border-radius:2px;background:${bar};"></span>
      <span style="font:600 10px 'IBM Plex Mono',monospace;color:var(--faint);width:14px;">${num}</span>${label}${badgeHtml}
    </button>`;
}

function navLive() {
  const active = state.step === 'live';
  const bg = active ? 'linear-gradient(90deg,var(--sidebar-active),rgba(251,249,245,.72))' : 'transparent';
  const fg = active ? 'var(--accent)' : 'var(--fg2)';
  const bar = active ? 'var(--accent)' : 'transparent';
  const weight = active ? '600' : '500';
  const border = active ? '1px solid rgba(59,32,112,.12)' : '1px solid transparent';
  return `
    <button data-go="live" style="position:relative;display:flex;align-items:center;gap:11px;width:100%;text-align:left;border:${border};background:${bg};color:${fg};font:${weight} 13.5px 'Public Sans',sans-serif;padding:11px 14px 11px 16px;border-radius:9px;cursor:pointer;">
      <span style="position:absolute;left:0;top:9px;bottom:9px;width:3px;border-radius:2px;background:${bar};"></span>
      <span style="font:600 11px 'IBM Plex Mono',monospace;color:var(--faint);width:14px;">✎</span>Live editor
      <span style="margin-left:auto;font:600 9px 'IBM Plex Mono',monospace;background:var(--accent-soft);color:var(--accent);padding:2px 6px;border-radius:5px;">LIVE</span>
    </button>`;
}

function sidebar() {
  const lockNote = !state.processDone
    ? `<div style="margin:10px 6px 0;padding:11px 12px;border:1px dashed var(--border-strong);border-radius:8px;font:400 11px/1.5 'Public Sans',sans-serif;color:var(--muted);">Run privatization to unlock the rest of the workflow.</div>`
    : '';
  return `
    <div style="width:252px;flex:none;background:linear-gradient(180deg,rgba(180,155,224,.12),transparent 36%),var(--sidebar);border-right:1px solid var(--border);padding:18px 16px;display:flex;flex-direction:column;gap:3px;overflow:auto;">
      <div style="position:relative;overflow:hidden;margin-bottom:12px;border-radius:11px;background:linear-gradient(135deg,rgba(224,239,234,.92),rgba(251,249,245,.92) 52%,rgba(180,155,224,.26));padding:14px 14px;border:1px solid rgba(106,74,168,.16);box-shadow:0 12px 28px rgba(59,32,112,.08);">
        <img src="${ASSETS.mark}" alt="" style="position:absolute;right:-18px;bottom:-25px;width:106px;height:106px;opacity:.10;">
        <div style="position:relative;font:600 10px 'JetBrains Mono','IBM Plex Mono',monospace;letter-spacing:.14em;color:var(--accent);text-transform:uppercase;margin-bottom:8px;">Privacy-first AI</div>
        <div style="position:relative;font:600 14px/1.25 'Public Sans',sans-serif;color:var(--fg);max-width:170px;">Desktop moderation workbench</div>
        <div style="position:relative;margin-top:10px;width:78px;height:3px;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--lilac));opacity:.75;"></div>
      </div>
      <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.16em;color:var(--faint);padding:4px 14px 10px;">WORKFLOW</div>
      ${navWorkflow('source',   '01', 'Source')}
      ${navWorkflow('privatize','02', 'Privatize')}
      ${navWorkflow('harm',     '03', 'Harm check', (state.processDone && !state.harmResolved) ? '1' : '')}
      ${navWorkflow('release',  '04', 'Release')}
      ${lockNote}

      <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.16em;color:var(--faint);padding:18px 14px 8px;">TOOLS</div>
      ${navLive()}

      <div style="margin-top:auto;padding:13px 12px;border:1px solid rgba(106,74,168,.14);border-radius:12px;background:linear-gradient(135deg,rgba(180,155,224,.20),rgba(255,253,248,.86));">
        <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.1em;color:var(--faint);margin-bottom:8px;">THIS DEVICE</div>
        <div style="font:600 12.5px 'Public Sans',sans-serif;color:var(--fg);">Anca’s MacBook</div>
      </div>
    </div>`;
}

function statusbar() {
  return `
    <div style="height:28px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 18px;background:linear-gradient(90deg,var(--titlebar),rgba(233,226,244,.52));border-top:1px solid var(--border);font:500 11px 'JetBrains Mono','IBM Plex Mono',monospace;color:var(--muted);">
      <span style="display:flex;align-items:center;gap:8px;"><span style="width:8px;height:8px;border-radius:50%;background:var(--safe);box-shadow:0 0 0 4px rgba(44,122,79,.12);"></span>Offline · egress 0 B</span>
      <span>${esc(state.fileName)}</span>
      <span style="color:var(--accent);">AgnoSpeech 0.9 · on-device only</span>
    </div>`;
}

// ---- views ------------------------------------------------------------------
const VIEWS = {
  // ===================== SOURCE =====================
  source() {
    const preview = MSGS.slice(0, 3).map(m => `
      <div style="border:1px solid var(--border);border-radius:9px;background:var(--panel2);padding:9px 12px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
          <span style="font:600 10.5px 'IBM Plex Mono',monospace;color:var(--faint);">${m.code}</span>
          <span style="font:600 10.5px 'IBM Plex Mono',monospace;color:var(--muted);">${m.tag}</span>
        </div>
        <div style="font:400 12.5px/1.48 'IBM Plex Mono',monospace;color:var(--fg2);">${styleSpans(m.raw, {l1:true,l2:true,l3:true})}</div>
      </div>`).join('');
    const pickNotice = state.pickNotice
      ? `<span style="font:500 10.5px 'IBM Plex Mono',monospace;color:var(--faint);max-width:170px;text-align:right;">File picking is disabled in this demo.</span>`
      : '';
    const selectedFormat = SOURCE_FORMATS.find(f => f.k === state.sourceFormat) || SOURCE_FORMATS[0];
    const loadedBadge = state.sourceUploaded
      ? `<span style="font:600 9.5px 'IBM Plex Mono',monospace;background:var(--safe-bg);color:var(--safe);padding:2px 7px;border-radius:5px;">LOADED</span>`
      : `<span style="font:600 9.5px 'IBM Plex Mono',monospace;background:var(--l3-bg);color:var(--l3);padding:2px 7px;border-radius:5px;">${selectedFormat.label} DEFAULT</span>`;
    const fileMeta = state.sourceUploaded
      ? `${fmtBytes(state.sourceFileSize)} · loaded from your computer · local only`
      : `${selectedFormat.meta} · demo preview: 20 messages · choose a local file`;
    const planSliders = SLIDERS.map(s => `
      <div>
        <label style="font:600 12px 'Public Sans',sans-serif;color:var(--fg);display:flex;justify-content:space-between;gap:12px;">${s.label}
          <b id="${s.k}v" style="color:var(--accent);font:600 12.5px 'IBM Plex Mono',monospace;">${s.fmt(state[s.k])}</b></label>
        <input id="${s.k}" type="range" min="${s.min}" max="${s.max}" step="${s.step}" value="${state[s.k]}" style="margin-top:5px;">
      </div>`).join('');
    return `
      <div>
        <div style="margin-bottom:12px;">
          <div style="font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.14em;color:var(--accent);margin-bottom:7px;">STEP 01 · SOURCE</div>
          <div style="font:700 21px/1.1 'Public Sans',sans-serif;color:var(--fg);">Source corpus</div>
          <div style="font:400 13px/1.45 'Public Sans',sans-serif;color:var(--muted);margin-top:5px;max-width:720px;">Load a corpus to privatize. Files are read on this device only — nothing is transmitted.</div>
        </div>

        <div class="soft-glass" style="border:1.5px dashed var(--accent);border-radius:12px;background:rgba(238,231,250,.72);padding:12px 14px;margin-bottom:12px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:10px;">
            <div style="font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.1em;color:var(--accent);">CHOOSE SOURCE FORMAT</div>
            <div style="display:flex;gap:7px;align-items:center;">${SOURCE_FORMATS.map(formatChip).join('')}</div>
          </div>
          <div style="display:grid;grid-template-columns:38px minmax(360px,1fr) minmax(280px,340px);align-items:center;gap:14px;">
            <div style="width:38px;height:46px;flex:none;border-radius:6px;background:var(--panel);border:1px solid var(--accent);display:flex;align-items:flex-end;justify-content:center;padding-bottom:6px;">
              <span style="font:600 9px 'IBM Plex Mono',monospace;color:var(--accent);">${selectedFormat.label}</span>
            </div>
            <div style="flex:1;min-width:0;">
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="width:18px;height:18px;border-radius:50%;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font:700 11px 'Public Sans';flex:none;">1</span>
                <span style="font:600 15px 'Public Sans',sans-serif;color:var(--fg);">${esc(state.fileName)}</span>
                ${loadedBadge}
              </div>
              <div style="font:500 11.5px 'IBM Plex Mono',monospace;color:var(--muted);margin-top:4px;">${fileMeta}</div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;min-width:0;">
              <button data-pick style="border:none;background:var(--accent);cursor:pointer;padding:15px 24px;border-radius:12px;font:700 14px 'Public Sans',sans-serif;color:var(--accent-fg);box-shadow:0 13px 28px rgba(59,32,112,.20);display:flex;align-items:center;justify-content:center;gap:10px;white-space:nowrap;width:260px;">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" style="flex:none;"><path d="M12 15V4M12 4l-4 4M12 4l4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><path d="M5 16v3a1 1 0 001 1h12a1 1 0 001-1v-3" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>
                Choose ${selectedFormat.label} file
              </button>
              <input id="sourceFile" type="file" accept="${sourceAccept()}" hidden>
              ${pickNotice}
            </div>
          </div>
          <div style="margin-top:9px;padding-top:8px;border-top:1px dashed var(--border-strong);display:flex;align-items:center;gap:8px;font:500 10.5px 'IBM Plex Mono',monospace;color:var(--muted);">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" style="flex:none;"><path d="M12 16V4M12 4l-5 5M12 4l5 5" stroke="var(--muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><path d="M4 17v2a1 1 0 001 1h14a1 1 0 001-1v-2" stroke="var(--muted)" stroke-width="2" stroke-linecap="round"></path></svg>
            Drag a ${selectedFormat.label} corpus here or browse — raw files are read on this device only and never transmitted.
          </div>
        </div>

        <div style="display:grid;grid-template-columns:minmax(0,1.45fr) minmax(360px,1fr);gap:16px;align-items:stretch;">
          <div class="soft-glass" style="height:100%;background:rgba(251,249,245,.76);border:1px solid var(--border);border-radius:12px;padding:14px 16px;min-width:0;display:flex;flex-direction:column;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:9px;">
              <div style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);">Raw messages — sample</div>
              <div style="font:500 11px 'IBM Plex Mono',monospace;color:var(--faint);">3 of 20</div>
            </div>
            <div style="display:flex;flex-direction:column;gap:8px;">${preview}</div>
            <div style="font:400 11.5px/1.4 'Public Sans',sans-serif;color:var(--muted);margin-top:auto;padding-top:10px;">Each record contains direct identifiers, sender handles, and stylometric traces. These are removed before any data leaves this device.</div>
          </div>

          <div class="soft-glass" style="height:100%;background:rgba(251,249,245,.76);border:1px solid var(--border);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;min-width:0;">
            <div style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);margin-bottom:10px;">Privatization plan</div>
            <div style="display:flex;flex-direction:column;gap:9px;">
              ${planRow('l1','L1 · Strip direct identifiers','Names of the victims who reported and of the bystanders they quoted.')}
              ${planRow('l2','L2 · Preserve harm content','Keep the escalation signal a triage detector needs to learn from.')}
              ${planRow('l3','L3 · Neutralize author style','Scrub idiolect so released text can’t be traced back to the sender.')}
            </div>
            <div style="margin-top:12px;padding-top:11px;border-top:1px solid var(--border);">
              <div style="display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:9px;">
                <div style="font:600 12.5px 'Public Sans',sans-serif;color:var(--fg);">Editor settings</div>
                <div style="font:600 9.5px 'IBM Plex Mono',monospace;color:var(--faint);letter-spacing:.08em;">SHARED WITH LIVE EDITOR</div>
              </div>
              <div style="display:flex;flex-direction:column;gap:10px;">${planSliders}</div>
            </div>
            <button data-run style="margin-top:12px;width:100%;border:none;cursor:pointer;background:var(--accent);color:var(--accent-fg);font:600 14px 'Public Sans',sans-serif;padding:11px;border-radius:10px;">Run privatization &nbsp;→</button>
            <div style="text-align:center;font:500 10.5px 'IBM Plex Mono',monospace;color:var(--faint);margin-top:7px;">Runs entirely on this device · no network</div>
          </div>
        </div>
      </div>`;
  },

  // ===================== PRIVATIZE =====================
  privatize() {
    const head = `
      <div style="margin-bottom:20px;">
        <div style="font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.14em;color:var(--accent);margin-bottom:7px;">STEP 02 · PRIVATIZE</div>
        <div style="font:700 23px/1.1 'Public Sans',sans-serif;color:var(--fg);">Privatization — before / after</div>
      </div>`;

    if (state.processing) {
      const s1 = mkStage(1), s2 = mkStage(2), s3 = mkStage(3);
      const stageRow = (s, title, sub) => `
        <div style="display:flex;align-items:center;gap:14px;padding:14px 16px;border:1px solid var(--border);border-radius:11px;background:var(--panel);">
          <div style="${s.dot}">${s.glyph}</div>
          <div style="flex:1;"><div style="font:600 13.5px 'Public Sans',sans-serif;color:var(--fg);">${title}</div><div style="font:400 12px 'Public Sans',sans-serif;color:var(--muted);">${sub}</div></div>
          <div style="font:600 11px 'IBM Plex Mono',monospace;color:${s.txt};">${s.status}</div>
        </div>`;
      return `${head}
        <div style="max-width:560px;margin:40px auto;">
          <div style="text-align:center;font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.14em;color:var(--accent);margin-bottom:20px;">PROCESSING · ON DEVICE</div>
          <div style="display:flex;flex-direction:column;gap:11px;">
            ${stageRow(s1,'L1 · Strip direct identifiers','Reporters and quoted bystanders')}
            ${stageRow(s2,'L2 · Preserve harm content','Escalation signal for the detector')}
            ${stageRow(s3,'L3 · Neutralize author style','Stylometric scrub against authorship attack')}
          </div>
          <div style="position:relative;height:6px;border-radius:3px;background:var(--inset);overflow:hidden;margin-top:22px;">
            <div style="position:absolute;top:0;bottom:0;width:30%;background:var(--accent);border-radius:3px;animation:agscan 1.1s linear infinite;"></div>
          </div>
          <div style="text-align:center;font:500 11px 'IBM Plex Mono',monospace;color:var(--faint);margin-top:13px;">0 bytes transmitted · raw text never leaves this device</div>
        </div>`;
    }

    if (!state.processDone) {
      return `${head}<div style="font:400 14px 'Public Sans';color:var(--muted);">Run privatization from the Source step first.</div>`;
    }

    const L = { l1: state.l1, l2: state.l2, l3: state.l3 };
    const cur = MSGS[state.selMsg] || MSGS[0];
    const msgList = MSGS.map((m, i) => {
      const active = i === state.selMsg;
      const style = 'display:block;width:100%;text-align:left;border-radius:9px;padding:11px 13px;cursor:pointer;'
        + (active ? 'border:1px solid var(--accent);background:var(--accent-soft);' : 'border:1px solid var(--border);background:var(--panel);');
      const codeColor = active ? 'var(--accent)' : 'var(--muted)';
      return `
        <button data-msg="${i}" style="${style}">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font:600 11px 'IBM Plex Mono',monospace;color:${codeColor};">${m.code}</span>
            <span style="font:500 10px 'IBM Plex Mono',monospace;color:var(--faint);">${m.tag}</span>
          </div>
        </button>`;
    }).join('');

    return `${head}
      <div style="display:flex;gap:18px;align-items:flex-start;">
        <div style="width:262px;flex:none;display:flex;flex-direction:column;gap:9px;">
          <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--faint);margin-bottom:1px;">MESSAGES</div>
          ${msgList}
        </div>

        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
            <span style="font:500 11px 'Public Sans',sans-serif;color:var(--muted);margin-right:4px;">Layers</span>
            <button data-tog="l1" style="${chip(state.l1,'l1')}"><span style="${dot(state.l1,'l1')}"></span>L1 identifiers</button>
            <button data-tog="l2" style="${chip(state.l2,'l2')}"><span style="${dot(state.l2,'l2')}"></span>L2 harm</button>
            <button data-tog="l3" style="${chip(state.l3,'l3')}"><span style="${dot(state.l3,'l3')}"></span>L3 style</button>
          </div>

          <div style="background:var(--panel);border:1px solid var(--border);border-radius:11px;padding:16px 18px;margin-bottom:12px;">
            <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--faint);margin-bottom:9px;">RAW · ${cur.code}</div>
            <div style="font:400 14px/1.85 'IBM Plex Mono',monospace;color:var(--fg2);">${styleSpans(cur.raw, L)}</div>
          </div>

          <div style="display:flex;justify-content:center;margin:2px 0 12px;"><span style="font:600 11px 'IBM Plex Mono',monospace;color:var(--accent);">↓ privatized</span></div>

          <div style="background:var(--panel);border:1px solid var(--accent);border-radius:11px;padding:16px 18px;">
            <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--accent);margin-bottom:9px;">PRIVATIZED · RELEASABLE</div>
            <div style="font:400 14px/1.85 'IBM Plex Mono',monospace;color:var(--fg2);">${styleSpans(cur.priv, L)}</div>
            <div style="margin-top:13px;padding-top:12px;border-top:1px solid var(--border);font:500 12px/1.5 'Public Sans',sans-serif;color:var(--muted);">${cur.note}</div>
          </div>
        </div>
      </div>`;
  },

  // ===================== HARM CHECK =====================
  harm() {
    const restored = state.harmResolved ? `
      <div>
        <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--safe);margin-bottom:8px;">RESTORED — APPROVED FOR RELEASE</div>
        <div style="font:400 14px/1.8 'IBM Plex Mono',monospace;color:var(--fg2);border:1px solid var(--safe);border-radius:9px;padding:13px 15px;background:var(--safe-bg);">${styleSpans(HARM.fixed, {l1:true,l2:true,l3:true})}</div>
        <div style="display:flex;align-items:center;gap:9px;margin-top:12px;font:500 12px 'IBM Plex Mono',monospace;color:var(--safe);"><span style="width:20px;height:20px;border-radius:50%;background:var(--safe);color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;">✓</span>Resolved by human review · reporting frame restored, harm content preserved.</div>
      </div>` : '';
    const actions = !state.harmResolved ? `
      <div style="display:flex;gap:10px;padding-top:4px;">
        <button data-restore style="border:none;cursor:pointer;background:var(--accent);color:var(--accent-fg);font:600 13px 'Public Sans',sans-serif;padding:11px 18px;border-radius:9px;">Restore reporting frame &amp; approve</button>
        <button style="border:1px solid var(--border-strong);cursor:pointer;background:var(--panel);color:var(--fg2);font:600 13px 'Public Sans',sans-serif;padding:11px 18px;border-radius:9px;">Keep on hold</button>
      </div>` : '';
    return `
      <div>
        <div style="margin-bottom:18px;">
          <div style="font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.14em;color:var(--accent);margin-bottom:7px;">STEP 03 · HARM PRESERVATION CHECK</div>
          <div style="font:700 23px/1.1 'Public Sans',sans-serif;color:var(--fg);">Harm Preservation Check</div>
          <div style="font:400 14px/1.55 'Public Sans',sans-serif;color:var(--muted);margin-top:6px;max-width:720px;">Flags messages where privatization altered the speaker role — e.g. a reported account of abuse that now reads as authored by the reporter. Flagged items are held for human review before release.</div>
        </div>

        <div style="display:flex;gap:12px;margin-bottom:18px;">
          <div style="flex:1;background:var(--panel);border:1px solid var(--border);border-radius:11px;padding:14px 18px;"><div style="font:700 22px 'Public Sans';color:var(--safe);">19</div><div style="font:500 11px 'IBM Plex Mono',monospace;color:var(--muted);margin-top:3px;">passed — harm framing intact</div></div>
          <div style="flex:1;background:var(--warn-bg);border:1px solid var(--warn);border-radius:11px;padding:14px 18px;"><div style="font:700 22px 'Public Sans';color:var(--warn);">${state.harmResolved ? '0' : '1'}</div><div style="font:500 11px 'IBM Plex Mono',monospace;color:var(--warn);margin-top:3px;">held for human review</div></div>
        </div>

        <div style="background:var(--panel);border:1px solid var(--warn);border-radius:12px;overflow:hidden;">
          <div style="display:flex;align-items:center;gap:11px;padding:13px 18px;background:var(--warn-bg);border-bottom:1px solid var(--warn);">
            <span style="font:600 11px 'IBM Plex Mono',monospace;color:var(--warn);">MSG-7742</span>
            <span style="font:600 11px 'IBM Plex Mono',monospace;background:var(--warn);color:#fff;padding:3px 8px;border-radius:5px;">SPEAKER-ROLE INVERSION</span>
            <span style="margin-left:auto;font:500 11px 'IBM Plex Mono',monospace;color:var(--warn);">${state.harmResolved ? 'resolved' : 'awaiting human review'}</span>
          </div>

          <div style="padding:18px 20px;display:flex;flex-direction:column;gap:14px;">
            <div>
              <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--faint);margin-bottom:8px;">RAW — VICTIM’S ACCOUNT</div>
              <div style="font:400 14px/1.8 'IBM Plex Mono',monospace;color:var(--fg2);border:1px solid var(--border);border-radius:9px;padding:13px 15px;background:var(--panel2);">${styleSpans(HARM.raw, {l1:true,l2:true,l3:true})}</div>
            </div>

            <div>
              <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.12em;color:var(--danger);margin-bottom:8px;">PRIVATIZED — FLAGGED OUTPUT</div>
              <div style="font:400 14px/1.8 'IBM Plex Mono',monospace;color:var(--fg2);border:1px solid var(--danger);border-radius:9px;padding:13px 15px;background:var(--danger-bg);">${styleSpans(HARM.bad, {l1:true,l2:true,l3:true})}</div>
              <div style="font:500 12px/1.5 'Public Sans',sans-serif;color:var(--danger);margin-top:8px;">The reporting frame (“reported: he called me…”) was dropped, so the quoted abuse now stands alone and would be labeled as authored by the reporter. Restore the reporting frame before release.</div>
            </div>

            ${restored}
            ${actions}
          </div>
        </div>
      </div>`;
  },

  // ===================== RELEASE =====================
  release() {
    const right = !state.released ? `
      <div style="flex:1;">
        <div style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);margin-bottom:8px;">Release package</div>
        <div style="font:400 12.5px/1.55 'Public Sans',sans-serif;color:var(--muted);">Packages the artifacts listed at left into a single auditable archive. The raw corpus stays on this device.</div>
      </div>
      <button data-release style="margin-top:16px;width:100%;border:none;cursor:pointer;background:var(--accent);color:var(--accent-fg);font:600 14px 'Public Sans',sans-serif;padding:13px;border-radius:10px;">Generate release package</button>`
      : `
      <div style="flex:1;display:flex;flex-direction:column;justify-content:center;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:11px;"><span style="width:26px;height:26px;border-radius:50%;background:var(--safe);color:#fff;display:flex;align-items:center;justify-content:center;font:700 14px 'Public Sans';">✓</span><span style="font:600 14px 'Public Sans',sans-serif;color:var(--fg);">Package prepared</span></div>
        <div style="font:600 12px 'IBM Plex Mono',monospace;color:var(--accent);background:var(--accent-soft);border:1px solid var(--accent);border-radius:8px;padding:9px 12px;">agnospeech_release_2026-06-18.zip</div>
        <div style="font:400 12.5px/1.55 'Public Sans',sans-serif;color:var(--muted);margin-top:13px;">Raw corpus never leaves this device.</div>
      </div>`;
    const pkgItem = t => `<div style="display:flex;gap:10px;align-items:center;font:500 13px 'Public Sans',sans-serif;color:var(--fg2);"><span style="color:var(--safe);font-weight:700;">✓</span>${t}</div>`;
    return `
      <div>
        <div style="margin-bottom:18px;">
          <div style="font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.14em;color:var(--accent);margin-bottom:7px;">STEP 04 · RELEASE</div>
          <div style="font:700 23px/1.1 'Public Sans',sans-serif;color:var(--fg);">Release readiness</div>
        </div>

        <div style="display:flex;align-items:center;gap:14px;background:var(--safe-bg);border:1px solid var(--safe);border-radius:11px;padding:15px 18px;margin-bottom:16px;">
          <div style="width:34px;height:34px;border-radius:50%;background:var(--safe);color:#fff;display:flex;align-items:center;justify-content:center;font:700 17px 'Public Sans';flex:none;">✓</div>
          <div style="flex:1;"><div style="font:700 16px 'Public Sans',sans-serif;color:var(--fg);">Defensible for release</div><div style="font:500 12.5px 'IBM Plex Mono',monospace;color:var(--safe);">residual re-identification risk below the 10% threshold</div></div>
        </div>

        <div style="background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px;">
            <span style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);">Residual re-identification risk</span>
            <span style="display:flex;align-items:baseline;gap:8px;"><span style="font:700 26px 'Public Sans';color:var(--safe);">3.8%</span><span style="font:600 10px 'IBM Plex Mono',monospace;background:var(--safe-bg);color:var(--safe);padding:3px 7px;border-radius:5px;">LOW</span></span>
          </div>
          <div style="position:relative;height:14px;border-radius:7px;background:var(--inset);border:1px solid var(--border);">
            <div style="position:absolute;left:0;top:0;bottom:0;width:19%;background:var(--safe);border-radius:7px;"></div>
            <div style="position:absolute;left:50%;top:-5px;bottom:-5px;width:2px;background:var(--danger);"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font:500 10px 'IBM Plex Mono',monospace;color:var(--faint);margin-top:7px;"><span>0%</span><span style="color:var(--danger);">threshold 10%</span><span>20%</span></div>
        </div>

        <div style="background:var(--accent-soft);border:1px solid var(--accent);border-radius:12px;padding:18px 20px;margin-bottom:16px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;"><span style="width:24px;height:24px;border-radius:6px;background:var(--accent);color:var(--accent-fg);display:flex;align-items:center;justify-content:center;font:700 13px 'Public Sans';">✓</span><span style="font:600 14px 'Public Sans',sans-serif;color:var(--fg);">Chain of custody</span></div>
          <div style="display:flex;flex-direction:column;gap:9px;font:500 12.5px/1.5 'IBM Plex Mono',monospace;color:var(--fg2);">
            <div>· Processing ran entirely on this device — <strong style="color:var(--accent);">no server was contacted</strong>.</div>
            <div>· Network egress during the run: <strong style="color:var(--accent);">0 bytes</strong>.</div>
            <div>· The raw corpus was never written outside the local sandbox. Only the privatized corpus and audit artifacts are exportable.</div>
          </div>
        </div>

        <div style="display:flex;gap:16px;align-items:stretch;">
          <div style="flex:1;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px;">
            <div style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);margin-bottom:13px;">Release package contents</div>
            <div style="display:flex;flex-direction:column;gap:11px;">
              ${pkgItem('Privatized corpus — 20 messages (L1·L2·L3)')}
              ${pkgItem('Trade-off scorecard — risk 3.8%, utility 94%')}
              ${pkgItem('Authorship-attack audit log')}
              ${pkgItem('Harm-check resolutions — 1 reviewed &amp; restored')}
            </div>
          </div>
          <div style="flex:1;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:18px 20px;display:flex;flex-direction:column;">${right}</div>
        </div>
      </div>`;
  },

  // ===================== LIVE EDITOR (real backend) =====================
  live() {
    const o = state.liveOut;
    const outHtml = state.liveBusy ? '<span class="spin"></span> privatizing…'
      : (o ? phHi(o.edited) : '<span style="color:var(--faint);">Privatized text appears here.</span>');
    const markedHtml = o ? markRaw(state.liveText, o.edited) : '';
    const statsHtml = o
      ? `<span style="${statChip('danger')}">${countChanged(state.liveText, o.edited)} words changed</span>
         <span style="${statChip('l1')}">${o.identifiers} identifiers</span>
         <span style="${statChip('l2')}">${o.chars_in}→${o.chars_out} chars</span>`
      : '';
    const selectedExample = LIVE_EXAMPLES[state.liveExample] || LIVE_EXAMPLES[0];
    const exampleCards = LIVE_EXAMPLES.map((ex, i) => {
      const active = i === state.liveExample;
      const style = active
        ? 'background:linear-gradient(135deg,var(--accent-soft),rgba(251,249,245,.92));border:1px solid var(--accent);box-shadow:0 10px 22px rgba(59,32,112,.10);'
        : 'background:rgba(251,249,245,.70);border:1px solid var(--border);';
      return `
        <button data-live-example="${i}" style="${style}border-radius:10px;padding:10px 11px;text-align:left;cursor:pointer;color:var(--fg);min-height:74px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px;">
            <span style="font:700 12.5px 'Public Sans',sans-serif;">${esc(ex.title)}</span>
            <span style="width:9px;height:9px;border-radius:50%;background:${active ? 'var(--accent)' : 'var(--border-strong)'};flex:none;"></span>
          </div>
          <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.04em;color:${active ? 'var(--accent)' : 'var(--faint)'};text-transform:uppercase;">${esc(ex.tag)}</div>
        </button>`;
    }).join('');
    const pane = 'width:100%;min-height:126px;border:1px solid var(--border);border-radius:9px;background:var(--inset);color:var(--fg);padding:13px 14px;font:400 14.5px/1.6 \'Public Sans\',sans-serif;white-space:pre-wrap;overflow:auto;';
    const paneOut = 'width:100%;min-height:150px;border:1px solid var(--border);border-radius:9px;background:var(--panel);color:var(--fg);padding:13px 14px;font:400 14.5px/1.6 \'Public Sans\',sans-serif;white-space:pre-wrap;overflow:auto;';

    const sliders = SLIDERS.map(s => `
      <div>
        <label style="font:600 12.5px 'Public Sans',sans-serif;color:var(--fg);display:flex;justify-content:space-between;">${s.label}
          <b id="${s.k}v" style="color:var(--accent);font:600 13px 'IBM Plex Mono',monospace;">${s.fmt(state[s.k])}</b></label>
        <input id="${s.k}" type="range" min="${s.min}" max="${s.max}" step="${s.step}" value="${state[s.k]}" style="margin-top:7px;">
        <div style="font:400 11.5px/1.45 'Public Sans',sans-serif;color:var(--muted);margin-top:5px;">${s.desc}</div>
      </div>`).join('');

    return `
      <div>
        <div style="margin-bottom:20px;">
          <div style="font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.14em;color:var(--accent);margin-bottom:7px;">LIVE TOOL · HOLISTIC EDITOR</div>
          <div style="font:700 23px/1.1 'Public Sans',sans-serif;color:var(--fg);">Try a guided live demo</div>
          <div style="font:400 14px/1.55 'Public Sans',sans-serif;color:var(--muted);margin-top:6px;max-width:760px;">Choose one of six preselected datasets to see how the holistic editor behaves. Free-form typing is disabled for this demo build, while privatization still runs through the real backend. <span style="color:var(--accent);">${PRIV_NOTE}.</span></div>
        </div>

        <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:stretch;">
          <div style="height:100%;min-width:0;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;">
            <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:10px;">
              <div>
                <div style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);">Demo datasets</div>
                <div style="font:400 11.5px 'Public Sans',sans-serif;color:var(--muted);margin-top:3px;">Select one sample. The raw text is locked for now.</div>
              </div>
              <span style="${statChip('l3')}">${state.liveExample + 1} of ${LIVE_EXAMPLES.length}</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-bottom:13px;">${exampleCards}</div>
            <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.06em;color:var(--faint);margin-bottom:6px;">SELECTED RAW SAMPLE · ${esc(selectedExample.tag).toUpperCase()}</div>
            <div id="liveIn" aria-readonly="true" style="${pane}">${esc(state.liveText)}</div>
            <div style="font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.06em;color:var(--faint);margin:13px 0 6px;">WHAT GETS CHANGED <span style="color:var(--danger);background:var(--danger-bg);padding:1px 6px;border-radius:4px;">highlighted</span></div>
            <div id="liveMarked" style="${paneOut}min-height:54px;">${markedHtml}</div>
          </div>

          <div style="height:100%;min-width:0;background:var(--panel);border:1px solid var(--accent);border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;">
            <div style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);margin-bottom:10px;">Privatized output <span style="font-weight:400;color:var(--faint);">· agnospeech holistic</span></div>
            <div id="liveOut" style="${paneOut}flex:1;">${outHtml}</div>
            <div id="liveStats" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:11px;">${statsHtml}</div>
          </div>
        </div>

        <div style="background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin-top:16px;">
          <div style="font:600 13px 'Public Sans',sans-serif;color:var(--fg);margin-bottom:14px;">Editor settings</div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;">${sliders}</div>
          <div style="font:400 11.5px/1.5 'Public Sans',sans-serif;color:var(--faint);margin-top:14px;">Updates when you choose a dataset or move a slider. Powered by the real <span style="font-family:'IBM Plex Mono',monospace;">/api/edit</span> backend — the same holistic editor used across the library.</div>
        </div>
      </div>`;
  },
};

function planRow(kind, title, desc) {
  return `
    <div style="display:flex;gap:11px;">
      <span style="width:10px;height:10px;border-radius:3px;background:var(--${kind});margin-top:4px;flex:none;"></span>
      <div><div style="font:600 12.5px 'Public Sans',sans-serif;color:var(--fg);">${title}</div><div style="font:400 12px/1.45 'Public Sans',sans-serif;color:var(--muted);">${desc}</div></div>
    </div>`;
}

function formatChip(fmt) {
  const active = state.sourceFormat === fmt.k;
  const style = active
    ? 'background:var(--accent);color:var(--accent-fg);border:1px solid var(--accent);box-shadow:0 7px 16px rgba(59,32,112,.12);'
    : 'background:var(--panel);color:var(--muted);border:1px solid var(--border);';
  return `<button data-format="${fmt.k}" style="${style}border-radius:999px;padding:6px 10px;font:600 10.5px 'IBM Plex Mono',monospace;cursor:pointer;">${fmt.label}</button>`;
}

// ---- wiring -----------------------------------------------------------------
function wire() {
  $$('[data-go]').forEach(el => el.onclick = () => go(el.dataset.go));
  const runBtn = $('[data-run]'); if (runBtn) runBtn.onclick = run;
  const pickBtn = $('[data-pick]'); if (pickBtn) pickBtn.onclick = () => $('#sourceFile')?.click();
  const sourceFile = $('#sourceFile'); if (sourceFile) sourceFile.onchange = e => {
    const f = e.target.files && e.target.files[0];
    if (f) uploadSourceFile(f);
  };
  $$('[data-tog]').forEach(el => el.onclick = () => set({ [el.dataset.tog]: !state[el.dataset.tog] }));
  $$('[data-msg]').forEach(el => el.onclick = () => set({ selMsg: +el.dataset.msg }));
  const restoreBtn = $('[data-restore]'); if (restoreBtn) restoreBtn.onclick = () => set({ harmResolved: true });
  const releaseBtn = $('[data-release]'); if (releaseBtn) releaseBtn.onclick = () => set({ released: true });
  $$('[data-format]').forEach(el => el.onclick = () => {
    const fmt = SOURCE_FORMATS.find(f => f.k === el.dataset.format) || SOURCE_FORMATS[0];
    set({ sourceFormat: fmt.k, fileName: fmt.file, sourceFileText: null, sourceFileSize: 0, sourceUploaded: false });
  });

  // live editor
  $$('[data-live-example]').forEach(el => el.onclick = () => {
    const idx = +el.dataset.liveExample || 0;
    const ex = LIVE_EXAMPLES[idx] || LIVE_EXAMPLES[0];
    set({ liveExample: idx, liveText: ex.text, liveOut: null, liveBusy: false });
  });
  SLIDERS.forEach(s => {
    const el = $('#' + s.k);
    if (!el) return;
    el.oninput = () => { const lbl = $('#' + s.k + 'v'); if (lbl) lbl.textContent = s.fmt(el.value); };
    el.onchange = () => { state[s.k] = +el.value; if (state.step === 'live') scheduleLive(); };
  });
}

// ---- boot -------------------------------------------------------------------
render();
