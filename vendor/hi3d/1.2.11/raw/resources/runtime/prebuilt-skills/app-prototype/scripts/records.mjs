import { decode, encode, writeSave } from './hi3d-core.mjs';

export const SAVE_VERSION = 1;

export function saveKey(appId) {
  if (typeof appId !== 'string' || !appId) throw new Error('appId required');
  return `app-prototype:${appId}`;
}

export function emptyState() {
  return { records: [], nextId: 1 };
}

function fieldIds(plan) {
  return (plan.fields || []).map((field) => field.id);
}

export function validateState(plan, data) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
  if (!Array.isArray(data.records) || !Number.isSafeInteger(data.nextId) || data.nextId < 1) return false;
  const ids = new Set();
  for (const record of data.records) {
    if (!record || typeof record !== 'object' || typeof record.id !== 'string' || !record.id) return false;
    if (ids.has(record.id)) return false;
    ids.add(record.id);
    if (record.example !== true && record.example !== false && record.example !== undefined) return false;
    for (const field of plan.fields || []) {
      if (!(field.id in record)) continue;
      if (!valueMatches(field, record[field.id])) return false;
    }
  }
  return true;
}

function valueMatches(field, value) {
  if (value === undefined || value === null) return !field.required;
  if (field.type === 'string') return typeof value === 'string';
  if (field.type === 'number') return typeof value === 'number' && Number.isFinite(value);
  if (field.type === 'boolean') return typeof value === 'boolean';
  if (field.type === 'enum') return field.options.includes(value);
  return false;
}

export function fieldErrors(plan, values) {
  const errors = {};
  for (const field of plan.fields || []) {
    const raw = values[field.id];
    if (field.required && (raw === undefined || raw === null || raw === '')) {
      errors[field.id] = `${field.label}为必填`;
      continue;
    }
    if (raw === undefined || raw === null || raw === '') continue;
    if (field.type === 'number') {
      const n = typeof raw === 'number' ? raw : Number(raw);
      if (!Number.isFinite(n)) errors[field.id] = `${field.label}须为数字`;
    } else if (field.type === 'boolean') {
      if (typeof raw !== 'boolean' && raw !== 'true' && raw !== 'false') errors[field.id] = `${field.label}须为是或否`;
    } else if (field.type === 'enum' && !field.options.includes(raw)) {
      errors[field.id] = `${field.label}不在允许选项中`;
    }
  }
  return errors;
}

export function normalizeValues(plan, values) {
  const out = {};
  for (const field of plan.fields || []) {
    const raw = values[field.id];
    if (raw === undefined || raw === null || raw === '') continue;
    if (field.type === 'number') out[field.id] = typeof raw === 'number' ? raw : Number(raw);
    else if (field.type === 'boolean') out[field.id] = raw === true || raw === 'true';
    else out[field.id] = String(raw);
  }
  return out;
}

function decodeOptions(plan) {
  return {
    game: plan.appId,
    version: SAVE_VERSION,
    validate: (data) => validateState(plan, data) === true,
  };
}

export function loadState(storage, plan) {
  const key = saveKey(plan.appId);
  const text = storage.getItem(key);
  if (!text) {
    const seeded = seedState(plan);
    persistState(storage, plan, seeded);
    return seeded;
  }
  return decode(text, decodeOptions(plan));
}

function seedState(plan) {
  const state = emptyState();
  for (const item of plan.records || []) {
    const id = item.id || `r-${state.nextId}`;
    state.records.push({ ...item, id, example: item.example === true });
    const numeric = Number(String(id).replace(/\D/g, ''));
    if (Number.isSafeInteger(numeric) && numeric >= state.nextId) state.nextId = numeric + 1;
    else state.nextId += 1;
  }
  return state;
}

export function persistState(storage, plan, data) {
  if (validateState(plan, data) !== true) throw new Error('invalid save payload');
  writeSave(storage, saveKey(plan.appId), encode(plan.appId, SAVE_VERSION, data));
}

export function createRecord(storage, plan, values) {
  const errors = fieldErrors(plan, values);
  if (Object.keys(errors).length) return { ok: false, errors };
  const state = loadState(storage, plan);
  const record = { id: `r-${state.nextId}`, ...normalizeValues(plan, values), example: false };
  state.records.push(record);
  state.nextId += 1;
  persistState(storage, plan, state);
  return { ok: true, record };
}

export function updateRecord(storage, plan, id, values) {
  const errors = fieldErrors(plan, values);
  if (Object.keys(errors).length) return { ok: false, errors };
  const state = loadState(storage, plan);
  const index = state.records.findIndex((item) => item.id === id);
  if (index < 0) return { ok: false, errors: { id: '记录不存在' } };
  const prev = state.records[index];
  state.records[index] = { ...prev, ...normalizeValues(plan, values), id: prev.id, example: false };
  persistState(storage, plan, state);
  return { ok: true, record: state.records[index] };
}

export function getRecord(storage, plan, id) {
  return loadState(storage, plan).records.find((item) => item.id === id) || null;
}

export function filterRecords(state, query, status, statusField) {
  const q = String(query || '').trim().toLowerCase();
  return state.records.filter((item) => {
    if (statusField && status && item[statusField] !== status) return false;
    if (!q) return true;
    return Object.values(item).some((value) => String(value).toLowerCase().includes(q));
  });
}

export function exportBackup(storage, plan) {
  return storage.getItem(saveKey(plan.appId)) || encode(plan.appId, SAVE_VERSION, emptyState());
}

export function importBackup(storage, plan, text) {
  const key = saveKey(plan.appId);
  const previous = storage.getItem(key);
  try {
    const data = decode(text, decodeOptions(plan));
    persistState(storage, plan, data);
    return { ok: true, backup: previous };
  } catch (error) {
    if (previous != null && storage.getItem(key) !== previous) writeSave(storage, key, previous);
    return { ok: false, error: String(error.message || error), backup: previous };
  }
}

export { fieldIds };
