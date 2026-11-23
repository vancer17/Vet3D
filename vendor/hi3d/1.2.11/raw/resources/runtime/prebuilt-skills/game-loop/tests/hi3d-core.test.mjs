import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('fixed time, pause, capped debt',()=>{let c=m.createClock({hz:10,maxSteps:2});let r=m.advance(c,.35);assert.equal(r.steps,2);assert(Math.abs(r.clock.dropped-.1)<1e-9);assert.equal(m.advance(m.pause(c),100).steps,0);assert.equal(c.tick,0);assert.equal(m.transition('playing','win'),'won');assert.throws(()=>m.transition('ready','resume'));assert.throws(()=>m.advance(c,NaN));});
 test('equivalent elapsed partitions',()=>{let c=m.createClock();for(let i=0;i<60;i++)c=m.advance(c,1/60).clock;assert.equal(c.tick,60);assert.equal(m.advance(m.createClock({maxSteps:100}),1).clock.tick,60);});
