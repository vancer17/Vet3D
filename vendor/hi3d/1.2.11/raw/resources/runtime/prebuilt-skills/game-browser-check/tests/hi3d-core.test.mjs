import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
test('invalid protocol rejected before browser use',async()=>{await assert.rejects(()=>m.checkBrowser({}, {url:'file:///test',timeoutMs:100,steps:[]}));});
 test('scenario error closes isolated context',async()=>{let closed=false;const page={setDefaultTimeout(){},on(){},async goto(){},locator(){return {async click(){throw Error('not found')}}}};const browser={async newContext(){return {async newPage(){return page},async route(){},async close(){closed=true}}}};await assert.rejects(()=>m.checkBrowser(browser,{url:'http://localhost/',timeoutMs:100,steps:[{action:'click',selector:'#absent'}]}));assert(closed);});
