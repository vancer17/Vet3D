import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
const level={nodes:[{id:'a'},{id:'b'}],edges:[['a','b']],start:'a',goals:['b']};
 test('directed graph reachability',()=>{assert(m.validateLevel(level).valid);assert(!m.validateLevel({...level,edges:[['b','a']]}).valid);assert(!m.validateLevel({...level,edges:[['a','missing']]}).valid);});
 test('duplicate and missing goals',()=>{assert(!m.validateLevel({...level,nodes:[{id:'a'},{id:'a'}]}).valid);assert(!m.validateLevel({...level,goals:[]}).valid);assert(!m.validateLevel(null).valid);});
