/* Learning + safety panels: what the connectome knows, and what stops it.
   Both are read-only views over organ state, with one exception: the research
   button, which spends tokens on purpose because a human pressed it.
*/
'use strict';

Object.assign(House, {
  _learnFilter: '',

  initLearning() {
    const f = House.byId('learn-filter');
    if (f) f.addEventListener('input', () => {
      House._learnFilter = f.value.trim();
      House.refreshLearning();
    });
  },

  async refreshLearning() {
    const q = encodeURIComponent(House._learnFilter || '');
    let m;
    try { m = await House.api('/api/memory?q=' + q + '&limit=14'); }
    catch (e) { return; }
    House.renderMemory(m || {});
  },

  renderMemory(m) {
    const ppl = House.byId('mem-people');
    if (ppl) {
      ppl.textContent = '';
      (m.people || []).forEach(p => {
        ppl.appendChild(House.el('div', {
          class: 'mem-person' + (p.in_room ? ' here' : '') }, [
          House.el('span', { class: 'p-name', text: p.name }),
          House.el('span', { class: 'p-kind', text: p.kind }),
          House.el('span', { class: 'p-stats',
            text: 'heard ' + House.num(p.heard) +
              ' · addressed ' + House.num(p.addressed) +
              (p.in_room ? ' · here' : ' · ' + House.num(p.ago_world_s) + 's') }),
        ]));
        ppl.appendChild(House.el('div', { class: 'mem-cells',
          text: 'kc ' + (p.kc_cells || []).join(', ') + ' · ' +
            House.num(p.kc_active) + ' cells · ' +
            House.num(p.semantic_wires) + ' wires' }));
        ppl.appendChild(House.el('div', { class: 'mem-cells',
          text: 'scent pn ' + (p.scent_cells || []).join(', ') +
            ' · attention ×' + House.fmt(p.salience) }));
        (p.associations || []).forEach(a => {
          ppl.appendChild(House.el('div', { class: 'mem-assoc' }, [
            House.el('span', { class: 'mem-tok', text: a.token }),
            House.el('span', { class: 'mem-w', text: House.fmt(a.weight) }),
          ]));
        });
        if (p.last_said) {
          ppl.appendChild(House.el('div', { class: 'p-said',
            text: '“' + p.last_said + '”' }));
        }
      });
      if (!(m.people || []).length) {
        ppl.appendChild(House.el('div', { class: 'muted small', text: 'nobody yet' }));
      }
    }

    const ab = House.byId('mem-assoc');
    const aq = House.byId('mem-assoc-q');
    if (ab) {
      ab.textContent = '';
      if (aq) aq.textContent = m.query ? '“' + m.query + '”' : '';
      (m.associations || []).forEach(a => {
        ab.appendChild(House.el('div', { class: 'mem-row' }, [
          House.el('span', { class: 'mem-tok', text: a.token }),
          House.el('span', { class: 'mem-kind', text: a.kind }),
          House.el('span', { class: 'mem-w', text: House.fmt(a.weight) }),
        ]));
      });
      if (!m.query) {
        ab.appendChild(House.el('div', { class: 'muted small', text: 'type a word or a name' }));
      } else if (!(m.associations || []).length) {
        ab.appendChild(House.el('div', { class: 'muted small', text: 'nothing wired to it' }));
      }
    }

    const nb = House.byId('mem-now');
    if (nb) {
      nb.textContent = '';
      (m.now || []).forEach(n => nb.appendChild(House.el('div', { class: 'mem-row' }, [
        House.el('span', { class: 'mem-tok', text: n.token }),
        House.el('span', { class: 'mem-kind', text: n.kind }),
        House.el('span', { class: 'mem-w', text: House.fmt(n.weight) }),
      ])));
      if (!(m.now || []).length) {
        nb.appendChild(House.el('div', { class: 'muted small', text: 'nothing lit' }));
      }
    }

    const pb = House.byId('mem-pools');
    const sy = House.byId('mem-syn');
    if (pb) {
      pb.textContent = '';
      const s = m.synapses || {};
      if (sy) sy.textContent =
        House.num(s.plastic_synapses) + ' synapses · ' +
        House.num(s.changed_from_birth) + ' changed · ' +
        House.num(s.semantic_wires) + ' wires · ' + House.num(s.words) + ' words';
      (m.pools || []).forEach(p => {
        pb.appendChild(House.el('div', { class: 'mem-pool' }, [
          House.el('span', { class: 'p-name', text: 'pool ' + p.pool }),
          House.el('span', { class: 'p-stats',
            text: House.num(p.words) + ' words' +
              (p.weight_share != null ? ' · ' + House.fmt(p.weight_share) + ' weight' : '') }),
        ]));
        if ((p.examples || []).length) {
          pb.appendChild(House.el('div', { class: 'mem-cells', text: p.examples.join(', ') }));
        }
      });
    }
  },

  row(obj, parts) {
    const r = House.el('div', { class: 'row' });
    r.appendChild(House.el('div', { class: 'head' }, [
      House.el('span', { text: String(parts[0] || '(untitled)').slice(0, 120) }),
      House.el('span', { class: 'tags', text: parts.slice(1).filter(Boolean).join(' · ') }),
    ]));
    const body = parts[2] || (typeof parts[0] === 'string' ? '' : JSON.stringify(obj).slice(0, 160));
    if (body) r.appendChild(House.el('div', { class: 'body', text: String(body).slice(0, 200) }));
    r.title = JSON.stringify(obj, null, 1).slice(0, 900);
    return r;
  },

  /* ── safety tab ───────────────────────────────────────────────────── */
  async refreshSafety() {
    const s = House.state || {};
    const c = s.consciousness || {};
    const st = s.stats || {};

    const ts = House.byId('thought-stream');
    if (ts) {
      ts.textContent = '';
      if (c.present === false) {
        ts.appendChild(House.el('div', { class: 'muted small', text: c.note || 'no heartbeat' }));
      }
      (c.recent_thoughts || []).slice().reverse().forEach(t => {
        ts.appendChild(House.el('div', { class: 'thought' }, [
          House.el('span', { class: 'kind', text: '[' + (t.kind || '?') + '] ' }),
          House.el('span', { text: t.text || '' }),
          House.el('span', { class: 'prov',
            text: '  ← ' + (t.provenance || []).join(',') + ' ' + House.ago(t.t) }),
        ]));
      });
      if (!(c.recent_thoughts || []).length && c.present !== false) {
        ts.appendChild(House.el('div', { class: 'muted small',
          text: 'nothing on the last beat' }));
      }
    }

    const gaps = House.byId('gaps-list');
    if (gaps) {
      gaps.textContent = '';
      const unmet = (c.knowledge_gaps || []).filter(g => g.kind === 'unmet');
      const known = (c.knowledge_gaps || []).filter(g => g.kind === 'known');
      if (!unmet.length && !known.length) {
        gaps.appendChild(House.el('div', { class: 'muted small',
          text: 'no gap has been recorded: every task so far was answered.' }));
      }
      unmet.concat(known).forEach(g => gaps.appendChild(House.el('div', { class: 'row' }, [
        House.el('div', { class: 'head' }, [
          House.el('span', { text: g.label }),
          House.el('span', { class: 'tags', text: g.count + ' · ' + (g.from || []).join(',') }),
        ]),
      ])));
      const q = (c.research_queue || []);
      if (q.length) {
        gaps.appendChild(House.el('h3', { text: 'queue', style: 'margin:8px 0 4px' }));
        q.forEach(item => {
          const r = House.el('div', { class: 'row' });
          r.appendChild(House.el('div', { class: 'head' }, [
            House.el('span', { text: String(item.task).slice(0, 90) }),
            House.el('span', { class: 'tags', text: item.reason }),
          ]));
          r.appendChild(House.el('button', {
            class: 'ghost', text: 'research now', style: 'margin-top:4px',
            title: 'Runs this through the connectome now. If the oracle is live, it costs tokens.',
            onclick: async (e) => {
              e.target.disabled = true;
              e.target.textContent = 'working...';
              try {
                const res = await House.post('/api/research', { task: item.task });
                e.target.textContent = res.success ? 'done' : 'failed';
                House.pollState();
              } catch (err) { e.target.textContent = 'refused'; e.target.title = err.message; }
            }
          }));
          gaps.appendChild(r);
        });
      }
      const sa = House.byId('self-assessment');
      if (sa) {
        sa.textContent = '';
        House.kvRows(c.self_assessment || {}, 1).forEach(n => sa.appendChild(n));
      }
    }

    const sb = House.byId('sandbox-box');
    if (sb) {
      sb.textContent = '';
      House.kvRows(st.sandbox || {}, 1).forEach(n => sb.appendChild(n));
      const pol = (st.sandbox && st.sandbox.policy) || {};
      Object.keys(pol).forEach(k => sb.appendChild(House.el('div', { class: 'kv',
        title: k }, [House.el('b', { text: 'policy.' + k }),
                     House.el('span', { text: House.fmt(pol[k]) })])));
    }

    const audit = House.byId('audit-log');
    if (audit) {
      audit.textContent = '';
      const a = s.sandbox || {};
      const cmds = (a.commands || a.recent_commands || []);
      if (!cmds.length) audit.appendChild(House.el('div', { class: 'muted small',
        text: 'no commands executed yet.' }));
      cmds.slice(-15).reverse().forEach(c => {
        const row = House.el('div', { class: 'row' });
        row.appendChild(House.el('div', { class: 'head' }, [
          House.el('span', { class: c.allow === false || c.blocked ? 'bad' : 'ok',
            text: (c.command || c.cmd || '?').slice(0, 110) }),
          House.el('span', { class: 'tags', text: House.ago(c.t || c.timestamp) }),
        ]));
        if (c.reason) row.appendChild(House.el('div', { class: 'body', text: c.reason }));
        audit.appendChild(row);
      });
    }

    const br = House.byId('breaker-box');
    if (br) {
      br.textContent = '';
      House.kvRows(st.circuit_breaker || st.breaker_stats || {}, 1).forEach(n => br.appendChild(n));
    }
    const rt = House.byId('router-box');
    if (rt) {
      rt.textContent = '';
      const fr = st.fast_route || {};
      House.kvRows({ decisions: fr.decisions, fell_through: fr.fell_through,
        fast_path_enabled: fr.fast_path_enabled,
        overhead_ms: fr.decision_overhead_ms }, 1).forEach(n => rt.appendChild(n));
      const med = fr.median_ms_by_path || {};
      Object.keys(med).forEach(k => {
        const v = med[k];
        rt.appendChild(House.el('div', { class: 'kv', title: k }, [
          House.el('b', { text: 'median ' + k }),
          House.el('span', { text: (v && typeof v === 'object')
            ? (House.fmt(v.measured_ms != null ? v.measured_ms : v.ms) +
               (v.samples ? ' ms (' + v.samples + ' samples, measured)' : ' ms'))
            : House.fmt(v) + ' ms' }),
        ]));
      });
      if (fr.code_shaped_tasks_never_bypass_verification !== undefined) {
        rt.appendChild(House.el('div', { class: 'small', text:
          'code-shaped tasks bypass verification: ' +
          (fr.code_shaped_tasks_never_bypass_verification ? 'NO (good)' : 'YES (bad)') }));
      }
    }
    House.renderGuarantee(st.guarantee);
  }
});