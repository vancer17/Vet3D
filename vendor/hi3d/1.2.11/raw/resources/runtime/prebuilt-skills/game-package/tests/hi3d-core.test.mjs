import test from 'node:test';
import assert from 'node:assert/strict';
import * as m from '../scripts/hi3d-core.mjs';
const good={schema:'game-package.v1',id:'sample',version:'1.0.0',entry:'index.html',permissions:[],files:[{path:'index.html',bytes:123,sha256:'a'.repeat(64)}]};
 test('identity, paths, duplicates, entry',()=>{assert(m.validateManifest(good).valid);for(const path of ['../secret','/etc/file','a\\b','%2e%2e/x','a/../b'])assert(!m.validateManifest({...good,files:[{...good.files[0],path}]}).valid);assert(!m.validateManifest({...good,files:[...good.files,...good.files]}).valid);assert(!m.validateManifest({...good,entry:'absent'}).valid);});
 test('permission and size limits',()=>{assert(!m.validateManifest({...good,permissions:['shell']}).valid);assert(!m.validateManifest({...good,files:[{...good.files[0],bytes:-1}]}).valid);assert(!m.validateManifest(null).valid);});
