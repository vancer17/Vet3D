import { decode, encode, writeSave } from './hi3d-core.mjs';

export const SAVE_VERSION = 1;
export const STATUSES = ['pending', 'done'];

export function saveKey(appId) {
  if (typeof appId !== 'string' || !appId) throw new Error('appId required');
  return `asset-review-board:${appId}`;
}

export function emptyState() {
  return { notes: [], nextId: 1, syncCamera: false, syncPlayback: false };
}

function versionIds(plan) {
  return new Set((plan.versions || []).map((item) => item.id));
}

function versionById(plan, versionId) {
  return (plan.versions || []).find((item) => item.id === versionId) || null;
}

export function validateLoc(kind, loc) {
  if (!loc || typeof loc !== 'object') return '位置必填';
  if (kind === 'image') {
    if (typeof loc.u !== 'number' || typeof loc.v !== 'number') return '图片批注使用 0–1 的 uv';
    if (loc.u < 0 || loc.u > 1 || loc.v < 0 || loc.v > 1) return '图片 uv 必须在 0–1';
    return null;
  }
  if (kind === 'video') {
    if (typeof loc.t !== 'number' || !Number.isFinite(loc.t) || loc.t < 0) return '视频批注使用非负时间 t';
    return null;
  }
  if (kind === 'model') {
    if (loc.global === true) return null;
    if (typeof loc.part !== 'string' || !loc.part) return '模型批注需要 part 或 global';
    if (loc.view != null && typeof loc.view !== 'string') return 'view 须为字符串';
    return null;
  }
  return '未知媒体类型';
}

export function validateState(plan, data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  if (!Array.isArray(data.notes) || !Number.isSafeInteger(data.nextId) || data.nextId < 1) return false;
  if (data.syncCamera !== true && data.syncCamera !== false) return false;
  if (data.syncPlayback !== true && data.syncPlayback !== false) return false;
  const ids = new Set();
  const versions = versionIds(plan);
  for (const note of data.notes) {
    if (!note || typeof note !== 'object') return false;
    if (typeof note.id !== 'string' || !note.id || ids.has(note.id)) return false;
    ids.add(note.id);
    if (!versions.has(note.versionId)) return false;
    const version = versionById(plan, note.versionId);
    if (validateLoc(version.kind, note.loc)) return false;
    if (typeof note.text !== 'string' || !note.text.trim()) return false;
    if (!STATUSES.includes(note.status)) return false;
  }
  return true;
}

function decodeOptions(plan) {
  return {
    game: plan.appId,
    version: SAVE_VERSION,
    validate: (data) => validateState(plan, data) === true,
  };
}

export function persistState(storage, plan, data) {
  if (validateState(plan, data) !== true) throw new Error('invalid save payload');
  writeSave(storage, saveKey(plan.appId), encode(plan.appId, SAVE_VERSION, data));
}

export function loadState(storage, plan) {
  const key = saveKey(plan.appId);
  const text = storage.getItem(key);
  if (!text) {
    const seeded = emptyState();
    persistState(storage, plan, seeded);
    return seeded;
  }
  return decode(text, decodeOptions(plan));
}

export function notesForVersion(state, versionId) {
  return (state.notes || []).filter((note) => note.versionId === versionId);
}

export function addNote(storage, plan, payload) {
  const version = versionById(plan, payload.versionId);
  if (!version) return { ok: false, error: '批注必须绑定已有版本' };
  const locError = validateLoc(version.kind, payload.loc);
  if (locError) return { ok: false, error: locError };
  const text = String(payload.text || '').trim();
  if (!text) return { ok: false, error: '批注不能为空' };
  const status = payload.status || 'pending';
  if (!STATUSES.includes(status)) return { ok: false, error: '状态只能是 pending 或 done' };
  const state = loadState(storage, plan);
  const note = {
    id: `n-${state.nextId}`,
    versionId: version.id,
    text,
    status,
    loc: { ...payload.loc },
  };
  state.notes.push(note);
  state.nextId += 1;
  persistState(storage, plan, state);
  return { ok: true, note, state };
}

export function editNote(storage, plan, id, patch) {
  const state = loadState(storage, plan);
  const index = state.notes.findIndex((item) => item.id === id);
  if (index < 0) return { ok: false, error: '批注不存在' };
  const prev = state.notes[index];
  const version = versionById(plan, prev.versionId);
  const next = {
    ...prev,
    text: patch.text != null ? String(patch.text).trim() : prev.text,
    status: patch.status != null ? patch.status : prev.status,
    loc: patch.loc != null ? { ...patch.loc } : prev.loc,
  };
  if (!next.text) return { ok: false, error: '批注不能为空' };
  if (!STATUSES.includes(next.status)) return { ok: false, error: '状态只能是 pending 或 done' };
  const locError = validateLoc(version.kind, next.loc);
  if (locError) return { ok: false, error: locError };
  next.versionId = prev.versionId;
  state.notes[index] = next;
  persistState(storage, plan, state);
  return { ok: true, note: next, state };
}

export function setNoteStatus(storage, plan, id, status) {
  return editNote(storage, plan, id, { status });
}

export function setCompare(storage, plan, flags) {
  const state = loadState(storage, plan);
  if (flags.syncCamera != null) state.syncCamera = flags.syncCamera === true;
  if (flags.syncPlayback != null) state.syncPlayback = flags.syncPlayback === true;
  persistState(storage, plan, state);
  return { ok: true, state };
}

export function durationWarning(plan) {
  return plan.durationWarning || null;
}

export function exportNotes(storage, plan) {
  return storage.getItem(saveKey(plan.appId)) || encode(plan.appId, SAVE_VERSION, emptyState());
}

function mergeNotes(current, incoming) {
  const seen = new Set(current.notes.map((item) => item.id));
  const notes = current.notes.slice();
  let nextId = current.nextId;
  for (const note of incoming.notes) {
    if (seen.has(note.id)) continue;
    notes.push(note);
    seen.add(note.id);
    const numeric = Number(String(note.id).replace(/\D/g, ''));
    if (Number.isSafeInteger(numeric) && numeric >= nextId) nextId = numeric + 1;
  }
  return {
    notes,
    nextId,
    syncCamera: incoming.syncCamera === true ? true : current.syncCamera,
    syncPlayback: incoming.syncPlayback === true ? true : current.syncPlayback,
  };
}

export function importNotes(storage, plan, text, options = {}) {
  const key = saveKey(plan.appId);
  const previous = storage.getItem(key);
  const mode = options.mode || 'merge';
  try {
    const incoming = decode(text, decodeOptions(plan));
    let next;
    if (mode === 'replace') {
      if (options.authorizeOverwrite !== true) {
        return { ok: false, error: '覆盖导入需要授权，并先保留备份', backup: previous };
      }
      next = incoming;
    } else if (mode === 'merge') {
      const current = previous ? decode(previous, decodeOptions(plan)) : emptyState();
      next = mergeNotes(current, incoming);
    } else {
      return { ok: false, error: '导入模式只能是 merge 或 replace', backup: previous };
    }
    persistState(storage, plan, next);
    return { ok: true, state: next, backup: previous, mode };
  } catch (error) {
    if (previous != null && storage.getItem(key) !== previous) writeSave(storage, key, previous);
    return { ok: false, error: String(error.message || error), backup: previous };
  }
}
