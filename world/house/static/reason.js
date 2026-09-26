/* Reasoning panel: give it a task, watch it search, see what got kept and why.

   Everything here was previously reachable only from the command line. The loop,
   the 620-procedure library, the oracle and the curriculum all worked and none of
   them appeared anywhere a human could look at them, so the dashboard showed a
   connectome babbling while a verified library sat unused behind it. This panel is
   the difference between the being having capabilities and the being appearing to.

   Two deliberate choices in the UI, both about not overclaiming:

   The check box is required. The gate is the task's own assertions, so a task with
   no check is a task that cannot be verified, and nothing unverified is ever kept.
   The house refuses those requests rather than returning something that looks
   solved and is not, and this says so before you press the button.

   A flat error trend on the outcome head is not a failure and is not drawn as one.
   If the same action sometimes passes and sometimes fails, chance is the best any
   predictor can do and the error sits there. The number worth watching is the
   trend on tasks that are actually learnable.
*/
'use strict';

Object.assign(House, {
  initReason() {
    const b = House.byId('reason-solve');
    if (b) b.addEventListener('click', () => House.solveReason());
    const r = House.byId('reason-refresh');
    if (r) r.addEventListener('click', () => House.refreshReason());
    document.querySelectorAll('#harness-subtabs .stab').forEach(x =>
      x.addEventListener('click', () => House.showHarnessSub(x.dataset.hsub)));
    House.showHarnessSub(House._hsub || 'reason');
  },

  showHarnessSub() {
    // The harness is ONE view now -- ask, work and instruments side by side with
    // the console across the bottom -- so there is nothing to switch. Kept as a
    // no-op because app.js calls it when the tab comes forward, and what it should
    // do there is refresh the instruments rather than hide two thirds of the page.
    House.refreshReason && House.refreshReason();
    House.refreshFiles && House.refreshFiles();
  },

  _rSet(id, v) {
    const el = House.byId(id);
    if (el) el.textContent = (v === null || v === undefined) ? '?' : String(v);
  },

  async refreshReason() {
    let s;
    try { s = await House.api('/api/reasoning/state'); }
    catch (e) { return; }
    const loop = s.loop || {};
    const head = loop.outcome_head || {};
    House._rSet('rs-episodes', loop.episodes);
    House._rSet('rs-attempts', loop.attempts);
    House._rSet('rs-solved', loop.solved);
    House._rSet('rs-tried', loop.candidates_tried);
    House._rSet('rs-engine', loop.engine_wired ? 'yes' : 'no');
    House._rSet('oh-updates', head.updates);
    House._rSet('oh-first', head.mean_error_first_10);
    House._rSet('oh-last', head.mean_error_last_10);
    House._rSet('oh-trend', head.trending_down === null ? '?' :
      (head.trending_down ? 'yes' : 'no'));
    const oh = House.byId('oh-trend');
    if (oh) oh.style.color = head.trending_down ? 'var(--ok, #7bd88f)' : '';

    const lib = s.library || {};
    House._rSet('lib-total', lib.procedures);
    House._rSet('lib-trusted', lib.trusted);
    const ev = House.byId('lib-evidence');
    if (ev) {
      ev.textContent = '';
      const rows = Object.entries(lib.evidence || {})
        .sort((a, b) => b[1] - a[1]);
      rows.forEach(([k, v]) => {
        const d = document.createElement('div');
        d.className = 'chip';
        const kk = document.createElement('span');
        kk.className = 'k';
        kk.textContent = k || 'none';
        const vv = document.createElement('span');
        vv.className = 'v';
        vv.textContent = v;
        d.appendChild(kk); d.appendChild(vv);
        ev.appendChild(d);
      });
    }

    const o = s.oracle || {};
    House._rSet('orc-provider', o.provider);
    House._rSet('orc-model', o.model);
    House._rSet('orc-mode', o.mode);
    House._rSet('orc-key', o.key ? 'configured' : 'none');

    const c = s.curriculum || {};
    const sp = c.splits || {};
    House._rSet('cur-total', c.total);
    House._rSet('cur-train', sp.train);
    House._rSet('cur-hold', sp.holdout);
    House._rSet('cur-gold', c.with_gold);

    const rd = s.reader || {};
    House._rSet('rd-started', rd.started ? 'yes' : 'no');
    House._rSet('rd-vocab', rd.vocabulary);
    House._rSet('rd-rate', (rd.last_run || {}).lines_per_second);

    House.renderAsks();

    const st = House.byId('reason-loop-state');
    if (st) {
      st.textContent = s.loop_present ? '' :
        ('no reasoning loop on this agent' +
         (s.loop_error ? ': ' + s.loop_error : ''));
    }
  },

  async solveReason() {
    const out = House.byId('reason-result');
    const task = ((House.byId('reason-task') || {}).value || '').trim();
    const check = ((House.byId('reason-check') || {}).value || '').trim();
    if (!out) return;
    out.textContent = '';
    if (!task) { out.textContent = 'a task needs words'; return; }
    if (!check) {
      out.textContent = 'no check: the assertions are the only gate, and ' +
        'nothing unverified is ever kept. Add one.';
      return;
    }
    out.textContent = 'searching…';
    let r;
    try { r = await House.post('/api/reasoning/solve', { task, check }); }
    catch (e) { out.textContent = 'refused by the house: ' + e.message; return; }
    House.rememberAsk(task, check, r);
    House.renderReasonResult(r);
    try {
      const st = await House.api('/api/reasoning/state');
      House.renderEpisode(((st || {}).loop || {}).recent || []);
    } catch (e) {}
    House.refreshReason();
  },

  /* What you have asked before. Real content in the space the prose used to take,
     and useful: a harness you cannot re-run from is a demo. */
  rememberAsk(task, check, r) {
    let asks = [];
    try { asks = JSON.parse(localStorage.getItem('droso.asks') || '[]'); } catch (e) {}
    asks = asks.filter(x => x.task !== task);
    asks.unshift({ task: task, check: check,
                   outcome: (r || {}).outcome || (r && r.ok ? 'solved' : 'refused') });
    try { localStorage.setItem('droso.asks', JSON.stringify(asks.slice(0, 8))); } catch (e) {}
    House.renderAsks();
  },

  renderAsks() {
    const box = House.byId('reason-recent');
    if (!box) return;
    let asks = [];
    try { asks = JSON.parse(localStorage.getItem('droso.asks') || '[]'); } catch (e) {}
    box.textContent = '';
    if (!asks.length) return;
    asks.forEach(a => {
      const c = House.el('button', { class: 'chip', title: a.task });
      const k = House.el('span', { class: 'k', text: a.outcome === 'solved' ? 'solved' : 'refused' });
      const v = House.el('span', { class: 'v',
        text: a.task.length > 34 ? a.task.slice(0, 34) + '…' : a.task });
      c.appendChild(k); c.appendChild(v);
      c.addEventListener('click', () => {
        House.byId('reason-task').value = a.task;
        House.byId('reason-check').value = a.check;
        House.byId('reason-task').focus();
      });
      box.appendChild(c);
    });
  },

  /* The part that makes this the connectome's harness and not a code runner.
     Every attempt goes through engine.decide() BEFORE it is executed -- that call
     is what sets the eligibility trace three-factor plasticity needs -- so the
     pool each candidate was routed to is real state, not decoration, and the
     reward prediction error is what teach() was given. Showing them beside the
     sandbox verdict is the difference between watching code run and watching a
     brain pick something and learn from how it went. */
  renderEpisode(trace) {
    const out = House.byId('reason-result');
    if (!out || !trace.length) return;
    const head = House.el('div', { class: 'small muted',
      text: 'trace · what the carve picked, and what it learned from it' });
    out.appendChild(head);
    trace.slice(-5).reverse().forEach(t => {
      const box = House.el('div', { class: 'episode' });
      const row = (n, v, cls) => {
        const d = House.el('div', { class: 'step' });
        d.appendChild(House.el('span', { class: 'n', text: n }));
        const val = House.el('span', { class: cls || '', text: v });
        d.appendChild(val);
        box.appendChild(d);
        return val;
      };
      row('candidate', String(t.label || '?'));
      row('head said', 'p(pass) = ' + (t.pred === undefined ? '?' : t.pred)
        + '   ranked ' + (t.rank === undefined ? '?' : t.rank));
      row('carve chose pool', (t.decided_pool === null || t.decided_pool === undefined)
        ? 'not routed' : String(t.decided_pool), 'pool');
      row('execution', t.passed ? 'passed its assertions' : 'failed',
        t.passed ? 'badge-ok' : 'badge-no');
      if (t.rpe !== undefined) {
        row('prediction error', (t.rpe > 0 ? '+' : '') + t.rpe
          + '  → teach()', t.rpe > 0 ? 'badge-ok' : 'badge-no');
      }
      if (!t.passed && t.why) row('why', String(t.why).slice(0, 120));
      out.appendChild(box);
    });
  },

  renderReasonResult(r) {
    const out = House.byId('reason-result');
    if (!out) return;
    out.textContent = '';
    const line = (txt, cls) => {
      const d = document.createElement('div');
      d.className = cls || 'small';
      d.textContent = txt;
      out.appendChild(d);
      return d;
    };
    const outcome = r.outcome || (r.ok ? 'solved' : 'refused');
    line((r.ok ? 'SOLVED' : 'REFUSED') + '  ·  ' + outcome, 'chip');
    if (r.candidate) line('candidate: ' + r.candidate);
    if (r.attempts !== undefined) line('attempts: ' + r.attempts);
    if (r.candidates !== undefined) line('candidates generated: ' + r.candidates);
    if (r.best_pred !== undefined) {
      line('predicted chance of passing: ' + r.best_pred +
           (r.attempt && r.attempt.pred !== undefined
             ? '  (the one tried was ' + r.attempt.pred + ')' : ''));
    }
    if (r.attempt) {
      if (r.attempt.passed) line('it passed its own assertions', 'small');
      else if (r.attempt.why) line('why it failed: ' + r.attempt.why, 'small');
      if (r.attempt.rpe !== undefined) {
        line('reward prediction error: ' + r.attempt.rpe +
             '  (what he expected vs what happened)', 'small');
      }
    }
    if (r.stored) line('kept: stored as a task_check procedure', 'small');
    else if (r.ok) line('not stored (holdout slice, or learning off)', 'small');
    if (r.reason) line('reason: ' + r.reason, 'small');
    if (r.escalate) line('nothing plausible left, so it refused rather than ' +
      'promoting the least-bad attempt', 'small muted');
  },
});
