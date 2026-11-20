/** Materialize a flat host distribution from canonical package manifests. Node 22+, offline. */
import { createHash } from 'node:crypto';
import { existsSync, lstatSync, readdirSync, readFileSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, resolve, relative, posix, sep, isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

const categories = ['tools', 'skills', 'workflows'];
const ignored = /^(?:\.git|\.DS_Store|__pycache__|\.pytest_cache|\.secrets|\.env(?:\..*)?|credentials\.json)$/;
export function safePath(value) {
  if (typeof value !== 'string' || !value || value.includes('\\') || isAbsolute(value)
      || value.split('/').some(part => !part || part === '.' || part === '..' || ignored.test(part))) throw new Error(`Unsafe package path: ${value}`);
  return value;
}
function source(repo, name) {
  safePath(name);
  let path = repo;
  for (const part of name.split('/')) { path = resolve(path, part); if (lstatSync(path).isSymbolicLink()) throw new Error(`Symlink source: ${name}`); }
  if (!lstatSync(path).isFile()) throw new Error(`Not a source file: ${name}`);
  return path;
}
function files(repo, owner) {
  const result = {};
  function visit(dir) {
    for (const entry of readdirSync(resolve(repo, dir), { withFileTypes: true }).sort((a,b) => a.name.localeCompare(b.name, 'en'))) {
      if (ignored.test(entry.name) || /\.py[co]$/.test(entry.name)) continue;
      const name = `${dir}/${entry.name}`;
      if (entry.isSymbolicLink()) throw new Error(`Symlink source: ${name}`);
      if (entry.isDirectory()) visit(name);
      else if (entry.isFile()) result[posix.relative(owner, name)] = name;
    }
  }
  visit(owner); return result;
}
const links = /(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)/g;
function rewrite(text, src, dest, locations, aliases) {
  return text.replace(links, (match, target) => {
    if (/^(?:[a-z][a-z0-9+.-]*:|\/|#)/i.test(target) || target.includes(' ')) return match;
    const index = target.indexOf('#'), path = index < 0 ? target : target.slice(0,index), fragment = index < 0 ? '' : target.slice(index);
    const original = posix.normalize(posix.join(posix.dirname(src), decodeURI(path)));
    const actual = aliases[original] ?? locations[original];
    if (!actual) throw new Error(`Unresolved local link: ${src} -> ${target}`);
    return match.replace(`(${target})`, `(${posix.relative(posix.dirname(dest), actual)}${fragment})`);
  });
}
export function buildHost({ repo, output, profile = 'sparc3d', allowExisting = false, beforeWrite = () => {}, entrySuffix = '' }) {
  repo = resolve(repo); output = resolve(output);
  if (output === repo || output.startsWith(repo + sep)) throw new Error('Output must be outside the source repository');
  if (!allowExisting && existsSync(output)) throw new Error('Output already exists');
  const config = JSON.parse(readFileSync(source(repo, `tools/package-tools/profiles/${safePath(profile)}.json`), 'utf8'));
  if (config.schema !== 1 || !Array.isArray(config.entries) || new Set(config.entries).size !== config.entries.length) throw new Error('Invalid host profile');
  const plans = [], entries = new Map(), names = new Set();
  for (const category of categories) for (const entry of readdirSync(resolve(repo, category), { withFileTypes: true })) {
    if (!entry.isDirectory() || ignored.test(entry.name)) continue;
    const name = entry.name, owner = `${category}/${name}`;
    source(repo, `${owner}/SKILL.md`);
    if (entries.has(name)) throw new Error(`Duplicate entry: ${name}`);
    entries.set(name, owner);
  }
  for (const name of config.entries) if (!entries.has(name)) throw new Error(`Unknown host entry: ${name}`);
  for (const [name, owner] of [...entries].sort()) {
    const manifest = JSON.parse(readFileSync(source(repo, `${owner}/package.json`), 'utf8'));
    if (manifest.schema !== 1 || !manifest.files || !Array.isArray(manifest.requires)) throw new Error(`Invalid manifest: ${owner}`);
    for (const dep of manifest.requires) if (!entries.has(dep)) throw new Error(`Unknown dependency: ${dep}`);
    let plan = files(repo, owner);
    for (const [dest, src] of Object.entries(manifest.files)) {
      safePath(dest); source(repo, src);
      if (dest in plan) throw new Error(`Materialization shadows local resource: ${owner}/${dest}`);
      plan[dest] = src;
    }
    const override = manifest.profiles?.[profile] ?? {};
    if (override.archiveBase) {
      const activeSources = new Set(Object.values(override.files ?? {}));
      const archived = Object.fromEntries(Object.entries(plan).filter(([dest, src]) => dest === 'SKILL.md' || (!activeSources.has(src) && dest !== 'package.json')));
      const archivedName = `.dependency-${name}-source`;
      if (names.has(archivedName)) throw new Error(`Duplicate installed name: ${archivedName}`);
      names.add(archivedName);
      plans.push({ name: `${name}-source`, owner, installed: archivedName, exposed: false, files: archived });
      plan = { 'package.json': `${owner}/package.json` };
    }

    for (const [dest, src] of Object.entries(override.files ?? {})) { safePath(dest); source(repo, src); plan[dest] = src; }
    for (const dest of override.remove ?? []) delete plan[safePath(dest)];
    // An implementation relocated by the profile is shipped once per package.
    for (const [dest, src] of Object.entries(override.files ?? {})) for (const [other, value] of Object.entries(plan)) {
      if (other !== dest && value === src && !(other in (override.files ?? {}))) delete plan[other];
    }
    const exposed = config.entries.includes(name), installed = exposed ? config.aliases?.[name] ?? name : `.dependency-${name}`;
    safePath(installed);
    if (names.has(installed)) throw new Error(`Duplicate installed name: ${installed}`);
    names.add(installed);
    for (const dest of Object.keys(plan)) if (posix.basename(dest) === 'SKILL.md' && dest !== 'SKILL.md') throw new Error(`Nested SKILL.md: ${owner}/${dest}`);
    plans.push({ name, owner, installed, exposed, files: plan });
  }
  const visited = new Set(), active = new Set();
  function checkDependencies(name) {
    if (active.has(name)) throw new Error(`Dependency cycle at ${name}`);
    if (visited.has(name)) return;
    active.add(name);
    const manifest = JSON.parse(readFileSync(source(repo, `${entries.get(name)}/package.json`), 'utf8'));
    for (const dep of manifest.requires) checkDependencies(dep);
    active.delete(name); visited.add(name);
  }
  for (const name of entries.keys()) checkDependencies(name);
  const locations = {}, docs = files(repo, 'doc');
  for (const [dest, src] of Object.entries(docs)) locations[src] = `.dependency-doc/${dest}`;
  for (const name of ['README.md', 'AGENTS.md']) locations[name] = `.dependency-doc/repository-${name}`;
  // Canonical locations and materialized aliases both participate in relocation.
  for (const plan of plans) for (const [dest, src] of Object.entries(plan.files)) {
    const actual = `${plan.installed}/${dest === 'SKILL.md' && !plan.exposed ? 'REFERENCE.md' : dest}`;
    locations[`${plan.owner}/${dest}`] = actual;
    if (!locations[src] || src.startsWith(plan.owner + '/')) locations[src] = actual;
  }
  // Source entry references follow the profile's selected entry content.
  for (const plan of plans) locations[`${plan.owner}/SKILL.md`] = `${plan.installed}/${plan.exposed ? 'SKILL.md' : 'REFERENCE.md'}`;
  for (const plan of plans) {
    locations[plan.owner] = `${plan.installed}/${plan.exposed ? 'SKILL.md' : 'REFERENCE.md'}`;
    for (const dest of Object.keys(plan.files)) {
      let parent = posix.dirname(dest);
      while (parent !== '.') { locations[`${plan.owner}/${parent}`] = `${plan.installed}/${parent}`; parent = posix.dirname(parent); }
    }
  }
  for (const category of categories) locations[category] = `.dependency-doc/repository-README.md#${category}`;
  locations.doc = '.dependency-doc/README.md';
  // Validate and render the entire plan before changing an existing installation.
  // In-place callers own conflict handling, pruning and interrupted-install recovery.
  const prepared = new Map();
  const prepare = (dest, src, aliases = {}) => {
    let bytes = readFileSync(source(repo, src));
    if (src.endsWith('.md')) bytes = Buffer.from(rewrite(bytes.toString('utf8'), src, dest, locations, aliases));
    prepared.set(dest, bytes);
  };
  for (const plan of plans) {
    const aliases = {};
    for (const [dest, src] of Object.entries(plan.files)) aliases[src] = `${plan.installed}/${dest === 'SKILL.md' && !plan.exposed ? 'REFERENCE.md' : dest}`;
    for (const [dest, src] of Object.entries(plan.files)) prepare(`${plan.installed}/${dest === 'SKILL.md' && !plan.exposed ? 'REFERENCE.md' : dest}`, src, aliases);
  }
  for (const [dest, src] of Object.entries(docs)) prepare(`.dependency-doc/${dest}`, src);
  for (const name of ['README.md', 'AGENTS.md']) prepare(`.dependency-doc/repository-${name}`, name);
  if (allowExisting) beforeWrite({
    entries: [...plans.map(plan => ({ name: plan.installed, source: plan.owner })), { name: '.dependency-doc', source: 'doc' }],
    files: [...prepared.keys(), ...plans.map(plan => `${plan.installed}/.runtime-profile.json`), '.dependency-doc/REFERENCE.md'],
  });
  if (allowExisting) {
    // Existing installation paths must not redirect writes outside the output.
    for (const dest of [...prepared.keys(), ...plans.map(plan => `${plan.installed}/.runtime-profile.json`), '.dependency-doc/REFERENCE.md', '.workflow-bundle.json']) {
      let path = output;
      for (const part of ['', ...dest.split('/')]) {
        path = resolve(path, part);
        try { if (lstatSync(path).isSymbolicLink()) throw new Error(`Symlink output: ${path}`); }
        catch (error) { if (error.code !== 'ENOENT') throw error; }
      }
    }
  }
  mkdirSync(dirname(output), { recursive: true });
  // All callers write directly to the final destination. Only an explicit
  // installer may reuse an existing directory.
  mkdirSync(output, { recursive: allowExisting });
  const records = [];
  function emit(dest, src) {
    const path = resolve(output, dest); mkdirSync(dirname(path), { recursive: true });
    const bytes = prepared.get(dest);
    writeFileSync(path, bytes); records.push([dest, src, createHash('sha256').update(bytes).digest('hex')]);
  }
  try {
    for (const plan of plans) {
      // Write the ownership-bearing entry first so an interrupted copy can be repaired.
      const entryName = plan.exposed ? 'SKILL.md' : 'REFERENCE.md';
      const entryDest = `${plan.installed}/${entryName}`;
      let entryText = prepared.get(entryDest).toString('utf8');
      if (plan.exposed) entryText = entryText.replace(/^name:.*$/m, `name: ${plan.installed}`);
      prepared.set(entryDest, Buffer.from(entryText + entrySuffix));
      emit(entryDest, plan.files['SKILL.md']);
      for (const [dest, src] of Object.entries(plan.files)) if (dest !== 'SKILL.md') emit(`${plan.installed}/${dest}`, src);
      writeFileSync(resolve(output, plan.installed, '.runtime-profile.json'), JSON.stringify({ schema: 1, profile, source: plan.owner }) + '\n');
    }
    for (const [dest, src] of Object.entries(docs)) emit(`.dependency-doc/${dest}`, src);
    for (const name of ['README.md', 'AGENTS.md']) emit(`.dependency-doc/repository-${name}`, name);
    writeFileSync(resolve(output, '.dependency-doc', 'REFERENCE.md'), '# Repository reference documentation\n' + entrySuffix);
    const result = { schema: 1, profile, entries: plans.filter(p => p.exposed).map(p => p.installed).sort(), files: records.sort((a,b)=>a[0].localeCompare(b[0], 'en')) };
    writeFileSync(resolve(output, '.workflow-bundle.json'), JSON.stringify(result, null, 2) + '\n');
    return { output, entries: result.entries.length, files: records.length };
  } catch (error) {
    // Fresh CLI output belongs to this invocation. Existing installations are
    // retained for the host's interrupted-install recovery.
    if (!allowExisting) rmSync(output, { recursive: true, force: true });
    throw error;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2), values = {};
  for (let i=0;i<args.length;i+=2) {
    if (!['--repo','--output','--profile'].includes(args[i]) || !args[i+1]) throw new Error('Usage: --repo ROOT --output NEW_DIR [--profile NAME]');
    values[args[i].slice(2)] = args[i+1];
  }
  if (!values.repo || !values.output) throw new Error('--repo and --output are required');
  console.log(JSON.stringify(buildHost(values)));
}
