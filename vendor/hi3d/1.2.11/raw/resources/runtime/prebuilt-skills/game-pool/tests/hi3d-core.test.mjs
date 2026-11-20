import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('bounded acquire and reuse invalidates old lease',()=>{const a=m.acquire(m.createPool(1));assert(m.isAlive(a.pool,a.handle));assert.equal(m.acquire(a.pool).handle,null);const released=m.release(a.pool,a.handle),b=m.acquire(released);assert(!m.isAlive(b.pool,a.handle));assert(m.isAlive(b.pool,b.handle));assert.equal(m.release(b.pool,a.handle),b.pool);});
 test('configuration and immutable input',()=>{assert.throws(()=>m.createPool(0));const p=m.createPool(2);m.acquire(p);assert.equal(p.slots[0].active,false);assert(!m.isAlive(p,null));});
