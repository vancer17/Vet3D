import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('spend and retry once',()=>{const s={balance:10,receipts:[]},c={id:'1',cost:4,reward:0},r=m.transact(s,c);assert.equal(r.balance,6);assert.equal(m.transact(r,c),r);assert.equal(s.balance,10);assert.throws(()=>m.transact(r,{...c,reward:1}));assert.throws(()=>m.transact(s,{...c,cost:11}));});
 test('reward cap and overflow',()=>{assert.equal(m.offlineReward(100,2,10),20);assert.throws(()=>m.offlineReward(-1,1,1));assert.throws(()=>m.transact({balance:Number.MAX_SAFE_INTEGER,receipts:[]},{id:'x',cost:0,reward:1}));});
