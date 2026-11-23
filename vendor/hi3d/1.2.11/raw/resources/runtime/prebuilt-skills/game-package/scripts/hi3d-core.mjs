/** Validate declarative game package manifests; never unpack or execute content. */
export function validateManifest(m){
 const issues=[];const safe=p=>typeof p==='string'&&p.length>0&&p.length<=512&&!p.includes('\\')&&!p.includes('%')&&!p.includes(':')&&!p.startsWith('/')&&!p.split('/').some(x=>!x||x==='.'||x==='..')&&!/[\x00-\x1f]/.test(p);
 if(!m||m.schema!=='game-package.v1'||typeof m.id!=='string'||!/^[a-z0-9][a-z0-9-]{0,63}$/.test(m.id)||typeof m.version!=='string'||!/^\d+\.\d+\.\d+$/.test(m.version))issues.push('invalid package identity');
 if(!Array.isArray(m?.files)||!m.files.length||m.files.length>10000)return {valid:false,issues:[...issues,'invalid file list']};
 const paths=new Set();let bytes=0;for(const f of m.files){if(!f||!safe(f.path)||paths.has(f.path)||typeof f.sha256!=='string'||!/^[a-f0-9]{64}$/.test(f.sha256)||!Number.isSafeInteger(f.bytes)||f.bytes<0||f.bytes>1073741824){issues.push('invalid file entry');continue;}paths.add(f.path);bytes+=f.bytes;}
 if(bytes>8589934592)issues.push('package size exceeds 8 GiB');if(!safe(m.entry)||!paths.has(m.entry))issues.push('entry missing');
 if(!Array.isArray(m.permissions)||!m.permissions.every(p=>['network','audio','pointer-lock','storage'].includes(p)))issues.push('unknown permission');
 return {valid:!issues.length,issues,bytes};
}
