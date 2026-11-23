import {
  createRecord,
  exportBackup,
  fieldErrors,
  filterRecords,
  getRecord,
  importBackup,
  loadState,
  updateRecord,
} from './records.mjs';

const PLAN = window.APP_PLAN;
const storage = window.localStorage;

function qs(name) {
  return new URLSearchParams(location.search).get(name);
}

function fieldControl(field, value) {
  const current = value === undefined || value === null ? '' : String(value);
  if (field.type === 'enum') {
    const opts = ['<option value="">请选择</option>']
      .concat(field.options.map((opt) => `<option value="${escapeAttr(opt)}"${opt === current ? ' selected' : ''}>${escapeHtml(opt)}</option>`));
    return `<select name="${escapeAttr(field.id)}" id="${escapeAttr(field.id)}">${opts.join('')}</select>`;
  }
  if (field.type === 'boolean') {
    return `<select name="${escapeAttr(field.id)}" id="${escapeAttr(field.id)}">
      <option value="false"${current === 'true' ? '' : ' selected'}>否</option>
      <option value="true"${current === 'true' ? ' selected' : ''}>是</option>
    </select>`;
  }
  const type = field.type === 'number' ? 'number' : 'text';
  return `<input type="${type}" name="${escapeAttr(field.id)}" id="${escapeAttr(field.id)}" value="${escapeAttr(current)}">`;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

function escapeAttr(text) {
  return escapeHtml(text);
}

function showErrors(map) {
  for (const field of PLAN.fields) {
    const node = document.querySelector(`[data-error="${field.id}"]`);
    if (node) node.textContent = map[field.id] || '';
  }
}

function formValues(form) {
  const data = {};
  for (const field of PLAN.fields) {
    const input = form.elements[field.id];
    data[field.id] = input ? input.value : '';
  }
  return data;
}

function layoutClass() {
  return `layout-${PLAN.layout || 'adaptive'}`;
}

function unimplementedBlock() {
  const items = (PLAN.unimplemented || []).map((name) => `<li>${escapeHtml(name)}：未实现</li>`).join('');
  return `<aside class="notice" role="note"><p>以下能力未实现，页面不提供可点击入口：</p><ul>${items}</ul></aside>`;
}

function bindBackup(root) {
  root.querySelector('[data-export]')?.addEventListener('click', () => {
    const blob = new Blob([exportBackup(storage, PLAN)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${PLAN.appId}-backup.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
  root.querySelector('[data-import]')?.addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    const status = root.querySelector('[data-import-status]');
    if (!file) return;
    const text = await file.text();
    const result = importBackup(storage, PLAN, text);
    if (status) status.textContent = result.ok ? '导入成功，已保留导入前备份于内存校验过程' : `导入失败，未覆盖现有数据：${result.error}`;
    if (result.ok) render();
  });
}

function listPage(root) {
  const state = loadState(storage, PLAN);
  const query = root.querySelector('[name="q"]')?.value || '';
  const status = root.querySelector('[name="status"]')?.value || '';
  const rows = filterRecords(state, query, status, PLAN.statusField);
  const cells = PLAN.fields.map((field) => `<th>${escapeHtml(field.label)}</th>`).join('');
  const body = rows.map((item) => {
    const tds = PLAN.fields.map((field) => `<td>${escapeHtml(item[field.id] ?? '')}${item.example ? '<span class="example">示例</span>' : ''}</td>`).join('');
    return `<tr><td><a href="detail.html?id=${encodeURIComponent(item.id)}">${escapeHtml(item.id)}</a></td>${tds}<td><a href="edit.html?id=${encodeURIComponent(item.id)}">编辑</a></td></tr>`;
  }).join('');
  const cards = rows.map((item) => {
    const bits = PLAN.fields.map((field) => `<p><strong>${escapeHtml(field.label)}</strong> ${escapeHtml(item[field.id] ?? '')}</p>`).join('');
    return `<article class="card"><h2><a href="detail.html?id=${encodeURIComponent(item.id)}">${escapeHtml(item.id)}</a></h2>${bits}${item.example ? '<p class="example">示例数据，不是真实业务记录</p>' : ''}<p><a href="edit.html?id=${encodeURIComponent(item.id)}">编辑</a></p></article>`;
  }).join('');
  const statusFilter = PLAN.statusField
    ? `<label>状态 <select name="status"><option value="">全部</option>${(PLAN.fields.find((f) => f.id === PLAN.statusField).options || []).map((opt) => `<option${opt === status ? ' selected' : ''}>${escapeHtml(opt)}</option>`).join('')}</select></label>`
    : '';
  root.innerHTML = `
    <header><h1>${escapeHtml(PLAN.entity)}列表</h1><p>${escapeHtml(PLAN.actor)} · ${escapeHtml(PLAN.scene)} · 主操作：${escapeHtml(PLAN.primaryAction)}</p></header>
    ${unimplementedBlock()}
    <form data-filter class="toolbar">
      <label>筛选 <input name="q" value="${escapeAttr(query)}"></label>
      ${statusFilter}
      <button type="submit">筛选</button>
      <a href="edit.html">新增</a>
      <button type="button" data-export>导出备份</button>
      <label>导入备份 <input type="file" data-import accept="application/json"></label>
      <p data-import-status></p>
    </form>
    <div class="table-wrap"><table><thead><tr><th>编号</th>${cells}<th></th></tr></thead><tbody>${body || '<tr><td colspan="99">暂无记录</td></tr>'}</tbody></table></div>
    <div class="cards">${cards || '<p>暂无记录</p>'}</div>`;
  root.querySelector('[data-filter]')?.addEventListener('submit', (event) => {
    event.preventDefault();
    listPage(root);
  });
  bindBackup(root);
}

function detailPage(root) {
  const id = qs('id');
  const record = id ? getRecord(storage, PLAN, id) : null;
  if (!record) {
    root.innerHTML = `<p>找不到记录</p><p><a href="index.html">返回列表</a></p>`;
    return;
  }
  const rows = PLAN.fields.map((field) => `<dt>${escapeHtml(field.label)}</dt><dd>${escapeHtml(record[field.id] ?? '')}</dd>`).join('');
  root.innerHTML = `
    <header><h1>${escapeHtml(PLAN.entity)}详情</h1></header>
    ${unimplementedBlock()}
    <dl>${rows}</dl>
    ${record.example ? '<p class="example">示例数据，不是真实业务记录</p>' : ''}
    <p><a href="edit.html?id=${encodeURIComponent(record.id)}">编辑</a> · <a href="index.html">返回列表</a></p>`;
}

function editPage(root) {
  const id = qs('id');
  const record = id ? getRecord(storage, PLAN, id) : {};
  const title = id ? `编辑${PLAN.entity}` : `新增${PLAN.entity}`;
  const fields = PLAN.fields.map((field) => `
    <div class="field">
      <label for="${escapeAttr(field.id)}">${escapeHtml(field.label)}${field.required ? ' *' : ''}</label>
      ${fieldControl(field, record[field.id])}
      <p class="error" data-error="${escapeAttr(field.id)}"></p>
    </div>`).join('');
  root.innerHTML = `
    <header><h1>${escapeHtml(title)}</h1></header>
    ${unimplementedBlock()}
    <form data-edit>
      ${fields}
      <button type="submit">${escapeHtml(PLAN.primaryAction)}</button>
      <a href="index.html">取消</a>
    </form>`;
  root.querySelector('[data-edit]').addEventListener('submit', (event) => {
    event.preventDefault();
    const values = formValues(event.target);
    const errors = fieldErrors(PLAN, values);
    showErrors(errors);
    if (Object.keys(errors).length) return;
    const result = id ? updateRecord(storage, PLAN, id, values) : createRecord(storage, PLAN, values);
    if (!result.ok) {
      showErrors(result.errors || {});
      return;
    }
    location.href = `detail.html?id=${encodeURIComponent(result.record.id)}`;
  });
}

function render() {
  const root = document.getElementById('app');
  document.body.className = layoutClass();
  const page = document.body.dataset.page;
  if (page === 'detail') detailPage(root);
  else if (page === 'edit') editPage(root);
  else listPage(root);
}

render();
