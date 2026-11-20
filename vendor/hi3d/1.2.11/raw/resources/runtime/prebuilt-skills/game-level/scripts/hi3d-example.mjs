import * as m from './hi3d-core.mjs';
console.log(m.validateLevel({nodes:[{id:'spawn'},{id:'exit'}],edges:[['spawn','exit']],start:'spawn',goals:['exit']}));
