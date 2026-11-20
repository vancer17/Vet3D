import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('highest per player and competition ties',()=>{const r=m.rankScores([{game:'a',player:'b',score:5},{game:'a',player:'a',score:5},{game:'a',player:'c',score:3},{game:'a',player:'b',score:1}],{game:'a'});assert.deepEqual(r.top.map(x=>x.rank),[1,1,3]);assert.equal(r.top[0].player,'a');});
 test('outside top and namespace isolation',()=>{const r=m.rankScores([{game:'b',player:'x',score:100},...Array.from({length:20},(_,i)=>({game:'a',player:'p'+i,score:20-i}))],{game:'a',player:'p19',limit:10});assert.equal(r.top.length,10);assert.equal(r.self.rank,20);assert.equal(r.total,20);});
