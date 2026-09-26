/* Terminal: the muscles, and the fence in front of them.
   This panel never runs a command directly. It asks, the fence answers with
   allow / block / pending, and a pending answer gets buttons, not a hang.
*/
'use strict';

Object.assign(House, {
  _hist: [], _histAt: 0,

  initTerminal() {
    const run = House.byId('terminal-run');
    const input = House.byId('terminal-input');
    if (!run || !input) return;
    try { House._hist = JSON.parse(localStorage.getItem('droso.hist') || '[]'); }
    catch (e) { House._hist = []; }
    House._histAt = House._hist.length;
    const go = () => House.runCommand(input.value);
    run.addEventListener('click', go);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); go(); return; }
      // shell history, because a console you cannot re-run from is a log box
      if (e.key === 'ArrowUp' && House._hist.length) {
        e.preventDefault();
        House._histAt = Math.max(0, House._histAt - 1);
        input.value = House._hist[House._histAt] || '';
        input.setSelectionRange(input.value.length, input.value.length);
      }
      if (e.key === 'ArrowDown' && House._hist.length) {
        e.preventDefault();
        House._histAt = Math.min(House._hist.length, House._histAt + 1);
        input.value = House._hist[House._histAt] || '';
      }
    });
    House.consoleLine('meta', 'console ready · every command goes to the '
      + 'fence first · up/down for history · "clear" to wipe');
  },

  consoleLine(kind, text) {
    const out = House.byId('terminal-output');
    if (!out) return;
    if (!out.classList.contains('console')) out.classList.add('console');
    const map = { cmd: 'cl cl-in', ok: 'cl cl-out', err: 'cl cl-err',
                  meta: 'cl cl-meta', '': 'cl cl-out' };
    const d = House.el('div', { class: map[kind] !== undefined ? map[kind] : 'cl cl-out' });
    d.textContent = text;
    out.appendChild(d);
    out.scrollTop = out.scrollHeight;
    while (out.children.length > 500) out.removeChild(out.firstChild);
  },

  tline(cls, text) {
    // kept for the approval path and anything else that used the old call
    House.consoleLine(cls === 't-cmd' ? 'cmd' : cls === 't-block' ? 'err'
      : cls === 't-ok' ? 'ok' : cls === 'muted' ? 'meta' : '', text);
  },

  async runCommand(cmd) {
    cmd = (cmd || '').trim();
    if (!cmd) return;
    const input = House.byId('terminal-input');
    if (input) input.value = '';
    if (cmd === 'clear') {
      const out = House.byId('terminal-output');
      if (out) out.textContent = '';
      return;
    }
    House._hist.push(cmd);
    House._histAt = House._hist.length;
    try { localStorage.setItem('droso.hist', JSON.stringify(House._hist.slice(-60))); } catch (e) {}
    const at = new Date();
    const hhmmss = at.toTimeString().slice(0, 8);
    House.consoleLine('cmd', hhmmss + '  $ ' + cmd);
    const t0 = performance.now();
    let r;
    try {
      r = await House.post('/api/terminal', { command: cmd });
    } catch (e) {
      House.consoleLine('err', '        ' + e.message);
      return;
    }
    const ms = Math.round(performance.now() - t0);
    if (r.pending_approval) {
      House.consoleLine('meta', '        PENDING HUMAN APPROVAL -- '
        + (r.reason || 'a destructive action needs a grant'));
      House.refreshSafety && House.refreshSafety();
      return;
    }
    const code = r.returncode !== undefined ? r.returncode : r.exit_code;
    const ok = r.success !== false && (code === undefined || code === 0);
    if (!ok && (r.error || r.reason) && (r.output === undefined && r.stdout === undefined)) {
      House.consoleLine('err', '        ' + (r.error || r.reason));
      return;
    }
    House.consoleLine('meta', '        exit '
      + (code === undefined ? '?' : code) + (r.timed_out ? ' (timed out)' : '')
      + '  in ' + ms + ' ms');
    const body = String(r.output !== undefined ? r.output : (r.stdout || ''));
    const lines = body.replace(/\s+$/, '').split('\n');
    if (lines.length && lines[0] !== '') {
      lines.slice(0, 200).forEach(l => House.consoleLine(ok ? 'ok' : 'err', '  ' + l));
    } else {
      House.consoleLine('meta', '        (no output)');
    }
  },

  /* ── approvals, rendered wherever the pending list is shown ── */
  renderApprovals(pending, auditPending) {
    const box = House.byId('approvals');
    if (!box) return;
    const rows = (pending && pending.length ? pending : auditPending) || [];
    box.textContent = '';
    if (!rows.length) {
      box.appendChild(House.el('div', { class: 'muted small',
        text: 'nothing waiting' }));
      return;
    }
    rows.slice(0, 8).forEach((p, i) => {
      const what = p.what || p.action || p.reason || 'action';
      const row = House.el('div', { class: 'appr' });
      row.appendChild(House.el('span', { class: 'what', text: what }));
      const answer = async (approved, btn) => {
        btn.disabled = true;
        try {
          await House.post('/api/sandbox_answer', { matches: what, approved: approved });
          House.refreshSafety && House.refreshSafety();
          House.pollState && House.pollState();
        } catch (e) {
          btn.disabled = false;
          row.appendChild(House.el('span', { class: 'small bad', text: e.message }));
        }
      };
      const ok = House.el('button', { class: 'approve', text: 'grant once' });
      ok.addEventListener('click', () => answer(true, ok));
      const no = House.el('button', { class: 'deny', text: 'deny' });
      no.addEventListener('click', () => answer(false, no));
      row.appendChild(ok);
      row.appendChild(no);
      box.appendChild(row);
    });
    box.appendChild(House.el('div', { class: 'small muted',
      text: 'a grant covers one action; deletes always need one' }));
  }
});