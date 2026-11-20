import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('deadzone and diagonal magnitude',()=>{assert.deepEqual(m.axis(.01,0),[0,0]);assert(Math.abs(Math.hypot(...m.axis(1,1))-1)<1e-10);assert.throws(()=>m.axis(1,0,1));assert.deepEqual(m.actions(['KeyW'],{forward:['KeyW'],fire:['Space']}),{forward:true,fire:false});});
 test('keyboard ownership and disposal',()=>{const listeners=new Map();const target={addEventListener:(k,v)=>listeners.set(k,v),removeEventListener:k=>listeners.delete(k)};let state;const dispose=m.bindKeyboard(target,{fire:['Space']},s=>state=s);listeners.get('keydown')({type:'keydown',code:'Space',target:{tagName:'INPUT'}});assert.equal(state,undefined);listeners.get('keydown')({type:'keydown',code:'Space'});assert.equal(state.fire,true);listeners.get('blur')();assert.equal(state.fire,false);dispose();dispose();assert.equal(listeners.size,0);});
