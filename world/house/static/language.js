/* Language as NEURAL PATTERNS in the BANC carve.
   A word here is not an entry in a list: it is WHICH KC neurons fire for it
   and which MBON pool that activation won. The panel shows the counts, whether
   the connectome can speak yet, and the actual neurons behind a word. */
'use strict';

Object.assign(House, {
  initLanguage() {
    House.refreshLanguage();
  },

  _langMsg(text, bad) {
    const box = House.byId('lang-gloss');
    if (!box) return;
    box.textContent = text;
    box.className = 'small ' + (bad ? 'bad' : 'muted');
  },

  async refreshLanguage() {
    let s;
    try { s = await House.api('/api/language/state'); }
    catch (e) { House._langMsg('state unreadable: ' + e.message, true); return; }
    House.renderLanguageState(s);
    await House.refreshLanguageVocab();
  },

  renderLanguageState(s) {
    const box = House.byId('lang-state');
    if (!box) return;
    box.textContent = '';
    if (!s.present) {
      box.appendChild(House.el('div', { class: 'warn',
        text: 'no language organ on this agent' }));
      return;
    }
    box.appendChild(House.el('div', { class: s.can_speak ? 'ok' : 'warn',
      text: s.can_speak
        ? 'CAN SPEAK: ' + House.num(s.vocabulary_size) + ' words encoded as '
        + 'KC patterns (threshold ' + House.num(s.min_vocabulary) + ')'
        : 'SILENT: ' + House.num(s.vocabulary_size) + ' of '
        + House.num(s.min_vocabulary) + ' word patterns needed. '
        + 'It will not pretend otherwise.' }));
    [
      ['word patterns', s.word_patterns],
      ['neural basis', s.neural_basis || 'BANC_v888_KC_neurons'],
      ['exchanges observed', s.exchanges_observed],
    ].forEach(([k, v]) => box.appendChild(House.el('div', { class: 'kv' },
      [House.el('b', { text: k }), House.el('span', { text: House.fmt(v) })])));
    const pools = Object.entries(s.pools_used || {}).map(([p, n]) =>
      'pool ' + p + ': ' + n).join(', ');
    if (pools) box.appendChild(House.el('div', { class: 'kv' },
      [House.el('b', { text: 'words per pool' }),
       House.el('span', { text: pools })]));
  },

  async refreshLanguageVocab() {
    const q = encodeURIComponent((House.byId('lang-filter') || {}).value || '');
    const vs = await House.api('/api/language/store?section=vocabulary&q=' + q
      + '&limit=200').catch(() => null);
    const box = House.byId('lang-vocab');
    const cnt = House.byId('lang-vocab-count');
    if (cnt && vs) cnt.textContent = House.num(vs.matched) + ' of '
      + House.num(vs.total);
    if (box) {
      box.textContent = '';
      ((vs && vs.vocabulary) || []).forEach(w => {
        const row = House.el('div', {
          class: 'vocab-row', style: 'cursor:pointer',
          title: 'show the KC neurons that fire for this word' });
        row.appendChild(House.el('b', { text: w.word }));
        row.appendChild(House.el('span', { class: 'small muted',
          text: 'pool ' + w.pool + ' - ' + (w.kc_count || 0) + ' KCs - from '
            + (w.source || '?') }));
        row.addEventListener('click', () => House.showWordPattern(w));
        box.appendChild(row);
      });
      if (vs && !(vs.vocabulary || []).length) {
        box.appendChild(House.el('div', { class: 'muted',
          text: 'no word patterns yet. Teach it with real lessons, or talk '
              + '-- conversation is experience, but only a teacher encodes '
              + 'words.' }));
      }
    }
  },

  /* The visualization the whole tab exists for: WHICH KC neurons fire. */
  showWordPattern(w) {
    House._selWord = w;
    const label = House.byId('lang-pattern-word');
    const box = House.byId('lang-kc');
    const pool = House.byId('lang-pool');
    const fb = House.byId('lang-forget');
    if (fb) fb.disabled = false;
    if (label) label.textContent = '"' + w.word + '"';
    if (!box) return;
    box.textContent = '';
    const kcs = w.kc || [];
    const total = 3840;
    kcs.forEach(i => {
      box.appendChild(House.el('span', { class: 'kcpip', title: 'KC #' + i,
        text: String(i) }));
    });
    if (pool) pool.textContent = 'this pattern won MBON pool ' + w.pool
      + ' (' + kcs.length + ' of ' + total + ' KC code cells active). The '
      + 'meaning is not stored as text: it IS this activation.';
  }
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('#learn-subtabs .stab').forEach(b => {
    b.addEventListener('click', () => {
      document.querySelectorAll('#learn-subtabs .stab').forEach(x =>
        x.classList.toggle('active', x === b));
      document.querySelectorAll('#learning-panel .lsub').forEach(s =>
        s.hidden = s.id !== 'lsub-' + b.dataset.lsub);
    });
  });
  let _parTags = [];
  const pollPar = async () => {
    try {
      const c = await House.api('/api/language/curriculum');
      const set = (id, v) => { const el = House.byId(id); if (el) el.textContent = v; };
      const nar = c.narration || {};
      set('par-phase', nar.phase || '?');
      set('par-care', nar.care_active || 'none');
      set('par-total', c.total || 0);
      set('par-att', c.attention != null ? c.attention : '?');
      set('par-count', (c.lessons || []).filter(l => l.sayable_now).length +
        ' sayable right now');
      const ls = c.lessons || [];
      const said = ls.filter(l => l.last_spoken_ago_world_s != null)
        .sort((a, b) => a.last_spoken_ago_world_s - b.last_spoken_ago_world_s)[0];
      set('par-status', said
        ? 'last: “' + said.sentence + '” · ' +
          House.num(said.last_spoken_ago_world_s) + 's ago'
        : 'nothing said yet');
      _parTags = c.groundings || [];
      const sel = House.byId('par-new-tag');
      if (sel && !sel.options.length) {
        _parTags.forEach(t => { const o = document.createElement('option');
          o.value = t; o.textContent = t; sel.appendChild(o); });
        sel.value = 'event:user';
      }
      renderParEvents(nar.recent_events || []);
      renderLessons(ls);
    } catch (e) { }
  };

  function renderParEvents(events) {
    const box = House.byId('par-events');
    if (!box) return;
    box.textContent = '';
    if (!events.length) {
      box.appendChild(House.el('div', { class: 'muted small',
        text: 'nothing has happened lately' }));
      return;
    }
    events.slice().reverse().forEach(ev => {
      box.appendChild(House.el('div', { class: 'par-ev' }, [
        House.el('span', { class: 'par-ev-kind', text: ev.kind }),
        House.el('span', { class: 'par-ev-detail', text: ev.detail || '' }),
        House.el('span', { class: 'par-ev-age',
          text: House.num(ev.age_world_s) + 's ago' +
            (ev.narrated ? ' · said ' + ev.narrated : '') }),
      ]));
    });
  }

  function renderLessons(lessons) {
    const box = House.byId('par-lessons');
    if (!box) return;
    box.textContent = '';
    lessons.forEach((l, i) => {
      const row = House.el('div', {
        class: 'lesson-row' + (l.sayable_now ? ' sayable' : '') });
      row.appendChild(House.el('span', { class: 'lesson-idx', text: i }));
      const sentence = House.el('span', { class: 'lesson-sentence',
        text: l.sentence, title: 'click to edit this phrase' });
      sentence.addEventListener('click', () => editLesson(i, l, row));
      row.appendChild(sentence);
      row.appendChild(House.el('span', { class: 'lesson-tag',
        text: l.tag || 'custom',
        title: 'spoken only while this is true of the world' }));
      if (l.care) {
        row.appendChild(House.el('span', { class: 'lesson-care', text: l.care,
          title: 'the real care act spoken together with it' }));
      }
      row.appendChild(House.el('span', { class: 'lesson-lived',
        text: '×' + (l.times_lived || 0),
        title: (l.last_spoken_ago_world_s != null
          ? 'last said ' + House.num(l.last_spoken_ago_world_s) + ' world-s ago'
          : 'never said yet') }));
      const del = House.el('button', { class: 'ghost lesson-del', text: '×',
        title: 'delete this phrase' });
      del.addEventListener('click', async () => {
        if (!confirm('delete "' + l.sentence + '"?')) return;
        try {
          await House.post('/api/language/curriculum/edit',
            { op: 'delete', index: i });
          pollPar();
        } catch (e) { del.textContent = '!'; }
      });
      row.appendChild(del);
      box.appendChild(row);
    });
  }

  function editLesson(i, l, row) {
    row.textContent = '';
    row.classList.add('editing');
    const text = House.el('input', { class: 'lesson-edit-text' });
    text.value = l.sentence;
    const tag = House.el('select', { class: 'lesson-edit-tag' });
    (_parTags.length ? _parTags : [l.tag || 'custom']).forEach(t => {
      const o = document.createElement('option');
      o.value = t; o.textContent = t;
      if (t === (l.tag || 'custom')) o.selected = true;
      tag.appendChild(o);
    });
    const care = House.el('select', { class: 'lesson-edit-care' });
    [['', 'no care act'], ['feed', 'feed'], ['pet', 'pet'],
     ['praise', 'praise']].forEach(pair => {
      const o = document.createElement('option');
      o.value = pair[0]; o.textContent = pair[1];
      if ((l.care || '') === pair[0]) o.selected = true;
      care.appendChild(o);
    });
    const save = House.el('button', { class: 'ghost', text: 'save' });
    const cancel = House.el('button', { class: 'ghost', text: 'cancel' });
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const r = await House.post('/api/language/curriculum/edit',
          { op: 'update', index: i, sentence: text.value, tag: tag.value,
            care: care.value || null });
        if (r && r.success === false) {
          alert(r.reason || 'refused'); save.disabled = false; return;
        }
        pollPar();
      } catch (e) { alert('save failed: ' + e.message); save.disabled = false; }
    });
    cancel.addEventListener('click', pollPar);
    [text, tag, care, save, cancel].forEach(n => row.appendChild(n));
    text.focus();
  }

  const addInput = House.byId('par-new-sentence');
  if (House.byId('par-add')) House.byId('par-add').addEventListener('click', async () => {
    const s = (addInput ? addInput.value : '').trim();
    if (!s) return;
    const tagSel = House.byId('par-new-tag');
    const careSel = House.byId('par-new-care');
    try {
      const r = await House.post('/api/language/curriculum/edit',
        { op: 'add', sentence: s,
          tag: tagSel ? tagSel.value : 'custom',
          care: careSel && careSel.value ? careSel.value : null });
      if (r && r.success === false) { alert(r.reason || 'refused'); return; }
      if (addInput) addInput.value = '';
      pollPar();
    } catch (e) { alert('add failed: ' + e.message); }
  });
  const dialBtn = House.byId('par-dials');
  if (dialBtn) dialBtn.addEventListener('click', async () => {
    try {
      await House.post('/api/language/curriculum/edit', { op: 'dials',
        attention: parseFloat(House.byId('par-attention')?.value) || undefined,
        reward: parseFloat(House.byId('par-reward')?.value) || undefined });
    } catch (e) { }
  });
  const startPar = async () => {
    try {
      await House.post('/api/language/curriculum', {});
      House._langMsg('curriculum started');
    } catch (e) { House._langMsg('failed: ' + e.message); }
    pollPar();
  };
  const ps = House.byId('par-start');
  if (ps) ps.addEventListener('click', startPar);
  pollPar(); setInterval(pollPar, 4000);
  // The tutor block that stood here polled /api/language/tutor every 4 seconds -- an
  // endpoint that no longer exists, so it was a request to a 404 on a timer, forever.
  // It also ended with `if (!tb) return;` against an element that is not in the page,
  // so the whole rest of this init -- including the voice panel wiring below -- was
  // never reached. Both are gone with the block.
  const vb = House.byId('voice-enabled');
  const syncVoice = async () => {
    try {
      const v = await House.api('/api/language/voice');
      if (vb && document.activeElement !== vb) vb.checked = !!v.enabled;
      const st = House.byId('voice-status');
      if (st) st.textContent = v.enabled ? 'on' : 'off';
      const mx = House.byId('voice-max');
      if (mx && document.activeElement !== mx) mx.value = v.max_sentence_words;
    } catch (e) { }
  };
  if (vb) vb.addEventListener('change', async () => {
    try { await House.post('/api/language/voice', { enabled: vb.checked }); }
    catch (e) { }
    syncVoice();
  });
  const vapply = House.byId('voice-apply');
  if (vapply) vapply.addEventListener('click', async () => {
    try {
      await House.post('/api/language/voice', {
        max_sentence_words: parseInt(House.byId('voice-max')?.value, 10) || 6 });
    } catch (e) { }
    syncVoice();
  });
  const vtry = House.byId('voice-try');
  if (vtry) vtry.addEventListener('click', async () => {
    const out = House.byId('voice-out');
    vtry.disabled = true;
    if (out) out.textContent = 'thinking...';
    try {
      const r = await House.post('/api/language/sentence', {
        context: 'what is on my mind', render: vb ? vb.checked : false });
      if (out) {
        out.textContent = (r.sentence || '(nothing)') +
          (r.stopped ? '  [' + r.stopped + ']' : '') +
          (r.voice && r.voice.rendered ? '\nvoice: ' + r.voice.text : '');
      }
    } catch (e) { if (out) out.textContent = 'failed: ' + e.message; }
    vtry.disabled = false;
  });
  syncVoice();
  // pushTutor posted the tutor settings to the same removed endpoint, from controls
  // that are not in the page. Nothing to push, nothing to wire.

  const lf = House.byId('lang-filter');
  if (lf) lf.addEventListener('input', () => House.refreshLanguageVocab());
  const fb = House.byId('lang-forget');
  if (fb) fb.addEventListener('click', async () => {
    const w = House._selWord;
    if (!w) { House._langMsg('pick a word first'); return; }
    if (!confirm('delete "' + w.word + '" from the vocabulary?')) return;
    fb.disabled = true;
    try {
      await House.post('/api/language/forget', { word: w.word });
      House._selWord = null;
      const label = House.byId('lang-pattern-word');
      const kc = House.byId('lang-kc');
      const pl = House.byId('lang-pool');
      if (label) label.textContent = 'pick a word';
      if (kc) kc.textContent = '';
      if (pl) pl.textContent = '';
      House._langMsg('forgotten: ' + w.word);
      await House.refreshLanguageVocab();
    } catch (e) { House._langMsg('failed: ' + e.message); }
  });
});