/* Organs: the anatomy panel.
   Every card says whether the organ is present, active, disabled or broken --
   four different states that a single "offline" label would collapse into a lie.
*/
'use strict';

Object.assign(House, {
  _openOrgans: new Set(),
  _organFilter: '',

  async refreshOrgans() {
    let organs;
    try { organs = await House.api('/api/organs'); }
    catch (e) { return; }
    House.organCache = organs;
    const list = House.byId('organs-list');
    if (!list) return;
    const groups = {};
    Object.keys(organs).sort().forEach(name => {
      const o = organs[name] || {};
      const g = o.group || 'other';
      (groups[g] = groups[g] || []).push([name, o]);
    });
    list.textContent = '';
    const order = ['consciousness', 'thought', 'knowledge', 'memory', 'economy',
                   'safety', 'hands', 'muscles', 'other'];
    order.filter(g => groups[g]).forEach(g => {
      const head = House.el('div', { class: 'organ-group-head',
        text: g.toUpperCase() });
      head.style.cssText = 'grid-column:1/-1;color:var(--muted);font:11px var(--mono);' +
        'letter-spacing:.8px;margin:12px 0 2px';
      list.appendChild(head);
      groups[g].forEach(([name, o]) => {
        if (House._organFilter &&
            !(name + ' ' + (o.label || '')).toLowerCase().includes(House._organFilter))
          return;
        list.appendChild(House.organCard(name, o));
      });
    });
    const n = Object.keys(organs).length;
    const live = Object.values(organs).filter(o => o.status === 'active').length;
    House.byId('organ-count').textContent = live + ' active / ' + n + ' known';
  },

  organCard(name, o) {
    const card = House.el('div', {
      class: 'organ ' + (o.status || '') + (House._openOrgans.has(name) ? ' open' : '')
    });
    const head = House.el('div', { class: 'organ-header' });
    head.appendChild(House.el('span', { class: 'organ-name', text: o.label || name }));
    head.appendChild(House.el('span', { class: 'organ-status ' + (o.status || ''),
      text: o.status_name || o.status || '?' }));
    head.appendChild(House.el('span', { class: 'organ-group', text: name }));
    const tog = House.el('button', {
      class: 'ghost organ-toggle',
      text: o.status === 'disabled' ? 'on' : 'off',
      title: 'Disabling hides the organ and stops its timer; only the switches the ' +
             'loop actually reads change reasoning behaviour.',
      onclick: async (e) => {
        e.stopPropagation();
        try {
          const r = await House.post('/api/organ/toggle',
            { organ: name, enabled: o.status === 'disabled' });
          if (r.note) tog.title = r.note;
          House.refreshOrgans();
        } catch (err) { tog.textContent = 'refused'; tog.title = err.message; }
      }
    });
    head.appendChild(tog);
    head.addEventListener('click', () => {
      if (House._openOrgans.has(name)) House._openOrgans.delete(name);
      else House._openOrgans.add(name);
      card.classList.toggle('open');
      if (card.classList.contains('open') && !card.querySelector('.kv')) {
        House.kvRows(o.stats || o).forEach(r => card.querySelector('.organ-body').appendChild(r));
      }
    });
    card.appendChild(head);
    const body = House.el('div', { class: 'organ-body' });
    if (o.note) body.appendChild(House.el('div', { class: 'small', text: o.note }));
    if (!o.stats) {
      body.appendChild(House.el('div', { class: 'small', text: 'no stats() exposed' }));
    }
    card.appendChild(body);
    const hits = House.headline(name, o.stats || {});
    if (hits.length) {
      const strip = House.el('div', { class: 'kv', style: 'border-top:1px solid var(--line)' });
      hits.forEach(h => strip.appendChild(House.el('span', { text: h, style: 'margin-right:10px' })));
      card.appendChild(strip);
    }
    return card;
  },

  headline(name, s) {
    const g = (k) => s[k] !== undefined ? s[k] : null;
    switch (name) {
      case 'api_oracle': return ['mode ' + g('mode'), 'calls ' + House.fmt(g('calls')),
        'credential ' + (g('has_key') ? 'stored' : 'NONE'), 'tokens est ' + House.fmt(g('tokens_prompt_est'))];
      case 'query_cache': return ['entries ' + House.fmt(g('entries')),
        'hits ' + House.fmt(g('hits')), 'rate ' + House.fmt(g('hit_rate'))];
      case 'local_solver': return ['solved ' + House.fmt(g('solved')),
        'refused ' + House.fmt(g('refused')), 'rate ' + House.fmt(g('solve_rate'))];
      case 'token_optimizer': return ['tasks ' + House.fmt(g('tasks')),
        'no-api ' + House.fmt(g('solved_without_api')),
        'saved est ' + House.fmt(g('tokens_not_spent_est'))];
      case 'learning_loop': return ['procedures ' + House.fmt(g('procedures')),
        'verified ' + House.fmt(g('verified_procedures')),
        'reuses ' + House.fmt(g('reuses'))];
      case 'sandbox': return ['blocked ' + House.fmt(g('blocked')),
        'pending ' + House.fmt(g('pending_approvals')),
        'writes ' + House.fmt(g('files_written'))];
      case 'fast_router': return ['runs ' + House.fmt(g('runs')),
        'fell through ' + House.fmt(g('fell_through'))];
      case 'circuit_breaker': return [g('state') + '',
        'trips ' + House.fmt(g('trips')), 'escalations ' + House.fmt(g('escalations'))];
      case 'context_manager': return ['budget ' + House.fmt(g('budget')),
        'last ' + House.fmt(g('last_tokens_est')),
        'dropped ' + House.fmt(g('dropped_parts'))];
      case 'heartbeat': return [g('state') + '', 'ticks ' + House.fmt(g('ticks'))];
      case 'autotraining': return [];
      case 'language': return ['words ' + House.fmt(g('vocabulary_size')),
        g('can_speak') ? 'CAN SPEAK' : 'silent'];
      case 'neural_growth': { const gw = g('growth') || {};
        return ['ticks ' + House.fmt(g('growth_ticks')),
          'grown ' + House.fmt(gw.changed_from_birth) + '/'
            + House.fmt(gw.plastic_synapses) + ' synapses',
          'replays ' + House.fmt(gw.consolidations)]; }
      default: return [];
    }
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const f = House.byId('organ-filter');
  if (f) f.addEventListener('input', () => {
    House._organFilter = f.value.trim().toLowerCase();
    House.refreshOrgans();
  });
});