import { mkdtemp, mkdir, writeFile, readFile, rm, lstat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { RuntimeStorage } from '../src/main/runtime-storage.ts';
const base = await mkdtemp(join(tmpdir(), 'hi3d-review-'));
try {
  const source = join(base, 'source', '.data');
  const parent = join(base, "user's files");
  await mkdir(join(source, 'codex-home'), {recursive:true}); await mkdir(parent);
  await writeFile(join(source, 'codex-home', 'config.toml'), `[projects.'${source}']\ntrust_level = 'trusted'\n`);
  const storage = new RuntimeStorage(source, join(base, 'settings'));
  const target = await storage.schedule(parent); await storage.migrate();
  console.log('TOML_AFTER', JSON.stringify(await readFile(join(target, 'codex-home', 'config.toml'), 'utf8')));
  console.log('SOURCE_REMOVED', await lstat(source).then(()=>false,()=>true));
  const installed = join(base, 'installed-app'); await mkdir(installed);
  console.log('APP_DIRECTORY_ACCEPTED', await storage.schedule(installed));
} finally {
  if (!resolve(base).startsWith(resolve(tmpdir()) + '\\hi3d-review-')) throw new Error('unexpected temp path');
  await rm(base, {recursive:true,force:true});
}
