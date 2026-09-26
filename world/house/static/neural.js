/* The always-alive neural core: what the carved graph is, and what it did.
   Every number here is measured -- graph facts come from the carve's own meta,
   activity rows are what the heartbeat's pulses actually propagated, and the
   lived-time ledger is cumulative simulated neural time. A pulse row is not a
   metaphor: it is one 50 ms episode through 12,867 neurons. */
'use strict';

Object.assign(House, {
  initNeural() {
    House.refreshNeural();
  },

  async refreshNeural() {
    let s;
    try { s = await House.api('/api/neural/state'); }
    catch (e) {
      const box = House.byId('neural-substrate');
      if (box) box.textContent = 'neural state unreadable: ' + e.message;
      return;
    }
    House.renderNeural(s);
  },

  renderNeural(s) {
    const sub = House.byId('neural-substrate');
    if (sub) {
      sub.textContent = '';
      sub.appendChild(House.el('div', { class: s.graph_loaded ? 'ok' : 'warn',
        text: s.graph_loaded
          ? 'carved BANC graph loaded and propagating'
          : 'carved graph NOT loaded (connectome.use_banc_graph false, or data '
          + 'files absent): only the grown colony is running' }));
      [
        ['neurons', House.num(s.neuron_count)],
        ['static synapses', House.num(s.synapse_count)],
        ['plastic KC->MBON synapses', House.num(s.plastic_synapses)],
        ['heartbeat pulses', House.num(s.neural_ticks)],
        ['pulse interval', s.interval_s != null ? s.interval_s + ' s' : '?'],
        ['drive mode', s.background_drive || '?'],
        ['engine static_pass', String(s.engine_static_pass)],
      ].forEach(([k, v]) => sub.appendChild(House.el('div', { class: 'kv' },
        [House.el('b', { text: k }), House.el('span', { text: String(v) })])));
      if (s.last_error) sub.appendChild(House.el('div', { class: 'bad small',
        text: 'last pulse error: ' + s.last_error }));
    }

    const lt = s.lived_time || {};
    const lived = House.byId('neural-lived');
    if (lived) {
      lived.textContent = '';
      [
        ['decisions simulated', House.num(lt.decisions)],
        ['neural time', (lt.total_neural_seconds != null
          ? House.num(lt.total_neural_seconds) + ' s' : '?')],
        ['in hours', lt.neural_hours != null ? House.num(lt.neural_hours) : '?'],
        ['neuron-update events', lt.neuron_update_events != null
          ? lt.neuron_update_events.toExponential(2) : '?'],
        ['fly-days equivalent', lt.fly_days_equivalent],
      ].forEach(([k, v]) => lived.appendChild(House.el('div', { class: 'kv' },
        [House.el('b', { text: k }), House.el('span', { text: String(v) })])));
      const note = House.byId('neural-lived-note');
      if (note) note.textContent = s.lived_time_path
        ? '(ledger: ' + s.lived_time_path + ')' : '';
    }

    const rows = s.recent_activity || [];
    const spark = House.byId('neural-spark');
    if (spark) {
      spark.textContent = '';
      const maxN = Math.max(1, ...rows.map(r => r.neurons_driven || 0));
      rows.forEach(r => spark.appendChild(House.el('span', {
        class: 'sparkbar' + ((r.active_neurons || 0) > 0 ? ' hot' : ''),
        style: 'height:' + Math.max(8, Math.round(100 *
          (r.neurons_driven || 0) / maxN)) + '%',
        title: 'pool ' + r.action + ', drove ' + (r.neurons_driven || 0) +
          ' KCs, max valuation ' + (r.valuation_max || 0) })));
      if (!rows.length) spark.appendChild(House.el('span', { class: 'muted',
        text: 'no pulses yet' }));
    }
    const dn = House.byId('neural-drive-note');
    if (dn) dn.textContent = s.background_drive
      ? '(drive mode: ' + s.background_drive + ')' : '';

    const list = House.byId('neural-activity');
    if (list) {
      list.textContent = '';
      rows.slice().reverse().forEach(r => {
        const row = House.el('div', { class: 'row' });
        row.appendChild(House.el('span', { class: 'small muted',
          text: new Date((r.t || 0) * 1000).toLocaleTimeString() }));
        row.appendChild(House.el('b', { text: 'pool ' + r.action }));
        row.appendChild(House.el('span', { class: 'small',
          text: 'max v ' + r.valuation_max + ', drove ' +
            (r.neurons_driven || 0) + ' KCs' }));
        row.appendChild(House.el('span', { class: 'small muted',
          text: r.drive || '' }));
        list.appendChild(row);
      });
      if (!rows.length) list.appendChild(House.el('div', { class: 'muted',
        text: 'no pulses yet' }));
    }
  }
});