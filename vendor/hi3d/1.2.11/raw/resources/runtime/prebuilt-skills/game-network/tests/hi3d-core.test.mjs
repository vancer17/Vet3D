import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('stale sessions and sequences',()=>{const c={session:'a',seq:2,tick:10};assert.equal(m.acceptSnapshot(c,{...c,session:'b',seq:3}).accepted,false);assert.equal(m.acceptSnapshot(c,c).accepted,false);const incoming={...c,seq:3,players:[{x:1}]};const r=m.acceptSnapshot(c,incoming);incoming.players[0].x=2;assert.equal(r.snapshot.players[0].x,1);});
 test('clamped interpolation and finite retry',()=>{assert.deepEqual(m.interpolate({time:0,x:0,y:0,z:0},{time:1,x:10,y:0,z:0},.5),{x:5,y:0,z:0});assert.equal(m.retryDelay(5),null);assert.equal(m.retryDelay(0),250);assert.throws(()=>m.retryDelay(-1));});
