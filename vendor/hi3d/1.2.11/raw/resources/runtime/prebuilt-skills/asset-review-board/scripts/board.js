import {
  addNote,
  durationWarning,
  editNote,
  exportNotes,
  importNotes,
  loadState,
  notesForVersion,
  persistState,
  setCompare,
  setNoteStatus,
} from './notes.mjs';

const PLAN = window.APP_PLAN;
const storage = window.localStorage;
let state;
let storageError = '';

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

function tryPersist() {
  try {
    persistState(storage, PLAN, state);
    storageError = '';
    return true;
  } catch (error) {
    storageError = `存储失败，请立刻导出备份。${error && error.message ? error.message : ''}`;
    return false;
  }
}

function reload() {
  try {
    state = loadState(storage, PLAN);
    storageError = '';
  } catch (error) {
    storageError = `无法读取存档，请立刻导出或更换目录。${error && error.message ? error.message : ''}`;
    state = { notes: [], nextId: 1, syncCamera: false, syncPlayback: false };
  }
}

function locLabel(kind, loc) {
  if (kind === 'image') return `uv ${loc.u.toFixed(2)}, ${loc.v.toFixed(2)}`;
  if (kind === 'video') return `t=${loc.t}s`;
  if (loc.global) return '整体';
  return loc.view ? `${loc.part} / ${loc.view}` : loc.part;
}

function mediaMarkup(version) {
  const src = `media/${version.file}`;
  if (version.kind === 'image') {
    return `<img src="${escapeHtml(src)}" alt="${escapeHtml(version.label)}" data-kind="image" data-version="${escapeHtml(version.id)}">`;
  }
  if (version.kind === 'video') {
    return `<video src="${escapeHtml(src)}" controls data-kind="video" data-version="${escapeHtml(version.id)}"></video>`;
  }
  return `<model-viewer src="${escapeHtml(src)}" camera-controls alt="${escapeHtml(version.label)}" data-kind="model" data-version="${escapeHtml(version.id)}"></model-viewer>`;
}

function locFromEvent(version, event) {
  if (version.kind === 'image') {
    const box = event.currentTarget.getBoundingClientRect();
    const u = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
    const v = Math.min(1, Math.max(0, (event.clientY - box.top) / box.height));
    return { u, v };
  }
  if (version.kind === 'video') {
    return { t: event.currentTarget.currentTime || 0 };
  }
  return { global: true };
}

function unimplementedBlock() {
  const items = (PLAN.unimplemented || []).map((name) => `<li>${escapeHtml(name)}：未实现</li>`).join('');
  return `<aside class="notice" role="note"><p>以下能力未实现，页面不提供可点击入口：</p><ul>${items}</ul></aside>`;
}

function render() {
  const root = document.getElementById('board');
  const warn = durationWarning(PLAN);
  const layout = PLAN.layout === 'single' ? 'layout-single' : 'layout-side';
  const panes = (PLAN.versions || []).map((version) => {
    const notes = notesForVersion(state, version.id).map((note) => `
      <li data-note="${escapeHtml(note.id)}">
        <p>${escapeHtml(note.text)} <small>${escapeHtml(locLabel(version.kind, note.loc))}</small></p>
        <p>
          <button type="button" data-status="${escapeHtml(note.id)}" data-to="${note.status === 'pending' ? 'done' : 'pending'}">${note.status === 'pending' ? '标为完成' : '标为待处理'}</button>
          <button type="button" data-edit="${escapeHtml(note.id)}">编辑</button>
        </p>
      </li>`).join('');
    return `<section class="pane" data-pane="${escapeHtml(version.id)}">
      <h2>${escapeHtml(version.label)} <small>${escapeHtml(version.kind)}</small></h2>
      ${mediaMarkup(version)}
      <form data-add="${escapeHtml(version.id)}">
        <label>批注 <textarea name="text" required></textarea></label>
        <button type="submit">添加</button>
      </form>
      <ul data-notes="${escapeHtml(version.id)}">${notes}</ul>
    </section>`;
  }).join('');
  root.className = layout;
  root.innerHTML = `
    <header>
      <h1>${escapeHtml(PLAN.title)}</h1>
      <p>审阅维度：${escapeHtml((PLAN.criteria || []).join('、'))}。${escapeHtml(PLAN.note || '')}</p>
      ${warn ? `<p class="warn">${escapeHtml(warn)}</p>` : ''}
      ${storageError ? `<p class="error" data-storage-error>${escapeHtml(storageError)} <button type="button" data-export>立刻导出</button></p>` : ''}
      <p>
        <label><input type="checkbox" data-sync-camera${state.syncCamera ? ' checked' : ''}> 同步相机</label>
        <label><input type="checkbox" data-sync-playback${state.syncPlayback ? ' checked' : ''}> 同步播放</label>
        <button type="button" data-export>导出批注</button>
        <label>导入 <input type="file" data-import accept="application/json"></label>
        <label><input type="checkbox" data-replace> 覆盖导入（需确认）</label>
      </p>
      <p data-import-status></p>
    </header>
    <div class="panes">${panes}</div>
    <noscript></noscript>
  `;
  const noticeHost = document.getElementById('unimplemented');
  if (noticeHost) noticeHost.innerHTML = unimplementedBlock();
  bind();
  applyCompare();
}

function bind() {
  document.querySelector('[data-sync-camera]')?.addEventListener('change', (event) => {
    const result = setCompare(storage, PLAN, { syncCamera: event.target.checked });
    if (result.ok) state = result.state;
    else storageError = result.error || '无法保存对比开关';
    render();
  });
  document.querySelector('[data-sync-playback]')?.addEventListener('change', (event) => {
    const result = setCompare(storage, PLAN, { syncPlayback: event.target.checked });
    if (result.ok) state = result.state;
    else storageError = result.error || '无法保存对比开关';
    render();
  });
  document.querySelectorAll('[data-export]').forEach((button) => {
    button.addEventListener('click', () => {
      const blob = new Blob([exportNotes(storage, PLAN)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${PLAN.appId}-notes.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  });
  document.querySelector('[data-import]')?.addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    const status = document.querySelector('[data-import-status]');
    if (!file) return;
    const text = await file.text();
    const replace = document.querySelector('[data-replace]')?.checked === true;
    const result = importNotes(storage, PLAN, text, {
      mode: replace ? 'replace' : 'merge',
      authorizeOverwrite: replace,
    });
    if (result.ok) {
      state = result.state;
      if (status) status.textContent = replace ? '已覆盖导入，上一份已备份在导出文件中。' : '已合并导入。';
      render();
    } else if (status) {
      status.textContent = `导入失败，现有批注未覆盖。${result.error || ''}`;
    }
  });
  for (const version of PLAN.versions || []) {
    const media = document.querySelector(`[data-version="${version.id}"]`);
    media?.addEventListener(version.kind === 'video' ? 'click' : 'click', (event) => {
      const form = document.querySelector(`form[data-add="${version.id}"]`);
      form.dataset.loc = JSON.stringify(locFromEvent(version, event));
    });
    media?.addEventListener('timeupdate', () => {
      if (state.syncPlayback) syncVideos(media);
    });
    media?.addEventListener('camera-change', () => {
      if (state.syncCamera) syncCameras(media);
    });
    document.querySelector(`form[data-add="${version.id}"]`)?.addEventListener('submit', (event) => {
      event.preventDefault();
      const loc = event.currentTarget.dataset.loc ? JSON.parse(event.currentTarget.dataset.loc) : defaultLoc(version);
      const result = addNote(storage, PLAN, {
        versionId: version.id,
        text: event.currentTarget.elements.text.value,
        loc,
      });
      if (result.ok) {
        state = result.state;
        render();
      } else {
        storageError = result.error;
        if (!tryPersist()) render();
        else render();
      }
    });
  }
  document.querySelectorAll('[data-status]').forEach((button) => {
    button.addEventListener('click', () => {
      const result = setNoteStatus(storage, PLAN, button.getAttribute('data-status'), button.getAttribute('data-to'));
      if (result.ok) state = result.state;
      render();
    });
  });
  document.querySelectorAll('[data-edit]').forEach((button) => {
    button.addEventListener('click', () => {
      const id = button.getAttribute('data-edit');
      const note = state.notes.find((item) => item.id === id);
      const text = window.prompt('编辑批注', note ? note.text : '');
      if (text == null) return;
      const result = editNote(storage, PLAN, id, { text });
      if (result.ok) state = result.state;
      render();
    });
  });
}

function defaultLoc(version) {
  if (version.kind === 'image') return { u: 0.5, v: 0.5 };
  if (version.kind === 'video') return { t: 0 };
  return { global: true };
}

function syncCameras(source) {
  if (!source || source.getAttribute('data-kind') !== 'model') return;
  const orbit = source.getCameraOrbit && source.getCameraOrbit();
  if (!orbit) return;
  document.querySelectorAll('model-viewer').forEach((viewer) => {
    if (viewer === source) return;
    if (viewer.cameraOrbit !== undefined) viewer.cameraOrbit = `${orbit.theta}rad ${orbit.phi}rad ${orbit.radius}m`;
  });
}

function syncVideos(source) {
  if (!source || source.getAttribute('data-kind') !== 'video') return;
  document.querySelectorAll('video').forEach((video) => {
    if (video === source) return;
    if (Math.abs(video.currentTime - source.currentTime) > 0.12) video.currentTime = source.currentTime;
  });
}

function applyCompare() {
  const firstModel = document.querySelector('model-viewer');
  const firstVideo = document.querySelector('video');
  if (state.syncCamera && firstModel) syncCameras(firstModel);
  if (state.syncPlayback && firstVideo) syncVideos(firstVideo);
}

reload();
render();
