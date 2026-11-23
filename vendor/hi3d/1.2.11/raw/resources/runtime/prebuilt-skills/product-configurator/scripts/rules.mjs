import { decode, encode, writeSave } from './hi3d-core.mjs';

export const SAVE_VERSION = 1;

export function saveKey(appId) {
  if (typeof appId !== 'string' || !appId) throw new Error('appId required');
  return `product-configurator:${appId}`;
}

export function defaultState(plan) {
  const colors = {};
  for (const option of plan.colorOptions || []) colors[option.id] = option.swatches[0];
  const visibility = {};
  for (const option of plan.visibilityOptions || []) visibility[option.id] = option.default !== false;
  return { colors, visibility };
}

export function exclusiveConflict(plan, state) {
  const reasons = [];
  for (const group of plan.exclusiveGroups || []) {
    const on = (group.optionIds || []).filter((id) => {
      if (id in state.visibility) return state.visibility[id] === true;
      return false;
    });
    if (on.length > 1) reasons.push(`${group.id}: 互斥选项不能同时开启`);
  }
  return reasons;
}

export function disabledVisibility(plan, state, optionId) {
  for (const group of plan.exclusiveGroups || []) {
    if (!(group.optionIds || []).includes(optionId)) continue;
    const othersOn = group.optionIds.filter((id) => id !== optionId && state.visibility[id] === true);
    if (othersOn.length && state.visibility[optionId] !== true) return othersOn;
  }
  return [];
}

export function setColor(plan, state, optionId, swatch) {
  const option = (plan.colorOptions || []).find((item) => item.id === optionId);
  if (!option) return { ok: false, error: '未知颜色选项' };
  if (!option.swatches.includes(swatch)) return { ok: false, error: '色板不在允许列表中' };
  return { ok: true, state: { ...state, colors: { ...state.colors, [optionId]: swatch } } };
}

export function setVisibility(plan, state, optionId, visible) {
  const option = (plan.visibilityOptions || []).find((item) => item.id === optionId);
  if (!option) return { ok: false, error: '未知显隐选项' };
  let next = { ...state, visibility: { ...state.visibility, [optionId]: visible === true } };
  if (visible === true) {
    for (const group of plan.exclusiveGroups || []) {
      if (!(group.optionIds || []).includes(optionId)) continue;
      for (const other of group.optionIds) {
        if (other !== optionId && next.visibility[other]) next = { ...next, visibility: { ...next.visibility, [other]: false } };
      }
    }
  }
  const reasons = exclusiveConflict(plan, next);
  if (reasons.length) return { ok: false, error: reasons[0], reasons };
  return { ok: true, state: next };
}

export function displayMap(plan, state) {
  const colors = {};
  for (const option of plan.colorOptions || []) colors[option.target] = state.colors[option.id];
  const hidden = [];
  for (const option of plan.visibilityOptions || []) {
    if (state.visibility[option.id] === false) hidden.push(option.target);
  }
  return { colors, hidden };
}

export function priceTotal(plan, state) {
  if (!plan.pricing) return null;
  let total = Number(plan.pricing.base);
  const extras = plan.pricing.options || {};
  for (const [id, amount] of Object.entries(extras)) {
    if (id in state.colors) total += Number(amount);
    else if (state.visibility[id] === true) total += Number(amount);
  }
  return { currency: plan.pricing.currency, total };
}

export function persistState(storage, plan, state) {
  writeSave(storage, saveKey(plan.appId), encode(plan.appId, SAVE_VERSION, state));
}

export function loadState(storage, plan) {
  const text = storage.getItem(saveKey(plan.appId));
  if (!text) {
    const seeded = defaultState(plan);
    persistState(storage, plan, seeded);
    return seeded;
  }
  return decode(text, {
    game: plan.appId,
    version: SAVE_VERSION,
    validate: (data) => data && typeof data === 'object' && data.colors && data.visibility,
  });
}

export function exportConfig(storage, plan) {
  return storage.getItem(saveKey(plan.appId)) || encode(plan.appId, SAVE_VERSION, defaultState(plan));
}

export function importConfig(storage, plan, text) {
  const key = saveKey(plan.appId);
  const previous = storage.getItem(key);
  try {
    const data = decode(text, {
      game: plan.appId,
      version: SAVE_VERSION,
      validate: (value) => value && typeof value === 'object' && value.colors && value.visibility,
    });
    persistState(storage, plan, data);
    return { ok: true, state: data };
  } catch (error) {
    if (previous != null && storage.getItem(key) !== previous) writeSave(storage, key, previous);
    return { ok: false, error: String(error.message || error) };
  }
}
