import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('tail latency and immutable samples',()=>{const a=[40,10,10,10],r=m.profile(a,{budgetMs:16});assert.equal(r.p95Ms,40);assert.equal(r.overBudget,1);assert.deepEqual(a,[40,10,10,10]);assert.throws(()=>m.profile([]));assert.throws(()=>m.profile([Infinity]));});
 test('quality boundaries and dead band',()=>{assert.equal(m.quality(0,{p95Ms:50}),0);assert.equal(m.quality(3,{p95Ms:5}),3);assert.equal(m.quality(2,{p95Ms:16}),2);assert.equal(m.quality(2,{p95Ms:40}),1);});
