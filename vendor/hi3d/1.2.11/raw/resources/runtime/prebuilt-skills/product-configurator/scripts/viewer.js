import {
  defaultState,
  disabledVisibility,
  displayMap,
  exportConfig,
  importConfig,
  loadState,
  persistState,
  priceTotal,
  setColor,
  setVisibility,
} from './rules.mjs';

const PLAN = window.APP_PLAN;
const storage = window.localStorage;
let state = loadState(storage, PLAN);

function hexToRgb(hex) {
  return [parseInt(hex.slice(1, 3), 16) / 255, parseInt(hex.slice(3, 5), 16) / 255, parseInt(hex.slice(5, 7), 16) / 255];
}

async function applyViewer() {
  const mv = document.querySelector('model-viewer');
  const status = document.querySelector('[data-load-status]');
  if (!mv) return;
  const map = displayMap(PLAN, state);
  try {
    await mv.updateComplete;
    if (!mv.model) throw new Error('模型未加载');
    if (status) status.textContent = '';
    for (const [name, hex] of Object.entries(map.colors)) {
      const mat = (mv.model.materials || []).find((item) => item.name === name);
      if (mat && mat.pbrMetallicRoughness) mat.pbrMetallicRoughness.setBaseColorFactor([...hexToRgb(hex), 1]);
    }
    for (const mat of mv.model.materials || []) {
      const hidden = map.hidden.some((node) => mat.name === node);
      if (mat.setAlphaMode) mat.setAlphaMode(hidden ? 'BLEND' : 'OPAQUE');
      if (mat.pbrMetallicRoughness) {
        const current = mat.pbrMetallicRoughness.baseColorFactor || [1, 1, 1, 1];
        const hex = map.colors[mat.name];
        const rgb = hex ? hexToRgb(hex) : [current[0], current[1], current[2]];
        mat.pbrMetallicRoughness.setBaseColorFactor([...rgb, hidden ? 0 : 1]);
      }
    }
  } catch (error) {
    if (status) status.innerHTML = `模型加载失败。<a href="${PLAN.modelFile}" download>下载模型</a> 后重试。${error && error.message ? error.message : ''}`;
  }
}

function renderPrice() {
  const node = document.querySelector('[data-price]');
  if (!node) return;
  const priced = priceTotal(PLAN, state);
  node.textContent = priced ? `${priced.currency} ${priced.total}` : '';
}

function render() {
  const root = document.getElementById('controls');
  const colors = (PLAN.colorOptions || []).map((option) => {
    const buttons = option.swatches.map((swatch) => `<button type="button" data-color="${option.id}" data-swatch="${swatch}" style="background:${swatch}" aria-label="${swatch}"${state.colors[option.id] === swatch ? ' aria-pressed="true"' : ''}></button>`).join('');
    return `<fieldset><legend>${option.label}</legend>${buttons}</fieldset>`;
  }).join('');
  const vis = (PLAN.visibilityOptions || []).map((option) => {
    const blocked = disabledVisibility(PLAN, state, option.id);
    const checked = state.visibility[option.id] ? ' checked' : '';
    const disabled = blocked.length && !state.visibility[option.id] ? ' disabled' : '';
    const why = blocked.length && !state.visibility[option.id] ? `<p class="error">与 ${blocked.join('、')} 互斥</p>` : '';
    return `<label><input type="checkbox" data-vis="${option.id}"${checked}${disabled}> ${option.label}</label>${why}`;
  }).join('');
  const cams = (PLAN.cameras || []).map((camera) => `<button type="button" data-orbit="${camera.orbit}">${camera.label}</button>`).join('');
  const unimplemented = (PLAN.unimplemented || []).map((name) => `<li>${name}：未实现</li>`).join('');
  root.innerHTML = `
    ${colors}
    ${vis}
    <p><button type="button" data-reset>恢复初始状态</button>
    <button type="button" data-export>导出配置</button>
    <label>导入配置 <input type="file" data-import accept="application/json"></label></p>
    <p data-import-status></p>
    <p data-price></p>
    <p>预设视角 ${cams}</p>
    <aside class="notice" role="note"><p>${PLAN.note}</p><p>以下能力未实现，页面不提供可点击入口：</p><ul>${unimplemented}</ul></aside>`;
  renderPrice();
  applyViewer();
}

document.getElementById('controls').addEventListener('click', (event) => {
  const color = event.target.closest('[data-color]');
  if (color) {
    const result = setColor(PLAN, state, color.dataset.color, color.dataset.swatch);
    if (result.ok) {
      state = result.state;
      persistState(storage, PLAN, state);
      render();
    }
    return;
  }
  if (event.target.matches('[data-reset]')) {
    state = defaultState(PLAN);
    persistState(storage, PLAN, state);
    render();
    return;
  }
  if (event.target.matches('[data-export]')) {
    const blob = new Blob([exportConfig(storage, PLAN)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${PLAN.appId}-config.json`;
    a.click();
    URL.revokeObjectURL(url);
    return;
  }
  const orbit = event.target.closest('[data-orbit]');
  if (orbit) {
    const mv = document.querySelector('model-viewer');
    if (mv) mv.cameraOrbit = orbit.dataset.orbit;
  }
});

document.getElementById('controls').addEventListener('change', (event) => {
  if (event.target.matches('[data-vis]')) {
    const result = setVisibility(PLAN, state, event.target.dataset.vis, event.target.checked);
    if (result.ok) {
      state = result.state;
      persistState(storage, PLAN, state);
    }
    render();
  }
  if (event.target.matches('[data-import]')) {
    const file = event.target.files && event.target.files[0];
    const status = document.querySelector('[data-import-status]');
    if (!file) return;
    file.text().then((text) => {
      const result = importConfig(storage, PLAN, text);
      if (status) status.textContent = result.ok ? '导入成功' : `导入失败，未覆盖现有配置：${result.error}`;
      if (result.ok) {
        state = result.state;
        render();
      }
    });
  }
});

const viewer = document.querySelector('model-viewer');
if (viewer) {
  viewer.addEventListener('load', applyViewer);
  viewer.addEventListener('error', () => {
    const status = document.querySelector('[data-load-status]');
    if (status) status.innerHTML = `模型加载失败。<a href="${PLAN.modelFile}" download>下载模型</a> 后重试。`;
  });
}

render();
