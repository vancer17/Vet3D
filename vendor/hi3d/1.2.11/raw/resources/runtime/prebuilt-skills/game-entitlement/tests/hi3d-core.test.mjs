import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
const s={order:'o',user:'u',product:'p',revision:0,status:'pending',events:[]},e={id:'e',order:'o',user:'u',product:'p',revision:1,status:'paid'};
 test('grant, idempotency, identity',()=>{const r=m.applyEvent(s,e);assert(m.canDownload(r,{user:'u',product:'p'}));assert.equal(m.applyEvent(r,e),r);assert(!m.canDownload(r,{user:'other',product:'p'}));assert.throws(()=>m.applyEvent(s,{...e,user:'other'}));});
 test('refund terminal and out of order',()=>{const r=m.applyEvent(m.applyEvent(s,e),{...e,id:'refund',revision:2,status:'refunded'});assert(!m.canDownload(r,{user:'u',product:'p'}));assert.throws(()=>m.applyEvent(r,{...e,id:'again',revision:3}));assert.throws(()=>m.applyEvent(r,{...e,id:'late'}));});
