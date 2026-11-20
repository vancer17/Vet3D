import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('shortest legal path and budget',()=>{const g=[[0,1,0],[0,0,0]];const r=m.findPath(g,[0,0],[2,0]);assert.equal(r.status,'found');assert.equal(r.path.length,5);assert.equal(m.findPath(g,[0,0],[2,0],{maxVisited:1}).status,'budget');assert.equal(m.findPath([[0,1,0]],[0,0],[2,0]).status,'unreachable');});
 test('blocked and invalid grids',()=>{assert.equal(m.findPath([[1]],[0,0],[0,0]).status,'blocked');assert.throws(()=>m.findPath([[0],[0,0]],[0,0],[0,1]));assert.throws(()=>m.findPath([[0]],[1,0],[0,0]));});
