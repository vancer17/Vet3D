import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
const a={min:[0,0,0],max:[1,1,1]},b={min:[5,0,0],max:[6,1,1]};
 test('continuous impact and parallel separation',()=>{const r=m.sweep(a,[10,0,0],b);assert.equal(r.time,.4);assert.deepEqual(r.normal,[-1,0,0]);assert(!m.sweep(a,[0,10,0],b).hit);assert(!m.sweep(a,[-10,0,0],b).hit);});
 test('initial overlap, touching and input',()=>{assert(m.sweep(a,[0,0,0],a).overlap);assert(!m.sweep(a,[-1,0,0],{min:[1,0,0],max:[2,1,1]}).hit);assert.throws(()=>m.sweep(a,[NaN,0,0],b));});
