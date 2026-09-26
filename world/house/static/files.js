/* Files: the connectome's hands.
   The browser shows the tree the *fence* guards, and a save goes through
   organs/sandbox.py -- so an overwrite comes back as a refusal you can approve,
   never as a silent clobber.
*/
'use strict';

Object.assign(House, {
  _fileSel: null,
  _editing: false,

  initFiles() {
    House.byId('files-refresh').addEventListener('click', House.refreshFiles);
    House.byId('file-edit').addEventListener('click', () => House.setEditing(true));
    House.byId('file-cancel').addEventListener('click', () => House.setEditing(false));
    House.byId('file-save').addEventListener('click', House.saveFile);
    House.refreshFiles();
  },

  async refreshFiles() {
    let r;
    try { r = await House.api('/api/files?path=.'); }
    catch (e) { House.byId('file-note').textContent = 'listing refused: ' + e.message; return; }
    const tree = House.byId('file-tree');
    tree.textContent = '';
    (r.files || []).forEach(row => {
      const depth = (row.path.match(/[\/]/g) || []).length;
      const item = House.el('div', {
        class: 'f-item' + (row.connectome_touched ? ' touched' : '') +
               (House._fileSel === row.path ? ' sel' : ''),
        style: 'padding-left:' + (4 + depth * 9) + 'px',
        title: row.path + (row.connectome_touched ? '\nwritten inside the workzone' : ''),
        onclick: () => House.openFile(row.path)
      });
      const short = row.path.split('/').pop();
      item.appendChild(House.el('span', { text: short }));
      item.appendChild(House.el('span', { class: 'sz', text: House.bytes(row.size) }));
      tree.appendChild(item);
    });
    const note = House.byId('file-note');
    note.textContent = (r.count || 0) + ' files' +
      (r.truncated ? ' (truncated at ' + (r.count || 0) + ')' : '') +
      (r.skipped_large ? ' · ' + r.skipped_large + ' large/weight files skipped' : '');
    note.title = r.note || '';
  },

  bytes(n) {
    if (n == null) return '?';
    if (n < 1024) return n + 'b';
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + 'k';
    return (n / 1048576).toFixed(1) + 'M';
  },

  async openFile(path) {
    House._fileSel = path;
    House.setEditing(false);
    document.querySelectorAll('.f-item').forEach(n => n.classList.remove('sel'));
    House.refreshFiles();
    House.byId('file-path').textContent = path;
    const out = House.byId('file-content');
    out.textContent = 'reading...';
    try {
      const r = await House.api('/api/file?path=' + encodeURIComponent(path));
      if (r.error) {
        out.textContent = '';
        House.byId('file-msg').textContent = 'refused: ' + r.error;
        House.byId('file-edit').disabled = true;
        return;
      }
      out.textContent = r.content;
      House.byId('file-msg').textContent = r.truncated ? 'TRUNCATED' : '';
      House.byId('file-edit').disabled = false;
    } catch (e) {
      out.textContent = '';
      House.byId('file-msg').textContent = 'error: ' + e.message;
    }
  },

  setEditing(on) {
    House._editing = on;
    const ed = House.byId('file-editor');
    const view = House.byId('file-content');
    House.byId('file-edit').hidden = on;
    House.byId('file-save').hidden = !on;
    House.byId('file-cancel').hidden = !on;
    ed.hidden = !on;
    view.hidden = on;
    if (on) {
      ed.value = view.textContent;
      ed.focus();
      House.byId('file-msg').textContent =
        'Saving writes through the sandbox. Inside the workzone it lands; a project ' +
        'file overwrite needs your grant first.';
    }
  },

  async saveFile() {
    if (!House._fileSel) return;
    const content = House.byId('file-editor').value;
    let r;
    try {
      r = await House.post('/api/file/write',
        { path: House._fileSel, content: content, reason: 'house editor' });
    } catch (e) {
      House.byId('file-msg').textContent = 'write error: ' + e.message;
      return;
    }
    const msg = House.byId('file-msg');
    if (r.success) {
      msg.textContent = 'written ' + House._fileSel;
      msg.className = 'small ok';
      House.setEditing(false);
      House.byId('file-content').textContent = content;
      House.refreshFiles();
    } else {
      const pending = r.code === 'approval_required' || r.pending;
      msg.textContent = (pending ? 'awaiting your grant: ' : 'refused: ') +
        (r.error || r.reason || 'unknown');
      msg.className = 'small ' + (pending ? 'warn' : 'bad');
      House.refreshSafety && House.refreshSafety();
    }
  }
});