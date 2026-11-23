import { decode, encode, writeSave } from './hi3d-core.mjs';

export const SAVE_VERSION = 1;

export function saveKey(appId) {
  if (typeof appId !== 'string' || !appId) throw new Error('appId required');
  return `exhibition-tour:${appId}`;
}

function unique(items) {
  return [...new Set(items.filter(Boolean))];
}

export function createState(plan) {
  const first = (plan.order || [])[0] || null;
  return {
    index: 0,
    playing: false,
    paused: false,
    complete: false,
    atStart: true,
    current: first,
    hotspot: null,
    visited: [],
  };
}

export function startTour(plan, state) {
  if (plan.mode === 'free') return { ok: false, error: 'free mode has no auto tour' };
  const first = plan.order[0];
  return {
    ok: true,
    state: {
      ...state,
      index: 0,
      playing: true,
      paused: false,
      complete: false,
      atStart: true,
      current: first,
      hotspot: first,
      visited: [],
    },
  };
}

export function pauseTour(state) {
  if (!state.playing || state.complete) return state;
  return { ...state, paused: true };
}

export function resumeTour(state) {
  if (!state.playing || state.complete) return state;
  return { ...state, paused: false };
}

export function userInteract(state) {
  if (state.playing && !state.paused && !state.complete) return pauseTour(state);
  return state;
}

export function nextStop(plan, state) {
  if (state.playing && state.paused) return { ok: false, error: '导览已暂停' };
  const order = plan.order || [];
  if (!order.length) return { ok: false, error: 'empty tour' };
  const visited = unique([...state.visited, state.current]);
  if (state.index >= order.length - 1) {
    return {
      ok: true,
      state: {
        ...state,
        visited,
        playing: false,
        paused: false,
        complete: true,
        current: order[order.length - 1],
        hotspot: order[order.length - 1],
      },
    };
  }
  const index = state.index + 1;
  return {
    ok: true,
    state: {
      ...state,
      visited,
      index,
      atStart: false,
      current: order[index],
      hotspot: order[index],
    },
  };
}

export function returnToStart(plan, state) {
  const first = plan.order[0];
  return {
    ...state,
    index: 0,
    playing: false,
    paused: false,
    complete: false,
    atStart: true,
    current: first,
    hotspot: null,
  };
}

export function openHotspot(plan, state, exhibitId) {
  const exhibit = (plan.exhibits || []).find((item) => item.id === exhibitId);
  if (!exhibit) return { ok: false, error: '热点与展品不匹配' };
  return {
    ok: true,
    state: {
      ...userInteract(state),
      current: exhibitId,
      hotspot: exhibitId,
      atStart: exhibitId === plan.order[0] && state.index === 0,
    },
    exhibit,
    placeholder: exhibit.kind === 'missing',
  };
}

export function hotspotMatches(plan, exhibitId) {
  return (plan.exhibits || []).some((item) => item.id === exhibitId);
}

export function routeComplete(plan, state) {
  const order = plan.order || [];
  return state.complete === true && order.every((id) => state.visited.includes(id));
}

export function persistState(storage, plan, state) {
  writeSave(storage, saveKey(plan.appId), encode(plan.appId, SAVE_VERSION, state));
}

export function loadState(storage, plan) {
  const text = storage.getItem(saveKey(plan.appId));
  if (!text) {
    const seeded = createState(plan);
    persistState(storage, plan, seeded);
    return seeded;
  }
  return decode(text, {
    game: plan.appId,
    version: SAVE_VERSION,
    validate: (data) => data && typeof data === 'object' && Array.isArray(data.visited),
  });
}
