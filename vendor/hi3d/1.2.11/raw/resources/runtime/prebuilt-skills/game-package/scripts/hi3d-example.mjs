import * as m from './hi3d-core.mjs';
console.log(m.validateManifest({schema:'game-package.v1',id:'sample',version:'1.0.0',entry:'index.html',permissions:[],files:[{path:'index.html',bytes:123,sha256:'a'.repeat(64)}]}));
