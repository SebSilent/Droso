/* Config: the DNA, editable from the wall.
   Only changed, whitelisted knobs are sent, and the server refuses anything it
   does not know -- so the form cannot grow a stray key into the config file.
*/
'use strict';

Object.assign(House, {
  _cfg: null,

  async openConfig() {
    let cfg;
    try { cfg = await House.api('/api/config'); }
    catch (e) { alert('could not read config: ' + e.message); return; }
    House._cfg = cfg;
    const m = cfg.model || {};
    const b = m.api_budget || {};
    const sb = cfg.sandbox || {};
    const hb = cfg.heartbeat || {};
    const cn = cfg.connectome || {};
    const lg = cfg.language || {};
    const set = (id, v) => {
      const el = House.byId(id);
      if (!el) return;
      if (el.type === 'checkbox') el.checked = !!v;
      else if (v !== null && v !== undefined) el.value = v;
    };
    const sel = House.byId('config-provider');
    if (sel) {
      const choices = (cfg.provider_choices || []).length
        ? cfg.provider_choices
        : Array.from(sel.options).map(o => o.value);
      sel.textContent = '';
      choices.forEach(v => {
        const o = document.createElement('option');
        o.value = v; o.textContent = v;
        sel.appendChild(o);
      });
      if (m.provider) sel.value = m.provider;
    }
    set('config-base-url', m.base_url);
    set('config-model', m.name || m.model);
    set('key-state', m.api_key_present
      ? 'stored: ' + m.api_key + ' (mode: ' + (m.oracle_mode || '?') + ')'
      : 'none stored -- the oracle is blocked and will raise rather than answer');
    House.byId('config-api-key').value = '';
    set('budget-query', b.max_tokens_per_query);
    set('budget-task', b.max_tokens_per_task);
    set('budget-day', b.max_tokens_per_day);
    set('sb-enabled', sb.enabled);
    set('sb-network', sb.allow_network);
    set('sb-writes', sb.auto_approve_writes);
    set('hb-enabled', hb.enabled !== false);
    set('hb-interval', hb.think_interval);
    set('hb-sleep', hb.sleep_threshold);
    set('hb-research', hb.auto_research);
    set('cn-retries', cn.max_retries);
    set('cn-tokens', cn.max_tokens_per_task);
    set('cn-time', cn.max_time_per_task);
    set('cn-context', cn.max_context_tokens);
    set('cn-fast', (cn.fast_path || {}).enabled);
    set('lg-autotrain', lg.auto_train !== false);
    House.byId('config-modal').hidden = false;
  },

  closeConfig() { House.byId('config-modal').hidden = true; },

  gather() {
    const cfg = House._cfg || {};
    const m = cfg.model || {}, b = m.api_budget || {}, sb = cfg.sandbox || {},
          hb = cfg.heartbeat || {}, cn = cfg.connectome || {},
          lg = cfg.language || {};
    const want = {};
    const g = (id) => {
      const el = House.byId(id);
      if (!el) return null;
      return el.type === 'checkbox' ? el.checked
        : (el.type === 'number' ? (el.value === '' ? null : Number(el.value)) : el.value);
    };
    const cmp = (key, current, next, kind) => {
      if (next === null || next === undefined) return;
      if (kind === 'num' && Number(current) === Number(next)) return;
      if (kind === 'bool' && !!current === !!next) return;
      if (kind === 'str' && String(current || '') === String(next)) return;
      want[key] = next;
    };
    const model = g('config-model');
    if (model !== null && String(m.name || m.model || '') !== String(model)) {
      want['model.name'] = model;
      want['model.model'] = model;
    }
    cmp('model.provider', m.provider, g('config-provider'), 'str');
    cmp('model.base_url', m.base_url, g('config-base-url'), 'str');
    const key = g('config-api-key');
    if (key && key.trim()) want['model.api_key'] = key.trim();
    cmp('model.api_budget.max_tokens_per_query', b.max_tokens_per_query, g('budget-query'), 'num');
    cmp('model.api_budget.max_tokens_per_task', b.max_tokens_per_task, g('budget-task'), 'num');
    cmp('model.api_budget.max_tokens_per_day', b.max_tokens_per_day, g('budget-day'), 'num');
    cmp('sandbox.enabled', sb.enabled, g('sb-enabled'), 'bool');
    cmp('sandbox.allow_network', sb.allow_network, g('sb-network'), 'bool');
    cmp('sandbox.auto_approve_writes', sb.auto_approve_writes, g('sb-writes'), 'bool');
    cmp('heartbeat.enabled', hb.enabled !== false, g('hb-enabled'), 'bool');
    cmp('heartbeat.think_interval', hb.think_interval, g('hb-interval'), 'num');
    cmp('heartbeat.sleep_threshold', hb.sleep_threshold, g('hb-sleep'), 'num');
    cmp('heartbeat.auto_research', hb.auto_research, g('hb-research'), 'bool');
    cmp('connectome.max_retries', cn.max_retries, g('cn-retries'), 'num');
    cmp('connectome.max_tokens_per_task', cn.max_tokens_per_task, g('cn-tokens'), 'num');
    cmp('connectome.max_time_per_task', cn.max_time_per_task, g('cn-time'), 'num');
    cmp('connectome.max_context_tokens', cn.max_context_tokens, g('cn-context'), 'num');
    cmp('connectome.fast_path.enabled', (cn.fast_path || {}).enabled, g('cn-fast'), 'bool');
    cmp('language.auto_train', lg.auto_train !== false, g('lg-autotrain'), 'bool');
    return want;
  },

  async saveConfig() {
    const patch = House.gather();
    const msg = House.byId('config-msg');
    if (!Object.keys(patch).length) {
      msg.textContent = 'nothing changed.';
      msg.className = 'small muted';
      return;
    }
    if (patch['heartbeat.auto_research'] === true &&
        !confirm('auto-research lets the heartbeat run queued tasks on a timer. ' +
                 'If the oracle is live, that spends money without a human in the ' +
                 'loop. Continue?')) {
      delete patch['heartbeat.auto_research'];
    }
    if (patch['sandbox.allow_network'] === true &&
        !confirm('Allowing the network lets commands the connectome runs reach ' +
                 'outside this machine. Continue?')) {
      delete patch['sandbox.allow_network'];
    }
    if ((patch['model.api_key'] || patch['autotraining.api_key']) &&
        !confirm('Store this key in your user profile\'s application-data '
                 + 'directory (outside the project, never in the repo)? '
                 + 'Continue?')) {
      delete patch['model.api_key'];
      delete patch['autotraining.api_key'];
    }
    msg.textContent = 'saving ' + Object.keys(patch).length + ' knob(s)...';
    let r;
    try { r = await House.post('/api/config/update', { config: patch }); }
    catch (e) { msg.textContent = 'refused: ' + e.message; msg.className = 'small bad'; return; }
    const bits = [];
    bits.push('applied ' + Object.keys(r.applied || {}).length);
    if ((r.refused || []).length) bits.push('refused ' + r.refused.join(', '));
    if (!r.saved_to_disk) bits.push('NOT SAVED TO DISK (in memory only)');
    (r.warnings || []).forEach(w => bits.push('warning: ' + w));
    msg.textContent = bits.join(' · ');
    msg.className = 'small ' + (r.success && !(r.refused || []).length ? 'ok' : 'warn');
    House.byId('key-state').textContent = 'a stored key is never sent back to this page';
    House.byId('config-api-key').value = '';
    House.pollState();
  }
});

document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !House.byId('config-modal').hidden) House.closeConfig();
  });
});