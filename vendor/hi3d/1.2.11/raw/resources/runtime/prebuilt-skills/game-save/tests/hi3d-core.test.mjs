import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('migration preserves input and rejects other games/future',()=>{const text=m.encode('a',1,{coins:5});assert.deepEqual(m.decode(text,{game:'a',version:2,migrations:{1:d=>({...d,level:1})}}),{coins:5,level:1});assert.throws(()=>m.decode(text,{game:'b',version:1}));assert.throws(()=>m.decode(text,{game:'a',version:2}));assert.throws(()=>m.decode(m.encode('a',3,{}),{game:'a',version:1}));assert.throws(()=>m.encode('a',1,{x:NaN}));});
 test('storage failures propagate',()=>{assert.throws(()=>m.writeSave({setItem(){throw Error('quota')}},'a','b'));assert.throws(()=>m.writeSave({setItem(){},getItem(){return 'old'}},'a','new'));assert.throws(()=>m.decode('bad',{game:'a',version:1}));});
