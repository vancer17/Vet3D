// Offline synthetic-fixture check; optionally save the FBX for importer testing.
const fs = require('fs'), zlib = require('zlib'), path = require('path');
const assets = path.join(__dirname, '../assets/viewer');
const cut = require(path.join(assets, 'cut.js')), fbx = require(path.join(assets, 'fbx.js'));
const assert = require('assert'), vm = require('vm');
(async () => {
  const html = fs.readFileSync(process.argv[2], 'utf8');
  const content = id => html.match(new RegExp('<script id="' + id + '"[^>]*>([\\s\\S]*?)</script>'))[1];
  const meta = JSON.parse(content('metadata')), bytes = zlib.gunzipSync(Buffer.from(content('payload'), 'base64'));
  const d = cut.views(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.length), meta);
  // Compile every executable inline script, including the embedded worker.
  for (const match of html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)) {
    if (!match[1].includes('type=') || match[1].includes('id="worker-code"')) new vm.Script(match[2]);
  }
  // Runtime compatibility check, not a browser rendering test.
  const context = vm.createContext({console: {warn() {}}, document: {}});
  vm.runInContext(fs.readFileSync(path.join(assets, 'three.min.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(assets, 'OrbitControls.js'), 'utf8'), context);
  vm.runInContext('const canvas={addEventListener(){},removeEventListener(){},ownerDocument:{removeEventListener(){}}}; const camera=new THREE.PerspectiveCamera(35,1,.01,100); camera.position.z=2; const controls=new THREE.OrbitControls(camera,canvas); controls.update(); controls.dispose();', context);
  let calls = 0;
  const messages = [], workerContext = vm.createContext({self: {}, postMessage: m => messages.push(m),
    SplitCut: {...cut, solve(...args) {calls++; return cut.solve(...args);}}, StaticFBX: fbx, Uint8Array});
  vm.runInContext(fs.readFileSync(path.join(assets, 'worker.js'), 'utf8'), workerContext);
  await workerContext.self.onmessage({data: {type: 'init', meta, buffer: bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.length)}});
  assert.equal(calls, 0); assert.equal(messages.at(-1).type, 'ready');
  await workerContext.self.onmessage({data: {type: 'export', threshold: .5, image: new Uint8Array()}});
  assert.equal(messages.at(-1).type, 'error'); assert.equal(calls, 0);
  const image = Buffer.from(content('texture'), 'base64'), cuts = [];
  for (const threshold of [.35, .5, .65]) {
    const result = cut.solve(d, meta, threshold);
    cuts.push({threshold, labels: Array.from(result.labels), stats: result.stats});
  }
  const output = Buffer.from(await fbx.exportFile(d, cuts[1].labels, image, () => {}, meta.material));
  if (process.argv[3]) fs.writeFileSync(process.argv[3], output);
  const isolated = {...d, lum: new Float64Array([0, 1]), a: new Uint32Array(), b: new Uint32Array()};
  const noBoundary = cut.solve(isolated, {...meta, faces: 2}, .5);
  process.stdout.write(JSON.stringify({cuts,
    fbx_header_valid: output.subarray(0, 20).toString().startsWith('Kaydara FBX Binary'),
    embedded_image_preserved: output.includes(image), no_boundary_labels: Array.from(noBoundary.labels)}));
})().catch(error => {console.error(error); process.exitCode = 1;});
