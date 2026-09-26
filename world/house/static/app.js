/* Connectome House -- core.
   Shared helpers, the polling loops, the status/guarantee rendering.

   Two rules this file keeps:
     * server text never enters innerHTML. Organ stats and chat carry strings the
       oracle wrote; a dashboard that injects them is a stored-XSS sink with an
       operator's session on it. Everything is built with createElement/textContent.
     * a number with no evidence is shown as "?", never as 0. A fabricated zero
       reads as "nothing happened", which is a claim about the world.
*/
'use strict';

const House = {
  base: window.location.origin,
  seq: 0,
  state: {},
  organCache: {},
  timers: [],
  failing: null,

  el(tag, props, kids) {
    const n = document.createElement(tag);
    if (props) for (const k in props) {
      if (k === 'class') n.className = props[k];
      else if (k === 'text') n.textContent = props[k];
      else if (k === 'html') n.innerHTML = props[k];
      else if (k.startsWith('on')) n.addEventListener(k.slice(2), props[k]);
      else if (props[k] === true) n.setAttribute(k, '');
      else if (props[k] !== false && props[k] != null) n.setAttribute(k, props[k]);
    }
    (Array.isArray(kids) ? kids : kids == null ? [] : [kids]).forEach(c => {
      if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return n;
  },

  byId(id) { return document.getElementById(id); },

  async api(path, opts) {
    const o = { headers: { 'Content-Type': 'application/json' } };
    const tok = localStorage.getItem('house_token');
    if (tok) o.headers['X-House-Token'] = tok;
    if (opts && opts.method) {
      o.method = opts.method;
      o.body = JSON.stringify(opts.body || {});
    }
    const r = await fetch(House.base + path, o);
    let data;
    try { data = await r.json(); }
    catch (e) { throw new Error(path + ' returned non-JSON (' + r.status + ')'); }
    if (r.status === 403 && data && data.error === 'refused') {
      House.mutationRefused(data.reason || 'mutations are loopback-only');
    }
    if (!r.ok && data && data.error) throw new Error(data.error + (data.reason ? ' -- ' + data.reason : ''));
    return data;
  },

  /* Shown once per page load: the connectome refuses writes from this address,
     and here is the honest way to change that. */
  mutationRefused(reason) {
    if (House._refusalShown) return;
    House._refusalShown = true;
    const bar = House.byId('refusal-banner');
    if (!bar) return;
    bar.hidden = false;
    bar.textContent = 'This address may READ only (' + reason + '). '
      + 'Open the house from localhost, or paste the house.access_token:';
    const input = document.createElement('input');
    input.type = 'password'; input.placeholder = 'access token';
    input.style.cssText = 'margin:0 8px;padding:2px 6px;width:220px';
    const ok = document.createElement('button');
    ok.textContent = 'use token'; ok.className = 'ghost';
    ok.addEventListener('click', () => {
      localStorage.setItem('house_token', input.value || '');
      bar.hidden = true; House._refusalShown = false;
    });
    bar.appendChild(input); bar.appendChild(ok);
  },

  post(path, body) { return House.api(path, { method: 'POST', body: body || {} }); },

  fmt(v) {
    if (v === null || v === undefined) return '?';
    if (typeof v === 'number') {
      if (!isFinite(v)) return String(v);
      return Number.isInteger(v) ? v.toLocaleString('en-US') : v.toFixed(v < 1 ? 4 : 2);
    }
    if (typeof v === 'boolean') return v ? 'yes' : 'no';
    return String(v);
  },

  ago(t) {
    if (!t) return '';
    const s = Math.max(0, Math.floor(Date.now() / 1000 - t));
    if (s < 60) return s + 's ago';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    return Math.floor(s / 3600) + 'h ago';
  },

  /* key/value rows for organ bodies; nested dicts are flattened one level */
  kvRows(obj, depth) {
    const out = [];
    if (!obj || typeof obj !== 'object') return out;
    Object.keys(obj).sort().forEach(k => {
      const v = obj[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && (depth || 0) < 1) {
        out.push(House.el('div', { class: 'kv nested', 'data-k': k },
          [House.el('b', { text: k }), House.el('span', { text: '{...}' })]));
        House.kvRows(v, (depth || 0) + 1).forEach(r => out.push(r));
        return;
      }
      let shown;
      if (Array.isArray(v)) shown = v.length > 3 ? '[' + v.length + ' items]' : JSON.stringify(v);
      else if (v && typeof v === 'object') shown = '{' + Object.keys(v).length + ' keys}';
      else shown = House.fmt(v);
      out.push(House.el('div', { class: 'kv', title: k + ' = ' + House.fmt(v) },
        [House.el('b', { text: k }), House.el('span', { text: shown })]));
    });
    return out;
  },

  /* the flat fields the guarantee/optimiser payloads share with the organs */
  num(v, suffix) {
    return (v === null || v === undefined) ? '?' : (House.fmt(v) + (suffix || ''));
  }
};

/* ── views ─────────────────────────────────────────────────────────────── */
function showView(name) {
  const bs = House.byId('brain-subtabs');
  if (bs) bs.classList.toggle('active', name === 'brain');
  if (name === 'brain' && House.showBrainSub) {
    House.showBrainSub(House._brainSub || 'neural');
  }
  document.querySelectorAll('.view').forEach(v =>
    v.classList.toggle('active', v.dataset.view === name));
  document.querySelectorAll('.tab[data-view]').forEach(t =>
    t.classList.toggle('active', t.dataset.view === name));
  if (name === 'learning') House.refreshLearning && House.refreshLearning();
  if (name === 'training') House.refreshTraining && House.refreshTraining();
  if (name === 'language') House.refreshLanguage && House.refreshLanguage();
  if (name === 'neural') House.refreshNeural && House.refreshNeural();
  if (name === 'safety') House.refreshSafety && House.refreshSafety();
  if (name === 'organs') House.refreshOrgans && House.refreshOrgans();
  if (name === 'harness') House.showHarnessSub && House.showHarnessSub(House._hsub || 'reason');
}

/* ── header + status bar ───────────────────────────────────────────────── */
function renderConsciousness(c) {
  const ind = House.byId('state-indicator');
  // No SLEEPING / IDLE / BUSY fiction. Those were labels on a state machine,
  // not measurements of anything. The only honest claim this header can make is
  // whether the carve is being pulsed right now, which is a number the world
  // panel already reports.
  const tps = ((c && c.world) || {}).measured_ticks_per_s;
  const alive = tps > 0;
  ind.textContent = alive ? 'ALIVE' : 'STILL';
  ind.className = 'state-' + (alive ? 'idle' : 'sleeping');
  ind.title = alive ? (tps + ' neural ticks per second')
                    : 'no ticks are reaching the carve';
  const tc = House.byId('thought-count');
  tc.textContent = House.num(c && c.thought_count) + ' thoughts';
  tc.title = 'thoughts since boot; the last dozen are listed in the Learning tab';
}

function renderStatusbar(s) {
  /* The status bar is gone. World speed is in the header, the oracle is in the
     harness, and everything else it carried was a duplicate. This stays as a no-op
     because pollState calls it and it is exported.

     How it broke is worth the comment: removing the oracle pill left om null, the
     .textContent and .title reads were guarded, .className was not, and the throw
     aborted pollState BEFORE refreshVisible and organPollTick -- so every panel
     stopped refreshing and the page just looked empty. A guard on some fields of an
     object is not a guard on the object. */
  return undefined;
}

/* guarantee strip: True green, False red, null grey -- never green by default */
function renderGuarantee(g, into) {
  const box = into || House.byId('guarantee');
  if (!box) return;
  box.textContent = '';
  if (!g || !g.guarantees) {
    box.appendChild(House.el('div', { class: 'muted', text: 'no guarantee payload' }));
    return;
  }
  const label = { true: ['✔', 'g-true'], false: ['✘', 'g-false'], null: ['·', 'g-none'] };
  g.guarantees.forEach(row => {
    const holds = row.holds === true ? 'true' : (row.holds === false ? 'false' : 'null');
    const mk = label[holds];
    box.appendChild(House.el('div', { class: 'g-row ' + mk[1] }, [
      House.el('span', { class: 'g-mark', text: mk[0] }),
      House.el('span', { text: row.id }),
      House.el('span', { class: 'muted', style: 'margin-left:auto;font-size:11px',
        text: row.holds === null ? 'unmeasured' : (row.note || '') }),
    ]));
    if (row.evidence) box.appendChild(House.el('div', { class: 'small', text: row.evidence }));
  });
  const lim = House.byId('guarantee-limits');
  if (lim) lim.textContent = (g.limits || []).join(' · ');
  const v = House.byId('guarantee-verdict');
  if (v) v.textContent = g.verdict || '';
}

/* ── polling ───────────────────────────────────────────────────────────── */
async function pollState() {
  // Every step isolated. One panel throwing used to abort the rest of this chain --
  // a single unguarded null stopped refreshVisible and organPollTick from running at
  // all, and the page simply looked empty with nothing in the console to say why.
  // A dashboard should degrade by losing one panel, not by going blind.
  const safe = (what, fn) => {
    try { fn(); } catch (e) {
      House.pollErrors = House.pollErrors || {};
      House.pollErrors[what] = String((e && e.message) || e);
      if (window.console) console.error('poll step failed: ' + what, e);
    }
  };
  try {
    const s = await House.api('/api/state');
    House.state = s;
    House.seq = s.seq || House.seq;
    safe('consciousness', () => renderConsciousness(s.consciousness));
    safe('statusbar', () => renderStatusbar(s));
    safe('guarantee', () => renderGuarantee((s.stats || {}).guarantee));
    safe('progress', () => House.renderProgress && House.renderProgress(s.progress || []));
    safe('approvals', () => House.renderApprovals && House.renderApprovals(
      (s.consciousness && s.consciousness.pending_approvals) || [],
      (s.sandbox && s.sandbox.pending) || []));
    safe('chat switches', () => House.syncChatSwitches && House.syncChatSwitches(s.mental || {}));
    safe('visible refresh', () => House.refreshVisible());
    safe('organ poll', () => House.organPollTick());
    House.failing = null;
  } catch (e) {
    House.failing = String(e.message || e);
    const f = House.byId('foot-state');
    f.textContent = 'poll failed: ' + House.failing;
    f.classList.add('bad');
  }
}

let organTick = 0;
function refreshVisible() {
  const active = document.querySelector('.view.active');
  const v = active && active.dataset.view;
  if (v === 'language' && House.refreshLanguageVocab) House.refreshLanguageVocab();
  // The harness is gated on being visible. It was in the unconditional poll, and
  // /api/reasoning/state reads the curriculum and reader status off disk every call,
  // so an idle tab we were not even looking at was costing a disk read per six
  // seconds. That comment claiming it was cheap was mine and it was wrong.
  if (v === 'harness') {
    if (House.refreshReason) House.refreshReason();
    if (House.refreshFiles) House.refreshFiles();
  }
  if (v === 'brain') {
    if (House.refreshNeural) House.refreshNeural();
    if (House.refreshSafety) House.refreshSafety();
  }
  if (House.refreshMind) House.refreshMind();
}

function organPollTick() {
  if (++organTick % 3 === 0) {
    House.refreshOrgans && House.refreshOrgans();
    House.refreshSafety && House.refreshSafety();
  }
}

function boot() {
  document.querySelectorAll('.tab[data-view]').forEach(t =>
    t.addEventListener('click', () => showView(t.dataset.view)));
  House.byId('config-open').addEventListener('click', House.openConfig);
  House.byId('config-close').addEventListener('click', House.closeConfig);
  House.byId('config-save').addEventListener('click', House.saveConfig);
  House.byId('breaker-reset') && House.byId('breaker-reset').addEventListener('click', async () => {
    try { await House.post('/api/breaker_reset', {}); pollState(); }
    catch (e) { alert('reset refused: ' + e.message); }
  });
  House.initChat && House.initChat();
  House.initFiles && House.initFiles();
  House.initTerminal && House.initTerminal();
  House.initLearning && House.initLearning();
  House.initTraining && House.initTraining();
  House.initLanguage && House.initLanguage();
  House.initNeural && House.initNeural();
  House.initMind && House.initMind();
  House.initReason && House.initReason();
  pollState();
  // No brain animation interval. It drove a canvas that is not in the page and a
  // function that was never loaded, so every 40 ms it did a DOM query to decide not
  // to do anything.
  House.timers.push(setInterval(pollState, 2000));
}

document.addEventListener('DOMContentLoaded', boot);

Object.assign(House, { renderGuarantee, renderStatusbar, renderConsciousness,
  pollState, showView, boot, refreshVisible, organPollTick });