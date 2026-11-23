import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, existsSync, symlinkSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { buildHost } from '../scripts/host-bundle.mjs';
import fs from 'node:fs';
import { syncBuiltinESMExports } from 'node:module';

// Any filesystem rename is forbidden, including the standalone build path.
function renameFaults(t, move) {
  const counts = new Map();
  const rename = t.mock.method(fs, 'renameSync', (from, to) => {
    counts.set(from, (counts.get(from) ?? 0) + 1);
    return move(from, to);
  });
  syncBuiltinESMExports();
  t.after(() => { rename.mock.restore(); syncBuiltinESMExports(); });
  return { counts };
}
function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'host-fixture-'));t.after(()=>rmSync(root,{recursive:true,force:true}));
  const repo=join(root,'repo');
  const write=(path,value)=>{mkdirSync(join(repo,path,'..'),{recursive:true});writeFileSync(join(repo,path), typeof value==='string'?value:JSON.stringify(value));};
  for (const name of ['tools','skills','workflows','doc'])mkdirSync(join(repo,name),{recursive:true});
  write('README.md','# Repository');write('AGENTS.md','# Rules');write('doc/README.md','[home](../README.md)');
  for (const owner of ['tools/package-tools','tools/generator','skills/core']) {
    write(`${owner}/SKILL.md`,`---\nname: ${owner.split('/')[1]}\ndescription: fixture\n---\n[code](scripts/main.py)\n`);
    write(`${owner}/scripts/main.py`,'old');write(`${owner}/package.json`,{schema:1,files:{},requires:[]});
  }
  write('tools/package-tools/profiles/sparc3d.json',{schema:1,entries:['generator'],aliases:{generator:'hi3d'}});
  write('skills/core/scripts/core.py','shared');
  write('tools/generator/scripts/account.py','account');
  write('tools/generator/package.json',{schema:1,files:{'scripts/core.py':'skills/core/scripts/core.py'},requires:[],profiles:{sparc3d:{files:{'scripts/main.py':'tools/generator/scripts/account.py'}}}});
  return {root,repo,write};
}
test('host profile materializes shared sources, aliases and hidden references reproducibly',t=>{
  const f=fixture(t),a=join(f.root,'a'),b=join(f.root,'b');buildHost({repo:f.repo,output:a});buildHost({repo:f.repo,output:b});
  assert.equal(readFileSync(join(a,'hi3d/scripts/main.py'),'utf8'),'account');
  assert.equal(readFileSync(join(a,'hi3d/scripts/core.py'),'utf8'),'shared');
  assert.match(readFileSync(join(a,'hi3d/SKILL.md'),'utf8'),/name: hi3d/);
  assert.ok(existsSync(join(a,'.dependency-core/REFERENCE.md')));
  assert.ok(!existsSync(join(a,'.dependency-core/SKILL.md')));
  assert.ok(!existsSync(join(a,'hi3d/scripts/account.py')));
  assert.equal(readFileSync(join(a,'.workflow-bundle.json'),'utf8'),readFileSync(join(b,'.workflow-bundle.json'),'utf8'));
  assert.throws(()=>buildHost({repo:f.repo,output:a}),/already exists/);
});
test('source changes rebuild only the affected bytes and broken links never publish partial output',t=>{
  const f=fixture(t),a=join(f.root,'a'),b=join(f.root,'b');buildHost({repo:f.repo,output:a});
  f.write('skills/core/scripts/core.py','changed');buildHost({repo:f.repo,output:b});
  assert.equal(readFileSync(join(a,'hi3d/scripts/main.py'),'utf8'),readFileSync(join(b,'hi3d/scripts/main.py'),'utf8'));
  assert.notEqual(readFileSync(join(a,'hi3d/scripts/core.py'),'utf8'),readFileSync(join(b,'hi3d/scripts/core.py'),'utf8'));
  f.write('tools/generator/references/bad.md','[missing](no.md)');
  const output=join(f.root,'bad');assert.throws(()=>buildHost({repo:f.repo,output}),/Unresolved/);assert.ok(!existsSync(output));
});
test('unsafe sources and destinations fail without reading credential files',t=>{
  const f=fixture(t);f.write('tools/generator/.env','synthetic-secret');
  const good=join(f.root,'good');buildHost({repo:f.repo,output:good});assert.ok(!existsSync(join(good,'hi3d/.env')));
  f.write('tools/generator/package.json',{schema:1,files:{'escape.py':'tools/generator/.env'},requires:[]});
  assert.throws(()=>buildHost({repo:f.repo,output:join(f.root,'bad')}),/Unsafe/);
  f.write('tools/generator/package.json',{schema:1,files:{},requires:[]});
  symlinkSync(join(f.repo,'skills/core/scripts/core.py'),join(f.repo,'tools/generator/link.py'));
  assert.throws(()=>buildHost({repo:f.repo,output:join(f.root,'link')}),/Symlink/);
  assert.throws(()=>buildHost({repo:f.repo,output:join(f.repo,'output')}),/outside/);
});
test('account tools isolate public implementations while retaining source references',t=>{
  const f=fixture(t);
  f.write('tools/generator/package.json',{schema:1,files:{},requires:[],profiles:{sparc3d:{archiveBase:true,files:{
    'SKILL.md':'tools/generator/references/account.md',
    'scripts/main.py':'tools/generator/scripts/account.py'
  }}}});
  f.write('tools/generator/references/account.md','---\nname: generator\ndescription: account\n---\n[client](../scripts/account.py)');
  const output=join(f.root,'archive');buildHost({repo:f.repo,output});
  assert.equal(readFileSync(join(output,'hi3d/scripts/main.py'),'utf8'),'account');
  assert.equal(readFileSync(join(output,'.dependency-generator-source/scripts/main.py'),'utf8'),'old');
  assert.ok(!existsSync(join(output,'.dependency-generator-source/SKILL.md')));
  assert.match(readFileSync(join(output,'hi3d/SKILL.md'),'utf8'),/\(scripts\/main.py\)/);
});

for (const allowExisting of [false, true]) test(`direct build (allowExisting=${allowExisting}) never renames or stages directories`, t => {
  const f = fixture(t), output = join(f.root, 'installed');
  const faults = renameFaults(t, () => { throw new Error('rename forbidden'); });
  const options = { repo: f.repo, output, allowExisting, entrySuffix: '\n<!-- managed -->\n' };
  buildHost(options);
  assert.equal(readFileSync(join(output, 'hi3d/scripts/main.py'), 'utf8'), 'account');
  assert.match(readFileSync(join(output, 'hi3d/SKILL.md'), 'utf8'), /managed/);
  f.write('skills/core/scripts/core.py', 'updated');
  options.allowExisting = true;
  buildHost(options);
  assert.equal(readFileSync(join(output, 'hi3d/scripts/core.py'), 'utf8'), 'updated');
  assert.equal(faults.counts.size, 0);
  assert.ok(!fs.readdirSync(f.root).some(name => name.startsWith('.host-bundle-')));
  const previous = readFileSync(join(output, 'hi3d/SKILL.md'), 'utf8');
  f.write('tools/generator/SKILL.md', '[broken](missing.md)');
  assert.throws(() => buildHost(options), /Unresolved/);
  assert.equal(readFileSync(join(output, 'hi3d/SKILL.md'), 'utf8'), previous);
});

test('an interrupted in-place write retains managed entries and can be completed', t => {
  const f = fixture(t), output = join(f.root, 'partial');
  const original = fs.writeFileSync;
  const failure = t.mock.method(fs, 'writeFileSync', (path, ...args) => {
    if (String(path) === join(output, 'hi3d/scripts/main.py')) throw new Error('interrupted write');
    return original(path, ...args);
  });
  syncBuiltinESMExports();
  t.after(() => { failure.mock.restore(); syncBuiltinESMExports(); });
  const options = { repo: f.repo, output, allowExisting: true, entrySuffix: '\n<!-- managed -->\n' };
  assert.throws(() => buildHost(options), /interrupted write/);
  assert.match(readFileSync(join(output, 'hi3d/SKILL.md'), 'utf8'), /managed/);
  assert.ok(!existsSync(join(output, '.workflow-bundle.json')));
  failure.mock.restore(); syncBuiltinESMExports();
  buildHost(options);
  assert.equal(readFileSync(join(output, 'hi3d/scripts/main.py'), 'utf8'), 'account');
  assert.ok(existsSync(join(output, '.workflow-bundle.json')));
});
