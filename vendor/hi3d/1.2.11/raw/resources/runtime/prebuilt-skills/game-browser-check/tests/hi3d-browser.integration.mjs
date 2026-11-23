import {createServer} from 'node:http';
import assert from 'node:assert/strict';
import {checkBrowser} from '../scripts/hi3d-core.mjs';
/** Caller provisions browser; local fixture server never reaches external services. */
export async function verifyBrowser(browser){
 const server=createServer((req,res)=>{
  if(req.url==='/hi3d-asset.json'){res.setHeader('content-type','application/json');res.end('{"ready":true}');return;}
  if(req.url==='/missing.json'){res.statusCode=404;res.end('missing');return;}
  const bad=req.url==='/broken';res.setHeader('content-type','text/html');
  res.end(`<!doctype html><html><head><meta charset="utf-8"><title>Game check fixture</title></head><body><button id="start">Start</button><div id="result">Ready</div><script>document.querySelector('#start').onclick=async()=>{const r=await fetch('${bad?'/missing.json':'/hi3d-asset.json'}');document.querySelector('#result').textContent=r.ok?'Playing':'Failed';};</script></body></html>`);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
 try{
  const scenario={url:origin+'/',timeoutMs:3000,steps:[{action:'click',selector:'#start'},{action:'visible',selector:'#result:text-is("Playing")'}]};
  const good=await checkBrowser(browser,scenario);assert(good.passed);assert(good.requests.some(r=>r.path==='/hi3d-asset.json'));
  const bad=await checkBrowser(browser,{...scenario,url:origin+'/broken',steps:[{action:'click',selector:'#start'},{action:'visible',selector:'#result:text-is("Failed")'}]});assert(!bad.passed);assert(bad.errors.some(e=>e.status===404));
  const count=browser.contexts().length;await assert.rejects(()=>checkBrowser(browser,{...scenario,steps:[{action:'visible',selector:'#never'}],timeoutMs:100}));assert.equal(browser.contexts().length,count);
  return {good,missingResourceDetected:!bad.passed,contextCleanup:true};
 }finally{await new Promise(resolve=>server.close(resolve));}
}
