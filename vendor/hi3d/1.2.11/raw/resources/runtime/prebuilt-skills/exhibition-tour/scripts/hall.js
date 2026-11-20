import {
  loadState,
  nextStop,
  openHotspot,
  persistState,
  returnToStart,
  resumeTour,
  startTour,
  pauseTour,
} from './tour.mjs';

const PLAN = window.APP_PLAN;
const storage = window.localStorage;
let state = loadState(storage, PLAN);
let timer = null;

function exhibitById(id) {
  return PLAN.exhibits.find((item) => item.id === id);
}

function stopTimer() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
}

function scheduleAdvance() {
  stopTimer();
  if (!state.playing || state.paused || state.complete || PLAN.mode === 'free') return;
  const exhibit = exhibitById(state.current);
  const wait = Math.max(0.5, Number(exhibit && exhibit.dwellSeconds) || 4) * 1000;
  timer = setTimeout(() => {
    const result = nextStop(PLAN, state);
    if (result.ok) {
      state = result.state;
      persistState(storage, PLAN, state);
      render();
      if (state.playing && !state.complete) scheduleAdvance();
    }
  }, wait);
}

function showExhibit(exhibit) {
  const panel = document.getElementById('panel');
  if (!exhibit) {
    panel.innerHTML = '<p>选择一个热点或开始导览。</p>';
    return;
  }
  const pending = exhibit.pending ? '<p class="pending">说明待补，未编造展品历史。</p>' : '';
  if (exhibit.kind === 'missing') {
    panel.innerHTML = `<h2>${exhibit.title}</h2><p>该展位素材缺失，可继续查看其他展位。</p>${pending}<p>${exhibit.caption}</p>`;
    return;
  }
  if (exhibit.kind === 'model') {
    panel.innerHTML = `<h2>${exhibit.title}</h2><model-viewer src="media/${exhibit.file}" camera-controls alt="${exhibit.title}"></model-viewer><p>${exhibit.caption}</p>${pending}`;
    return;
  }
  panel.innerHTML = `<h2>${exhibit.title}</h2><img src="media/${exhibit.file}" alt="${exhibit.title}"><p>${exhibit.caption}</p>${pending}`;
}

function renderHall() {
  const hall = document.getElementById('hall');
  const marks = PLAN.order.map((id) => {
    const pos = PLAN.positions[id];
    const exhibit = exhibitById(id);
    const active = state.hotspot === id || state.current === id ? ' active' : '';
    const missing = exhibit.kind === 'missing' ? ' missing' : '';
    return `<button type="button" class="hotspot${active}${missing}" style="left:${pos.x}%;top:${pos.y}%" data-hotspot="${id}">${exhibit.title}</button>`;
  }).join('');
  const spaceNote = PLAN.space.kind === 'virtual'
    ? `<p class="notice">${PLAN.space.note}</p>`
    : '<p class="notice">展厅背景来自用户提供的已有空间文件，本页不把它标成测绘成果。</p>';
  const bg = PLAN.space.kind === 'existing' && PLAN.space.file
    ? (String(PLAN.space.file).toLowerCase().endsWith('.glb')
      ? `<model-viewer class="space" src="space/${PLAN.space.file}" camera-controls alt="已有空间"></model-viewer>`
      : `<img class="space" src="space/${PLAN.space.file}" alt="已有空间">`)
    : '<div class="space virtual"></div>';
  hall.innerHTML = `${spaceNote}${bg}<div class="spots">${marks}</div>`;
}

function renderControls() {
  const bar = document.getElementById('tour-controls');
  const auto = PLAN.mode !== 'free';
  const status = state.complete ? '路线已走完' : (state.paused ? '已暂停' : (state.playing ? '导览中' : (state.atStart ? '在起点' : '浏览中')));
  bar.innerHTML = `
    <p data-status>${status}</p>
    ${auto ? '<button type="button" data-start>开始导览</button><button type="button" data-pause>暂停</button><button type="button" data-resume>继续</button>' : ''}
    <button type="button" data-home>返回起点</button>`;
}

function render() {
  renderHall();
  renderControls();
  showExhibit(exhibitById(state.current));
  if (state.playing && !state.paused && !state.complete) scheduleAdvance();
  else stopTimer();
}

document.getElementById('hall').addEventListener('click', (event) => {
  const btn = event.target.closest('[data-hotspot]');
  if (!btn) return;
  const result = openHotspot(PLAN, state, btn.dataset.hotspot);
  if (result.ok) {
    state = result.state;
    persistState(storage, PLAN, state);
    render();
  }
});

document.getElementById('tour-controls').addEventListener('click', (event) => {
  if (event.target.matches('[data-start]')) {
    const result = startTour(PLAN, state);
    if (result.ok) {
      state = result.state;
      persistState(storage, PLAN, state);
      render();
    }
    return;
  }
    if (event.target.matches('[data-pause]')) {
    state = pauseTour(state);
    persistState(storage, PLAN, state);
    render();
    return;
  }
  if (event.target.matches('[data-resume]')) {
    state = resumeTour(state);
    persistState(storage, PLAN, state);
    render();
    return;
  }
  if (event.target.matches('[data-home]')) {
    state = returnToStart(PLAN, state);
    persistState(storage, PLAN, state);
    render();
  }
});

render();
