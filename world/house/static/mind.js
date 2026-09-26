/* THE MIND: a 24/7 window into the connectome.
   Everything rendered here is measured -- the pulses the heartbeat actually
   drove through the carve, the thoughts its organs actually derived, the
   output the connectome actually produced. If nothing happened, the panel
   shows nothing. It never invents. */
'use strict';

Object.assign(House, {
  initMind() {
    House.refreshMind();
    House.startMindCanvas();
    if (!House._brainMap && !House._brainMapTried) {
      House._brainMapTried = true;
      House.api('/api/neural/map').then(m => {
        if (m && m.present) House._brainMap = m;
      }).catch(() => {});
    }
  },

  ZONES: [
    ['ol',    0.50, 0.20, 0.36, 0.10, 'optic lobes'],
    ['mb',    0.28, 0.44, 0.095, 0.13, 'mushroom body'],
    ['cx',    0.68, 0.38, 0.095, 0.11, 'central complex'],
    ['proto', 0.48, 0.50, 0.11, 0.13, 'protocerebrum'],
    ['lp',    0.10, 0.55, 0.075, 0.10, 'lateral proto'],
    ['lh',    0.74, 0.62, 0.065, 0.08, 'lateral horn'],
    ['al',    0.44, 0.72, 0.065, 0.08, 'antennal lobe'],
    ['sez',   0.60, 0.82, 0.095, 0.055, 'SEZ'],
    ['vnc',   0.42, 0.93, 0.085, 0.07, 'nerve cord'],
    ['other', 0.88, 0.85, 0.075, 0.075, 'assoc'],
  ],

  startMindCanvas() {
    const cv = House.byId('mind-canvas');
    if (!cv || House._mindRaf) return;
    House._poolAct = House._poolAct || new Float32Array(24);
    const ctx = cv.getContext('2d');
    const draw = () => {
      House._mindRaf = requestAnimationFrame(draw);
      const W = cv.width, H = cv.height;
      ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < House._poolAct.length; i++)
        House._poolAct[i] *= 0.985;
      House._mbBoost = (House._mbBoost || 0) * 0.985;
      const map = House._brainMap;
      const t = performance.now() / 1000;
      if (map && map.pools) {
        const counts = map.zones || {};
        const maxCount = Math.max(1,
          ...Object.values(counts).map(v => v || 0));
        House.ZONES.forEach(([key, fx, fy, frx, fry, label], zi) => {
          const count = counts[key] || 0;
          if (!count) return;
          let act = 0;
          map.pools.forEach((dist, p) => {
            act += (House._poolAct[p] || 0) * (dist[key] || 0);
          });
          if (key === 'mb') act += (House._mbBoost || 0);
          act = Math.min(1, act);
          const breathe = 0.10 + 0.04 * Math.sin(t * 1.3 + zi * 1.7);
          const a = Math.min(1, breathe + act);
          const scale = 0.75 + 0.5 * Math.sqrt(count / maxCount);
          const wob = 1 + 0.05 * Math.sin(t * 0.9 + zi);
          const x = fx * W, y = fy * H;
          const rx = frx * W * scale * wob;
          const ry = fry * H * scale * wob;
          if (act > 0.12) {
            ctx.fillStyle = 'rgba(80,170,255,' + (act * 0.16).toFixed(3) + ')';
            ctx.beginPath();
            ctx.ellipse(x, y, rx * 1.45, ry * 1.45, 0, 0, 6.283);
            ctx.fill();
          }
          ctx.fillStyle = 'rgba(126,196,255,'
            + (0.10 + act * 0.55).toFixed(3) + ')';
          ctx.strokeStyle = 'rgba(126,196,255,'
            + (0.22 + act * 0.6).toFixed(3) + ')';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.ellipse(x, y, rx, ry, 0, 0, 6.283);
          ctx.fill();
          ctx.stroke();
          ctx.fillStyle = 'rgba(150,190,230,'
            + (0.55 + act * 0.45).toFixed(3) + ')';
          ctx.font = '8px monospace';
          ctx.textAlign = 'center';
          ctx.fillText(label + ' \u00b7 ' + House.num(count), x, y + ry + 9);
        });
        return;
      }
      // No fallback drawing. The old ring of twelve dots was a picture of
      // nothing: not the brain, not the pools' anatomy, and it rendered
      // underneath the real zones while the map was still loading. If the
      // anatomy has not arrived, say so instead of drawing something.
      ctx.fillStyle = 'rgba(150,170,190,0.45)';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('loading the anatomy', W / 2, H / 2);
    };
    draw();
  },

  async refreshMind() {
    if (this._mindAt && performance.now() - this._mindAt < 4000) return;
    this._mindAt = performance.now();
    const core = House.api('/api/neural/state').catch(() => null);
    const th = House.api('/api/thoughts?n=25').catch(() => null);
    const st = House.api('/api/state').catch(() => null);
    const ch = House.api('/api/chat_history').catch(() => null);
    const gr = House.api('/api/neural/growth').catch(() => null);
    const ev = House._lastEvtT == null
      ? Promise.resolve(null)
      : House.api('/api/language/stream?since=' + House._lastEvtT)
          .catch(() => null);
    const [ns, thoughts, state, chat, growth, stream] = await Promise.all(
      [core, th, st, ch, gr, ev]);
    if (stream && stream.events && stream.events.length) {
      House._poolAct = House._poolAct || new Float32Array(24);
      stream.events.forEach(e => {
        House._lastEvtT = Math.max(House._lastEvtT || 0, e.t || 0);
        if (e.kind === 'thought' && e.pool != null
            && e.pool >= 0 && e.pool < House._poolAct.length)
          House._poolAct[e.pool] = Math.min(1.2,
            (House._poolAct[e.pool] || 0) + 0.45);
      });
    } else if (House._lastEvtT == null) {
      House._lastEvtT = 0;
    }
    if (ns && ns.last_decision) {
      const sig = ns.last_decision.cells.join(',');
      if (sig !== House._lastCellSig) {
        House._lastCellSig = sig;
        House._mbBoost = Math.min(1, (House._mbBoost || 0) + 0.4);
      }
    }
    if (ns) House.renderMindCore(ns);
    if (ns) House.renderMindActivity(ns.recent_activity || []);
    if (thoughts) House.renderMindThoughts(thoughts.thoughts || []);
    House.renderMindOutput(state, chat, ns);
    if (growth) House.renderMindGrowth(growth);
  },

  renderMindGrowth(g) {
    const el = House.byId('mind-growth');
    if (!el) return;
    const s = g.growth || {};
    el.textContent = '';
    if (!s.graph_loaded) { el.textContent = 'carve not loaded'; return; }
    [['synapses grown since birth', s.changed_from_birth],
     ['strengthened', s.strengthened], ['weakened', s.weakened],
     ['consolidation replays', s.consolidations]].forEach(([k, v]) =>
      el.appendChild(House.el('div', { class: 'kv' },
        [House.el('b', { text: k }),
         House.el('span', { text: House.fmt(v) })])));
    const share = Object.entries(s.pool_weight_share || {})
      .sort((a, b) => b[1] - a[1]).slice(0, 4)
      .map(([p, v]) => 'p' + p + ':' + Math.round(v * 100) + '%').join(' ');
    if (share) el.appendChild(House.el('div', { class: 'small muted',
      text: 'where the brain has grown: ' + share }));
  },

  renderMindCore(ns) {
    if (ns.pools) House._mindPools = ns.pools;
    const el = House.byId('mind-core');
    if (el) el.textContent = ns.graph_loaded
      ? 'BANC carve live - ' + House.num(ns.neuron_count) + ' neurons, '
        + House.num(ns.synapse_count) + ' synapses'
      : 'carve not loaded';
    const n = House.byId('mind-neurons');
    if (n) {
      n.textContent = '';
      n.appendChild(House.el('span', { class: 'pill'
        + (ns.graph_loaded ? ' live' : ''), text:
        'pulses ' + House.num(ns.neural_ticks) }));
      n.appendChild(House.el('span', { class: 'pill', text:
        'drive ' + (ns.background_drive || '?') }));
      n.appendChild(House.el('span', { class: 'pill', text:
        'plastic ' + House.num(ns.plastic_synapses) }));
    }
  },

  renderMindActivity(rows) {
    House._poolAct = House._poolAct || new Float32Array(24);
    const fresh = rows.filter(r => (r.t || 0) > (House._lastPulseT || 0));
    if (fresh.length) {
      House._lastPulseT = Math.max(...fresh.map(r => r.t || 0));
      House._vmax = Math.max(House._vmax || 0.05,
        ...fresh.map(r => r.valuation_max || 0), 0.05);
      fresh.forEach(r => {
        const p = r.action | 0;
        if (p >= 0 && p < House._poolAct.length) {
          const rel = Math.min(1, (r.valuation_max || 0)
            / (House._vmax || 0.05));
          House._poolAct[p] = Math.min(1.2,
            (House._poolAct[p] || 0) + 0.35 + 0.65 * rel);
        }
      });
    }
    if (rows.length)
      House._mindPools = Math.max(House._mindPools || 12,
        1 + Math.max(...rows.map(r => r.action | 0)));
    const act = House.byId('mind-activity');
    if (act) {
      act.textContent = '';
      rows.slice().reverse().slice(0, 10).forEach(r => {
        const row = House.el('div', { class: 'mindrow' });
        row.appendChild(House.el('span', { class: 'small',
          text: new Date((r.t || 0) * 1000).toLocaleTimeString() }));
        row.appendChild(House.el('span', { class: 'small',
          text: 'pool ' + r.action + ' | v ' + r.valuation_max }));
        act.appendChild(row);
      });
      if (!rows.length) act.appendChild(House.el('div', { class: 'muted small',
        text: 'no pulses yet' }));
    }
  },

  renderMindThoughts(thoughts) {
    const box = House.byId('mind-thoughts');
    if (!box) return;
    box.textContent = '';
    thoughts.slice().reverse().forEach(t => {
      const row = House.el('div', { class: 'mindrow' });
      row.appendChild(House.el('span', { class: 'small muted',
        text: new Date((t.t || 0) * 1000).toLocaleTimeString() }));
      row.appendChild(House.el('span', { class: 'small',
        text: (t.text || '').slice(0, 140) }));
      box.appendChild(row);
    });
    if (!thoughts.length) box.appendChild(House.el('div', {
      class: 'muted small', text: 'the connectome has said nothing yet' }));
  },

  renderMindOutput(state, chat, ns) {
    const box = House.byId('mind-output');
    if (!box) return;
    box.textContent = '';
    const hist = (chat && chat.history) || (state && state.chat_history) || [];
    const last = hist.length && hist[hist.length - 1];
    if (last && last.role === 'assistant' && (last.content || '').trim()) {
      box.appendChild(House.el('div', { class: 'small',
        text: last.content.slice(0, 400) }));
    }
    const ld = ns && ns.last_decision;
    if (ld && ld.cells && ld.cells.length) {
      box.appendChild(House.el('div', { class: 'small muted',
        text: 'last pattern: ' + ld.n_cells + ' KC cells ['
          + ld.cells.join(', ') + '] -> pool ' + ld.pool }));
    }
    const lt = House.byId('mind-lived');
    if (lt) {
      const mind = (state || {}).mental || {};
      lt.textContent = 'words known as patterns: '
        + House.num(mind.language ? mind.language.vocabulary_size : 0)
        + ' | oracle: ' + (((state || {}).stats || {}).oracle || {}).mode;
    }
  }
});