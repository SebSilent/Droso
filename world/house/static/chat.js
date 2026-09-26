/* The world channel: you speak into the air; Droso hears, and decides.
   Nothing you say is paired with a response. What appears here is whatever
   comes out of Droso's mouth or mind, on its own beat. */
'use strict';

Object.assign(House, {
  initChat() {
    const send = House.byId('chat-send');
    const input = House.byId('chat-input');
    send.addEventListener('click', House.sendMessage);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); House.sendMessage(); }
    });

    document.querySelectorAll('.ws-btn').forEach(b => {
      b.addEventListener('click', async () => {
        try {
          const r = await House.post('/api/world/speed', { mode: b.dataset.mode });
          if (r.success) House.pollWorldSpeed();
        } catch (e) { House.worldLog('speed change failed: ' + e.message); }
      });
    });
    House.pollWorldSpeed();
    setInterval(() => House.pollWorldSpeed(), 2000);

    House._lastEvent = 0;
    setInterval(() => {
      House.api('/api/language/stream?since=' + House._lastEvent).then(r => {
        (r.events || []).forEach(ev => {
          House._lastEvent = Math.max(House._lastEvent, ev.t);
          if (ev.kind === 'speech') {
            const voice = { droso: 'Droso', teacher: 'teacher',
              parent: 'parent', book: 'book', human: 'you', you: 'you' }[ev.speaker]
              || ev.speaker || 'Droso';
            // Who it was said TO is part of the act, not decoration: speech with
            // no addressee is speech into the air, and that is shown as such.
            let label = voice;
            if (ev.to && ev.to !== 'droso') {
              label += ev.to === 'air' ? ' (to the air)' : ' → ' + ev.to;
            }
            if (ev.voice === 'prosthesis') label += ' [voice]';
            // His own words first, always. A render is shown underneath and
            // labelled, so the device's grammar is never mistaken for his.
            let body = ev.text || '';
            if (ev.rendered) body += '\n↳ voice: ' + ev.rendered;
            House.air(voice.toLowerCase() === 'you' ? 'me' : 'droso',
              body, ev, label);
          } else if (ev.kind === 'exposure') {
            House.air('book', (ev.attended === false ? '(drifted) ' : '')
              + (ev.text || ''), ev, 'book');
          } else if (ev.kind === 'curriculum') {
            House.air('droso', ev.text || '', ev, 'parent');
          } else if (ev.kind === 'world') {
            House.worldLog(ev.what + (ev.text ? ': ' + ev.text : ''), ev.t);
          } else if (ev.kind === 'person' || ev.kind === 'milestone') {
            House.worldLog(ev.text || ev.kind, ev.t);
          } else if (ev.kind === 'heard') {
            House.worldLog('heard: ' + (ev.text || '').slice(0, 60));
          } else if (ev.kind === 'thought') {
            House.mind(ev.about
              ? 'thought: “' + ev.about + '” (pool ' + ev.pool + ')'
              : 'thought (pool ' + ev.pool + ')');
          }
        });
      }).catch(() => {});
    }, 2000);

    House.pollExposure = async () => {
      try {
        const s = await House.api('/api/language/exposure');
        const st = House.byId('lg-exp-status');
        if (st) st.textContent = 'exposure: ' + (s.enabled ? 'ON' : 'off') +
          ' \u00b7 book: ' + (s.book || 'none') + ' ' +
          (s.book_progress_pct || 0) + '% \u00b7 words heard: ' +
          s.words_heard_total + ' (' + s.distinct_words_heard +
          ' distinct) \u00b7 vocab: ' + s.vocabulary_size +
          ' \u00b7 mood: ' + s.social_drive;
        const cb = House.byId('lg-exp');
        if (cb && document.activeElement !== cb) cb.checked = !!s.enabled;
        const inner = s.inner || {};
        const setBar = (k, v) => {
          const f = House.byId('mf-' + k), vEl = House.byId('mv-' + k);
          if (f) f.style.width = Math.round((v || 0) * 100) + '%';
          if (vEl) vEl.textContent = (v != null) ? v : '?';
        };
        setBar('mood', inner.mood);
        setBar('lonely', inner.need_social);
        setBar('bored', inner.need_novelty);
        setBar('energy', inner.energy);
        const setSide = (k, v) => {
          const f = document.querySelector('.meter-fill[data-mood="' + k + '"]');
          if (f) f.style.width = Math.round((v || 0) * 100) + '%';
        };
        setSide('mood', inner.mood);
        setSide('lonely', inner.need_social);
        setSide('bored', inner.need_novelty);
        setSide('energy', inner.energy);
        const mph = House.byId('mind-phase');
        if (mph) mph.textContent = 'world ' + Math.round(s.world_clock || 0) + 's';
        if (s.vocabulary_size != null) {
          const hist = (House._vocabHist = House._vocabHist || []);
          const last = hist[hist.length - 1];
          if (!last || last.v !== s.vocabulary_size ||
              s.vocabulary_size === 0 || Date.now() - last.t > 30000)
            hist.push({ t: Date.now(), v: s.vocabulary_size });
          if (hist.length > 90) hist.shift();
          const line = House.byId('vocab-line');
          const area = House.byId('vocab-area');
          const now = House.byId('vocab-now');
          if (line && hist.length > 1) {
            const maxV = Math.max(...hist.map(h => h.v), 1);
            const pts = hist.map((h, i) => {
              const x = hist.length === 1 ? 0 : (i / (hist.length - 1)) * 600;
              return (x.toFixed(1)) + ',' + (66 - (h.v / maxV) * 60).toFixed(1);
            });
            line.setAttribute('points', pts.join(' '));
            area.setAttribute('points', '0,70 ' + pts.join(' ') + ' 600,70');
          }
          if (now) now.textContent = s.vocabulary_size + ' words';
        }
        const setv = (id, v) => {
          const el = House.byId(id);
          if (el && document.activeElement !== el) el.value = v;
        };
        setv('lg-exp-speed', s.speed_s);
        setv('lg-exp-int', s.intensity_words);
        setv('lg-exp-thr', s.assimilation_threshold);
        setv('rw-exposure', s.reward_exposure);
        setv('rw-social', s.reward_social);
        setv('rw-babble', s.reward_babble);
      } catch (e) { /* the world exists unobserved too */ }
    };
    House.pushExposure = async () => {
      const val = id => {
        const el = House.byId(id);
        return el ? el.value : undefined;
      };
      try {
        await House.post('/api/language/exposure', {
          enabled: House.byId('lg-exp') ? House.byId('lg-exp').checked : false,
          speed_s: parseFloat(val('lg-exp-speed')) || 2.0,
          intensity_words: parseInt(val('lg-exp-int')) || 12,
          assimilation_threshold: parseInt(val('lg-exp-thr')) || 12,
          reward_exposure: parseFloat(val('rw-exposure')) || 0.05,
          reward_social: parseFloat(val('rw-social')) || 0.4,
          reward_babble: parseFloat(val('rw-babble')) || 0.08
        });
      } catch (e) { House.worldLog('settings failed: ' + e.message); }
      House.pollExposure();
    };
    ['lg-exp', 'lg-exp-speed', 'lg-exp-int', 'lg-exp-thr', 'rw-exposure',
     'rw-social', 'rw-babble'].forEach(id => {
      const el = House.byId(id);
      if (el) el.addEventListener('change', House.pushExposure);
    });
    House.pollExposure();
    setInterval(House.pollExposure, 3000);

    ['parent', 'book'].forEach(who => {
      const b = House.byId('tog-' + who);
      if (!b) return;
      const key = 'droso.hide.' + who;
      const apply = () => {
        const off = localStorage.getItem(key) === '1';
        document.body.classList.toggle('hide-' + who, off);
        b.classList.toggle('off', off);
      };
      b.addEventListener('click', () => {
        localStorage.setItem(key, localStorage.getItem(key) === '1' ? '0' : '1');
        apply();
      });
      apply();
    });

    document.querySelectorAll('#brain-subtabs .stab').forEach(b => {
      b.addEventListener('click', () => House.showBrainSub(b.dataset.subtab));
    });
    const gd = (id, payload) => async () => {
      try {
        const r = await House.post('/api/neural/grow', payload);
        House.byId('grow-msg').textContent = JSON.stringify(r).slice(0, 160);
        House.pollExposure();
      } catch (e) {
        House.byId('grow-msg').textContent = 'failed: ' + e.message;
      }
    };
    const gb = House.byId('grow-do-syn');
    if (gb) gb.addEventListener('click', gd('syn', {
      synapses: parseInt(House.byId('grow-syn').value) || 100 }));
    const gp = House.byId('grow-do-prune');
    if (gp) gp.addEventListener('click', gd('prune', {
      prune_below: parseFloat(House.byId('grow-prune').value) || 0.004 }));
    const gn = House.byId('grow-do-pool');
    if (gn) gn.addEventListener('click', gd('pool', {
      pool: true, pool_nodes: parseInt(House.byId('grow-pool').value) || 8 }));
    const gc = House.byId('grow-consult');
    if (gc) gc.addEventListener('click', async () => {
      gc.disabled = true; gc.textContent = 'consulting...';
      try {
        const r = await House.post('/api/neural/consult', {});
        House.byId('consult-out').textContent =
          JSON.stringify(r.directive || r).slice(0, 220);
        House.pollExposure();
      } catch (e) {
        House.byId('consult-out').textContent = 'failed: ' + e.message;
      } finally {
        gc.disabled = false; gc.textContent =
          'ask the teacher how to improve the brain';
      }
    });

    const llm = House.byId('toggle-llm');
    if (llm) llm.addEventListener('change', async () => {
      try {
        await House.post('/api/llm/toggle', { enabled: llm.checked });
      } catch (e) {
        llm.checked = !llm.checked;
      }
      House.pollState();
    });

    House.loadHistory();
  },

  showBrainSub(sub) {
    const map = { consciousness: ['brain-consciousness'],
                  neural: ['brain-neural', 'brain-neural-2'],
                  growth: ['brain-growth'] };
    Object.entries(map).forEach(([k, ids]) => {
      ids.forEach(id => {
        const el = House.byId(id);
        if (el) el.hidden = k !== sub;
      });
    });
    document.querySelectorAll('#brain-subtabs .stab').forEach(b =>
      b.classList.toggle('active', b.dataset.subtab === sub));
    House._brainSub = sub;
  },

  async pollWorldSpeed() {
    try {
      const s = await House.api('/api/world/state');
      const out = House.byId('ws-readout');
      // world-pill went with the status bar; the header readout is the only world speed
      if (!out) return;
      if (s.speed === 'paused') out.textContent = 'Droso · paused';
      else if (s.speed === '1x') out.textContent = 'Droso · 1x';
      else out.textContent = 'Droso · max (' + s.measured_speed_x + 'x)';
      document.querySelectorAll('.ws-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.mode === s.speed));
    } catch (e) { /* the world keeps existing without the reader */ }
  },

  cap(node, n) {
    while (node.children.length > n) node.removeChild(node.firstChild);
  },

  air(cls, text, ev, voice) {
    const box = House.byId('chat-messages');
    if (!box) return;
    const sp = (ev && ev.speaker) ? String(ev.speaker).toLowerCase() : '';
    const m = House.el('div', {
      class: 'message ' + cls + (sp ? ' sp-' + sp.replace(/[^a-z]/g, '') : '') });
    const who = House.el('div', { class: 'who',
      text: voice || (cls === 'me' ? 'you' : 'Droso') });
    m.appendChild(who);
    m.appendChild(House.el('div', { class: 'body', text: text || '' }));
    if (ev) {
      const row = House.el('div', { class: 'meta' });
      if (ev.to && ev.to !== 'droso') row.appendChild(House.el('span',
        { class: 'to', text: ev.to === 'air' ? 'to no one' : 'to ' + ev.to }));
      if (ev.words && ev.words.length) row.appendChild(House.el('span',
        { text: (ev.words.length) + ' words' +
          (ev.stopped ? ' · stopped: ' + ev.stopped : '') }));
      if (ev.resonance != null) row.appendChild(House.el('span',
        { text: 'resonance ' + ev.resonance }));
      if (ev.mood != null) row.appendChild(House.el('span',
        { text: 'mood ' + ev.mood }));
      if (row.children.length) m.appendChild(row);
    }
    box.appendChild(m);
    box.scrollTop = box.scrollHeight;
    House.cap(box, 120);
  },

  worldLog(line, t) {
    const box = House.byId('world-log');
    if (!box) return;
    if (box.dataset.last === line) return;   // the same event twice is noise
    box.dataset.last = line;
    const d = t ? new Date(Number(t) * 1000) : new Date();
    const ts = d.toTimeString().slice(0, 8);
    const m = House.el('div', { class: 'logline', text: ts + '  ' + line });
    box.appendChild(m);
    box.scrollTop = box.scrollHeight;
    House.cap(box, 200);
  },

  mind(line) {
    const box = House.byId('mind-stream');
    if (!box) return;
    const m = House.el('div', { class: 'logline', text: line });
    box.appendChild(m);
    box.scrollTop = box.scrollHeight;
    House.cap(box, 200);
  },

  addMessage(role, content, cls) {
    const box = House.byId('chat-messages');
    const m = House.el('div', { class: 'message ' + role + (cls ? ' ' + cls : '') });
    m.appendChild(House.el('div', { class: 'body', text: content || '' }));
    box.appendChild(m);
    box.scrollTop = box.scrollHeight;
    return m;
  },

  async loadHistory() {
    try {
      const h = await House.api('/api/chat_history');
      const box = House.byId('chat-messages');
      (h.history || []).forEach(msg => {
        House.air(msg.role === 'user' ? 'me' : 'droso', msg.content);
      });
    } catch (e) { /* an empty air is honest */ }
  },

  renderMeta(node, meta) {
    const row = House.el('div', { class: 'meta' });
    const add = (k, v, cls) => row.appendChild(
      House.el('span', { class: cls || '', text: k + ': ' + v }));
    if (meta.ms != null) add('time', meta.ms + ' ms');
    if (meta.api_calls != null) add('api_calls', meta.api_calls);
    if (meta.oracle_mode) add('oracle', meta.oracle_mode +
      (meta.oracle_model ? '/' + meta.oracle_model : ''),
      meta.oracle_mode === 'live' ? 'good' : 'warn');
    if (meta.verified === true) add('verified', 'yes', 'good');
    if (meta.resonance != null) add('resonance', meta.resonance);
    if (meta.mood != null) add('mood', meta.mood);
    if (meta.reason) add('reason', String(meta.reason).slice(0, 80), 'warn');
    node.appendChild(row);
  },

  async sendMessage() {
    const input = House.byId('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    House.air('me', msg);
    try {
      await House.post('/api/chat', { message: msg });
    } catch (e) {
      House.worldLog('world channel error: ' + e.message);
    }
  }
});