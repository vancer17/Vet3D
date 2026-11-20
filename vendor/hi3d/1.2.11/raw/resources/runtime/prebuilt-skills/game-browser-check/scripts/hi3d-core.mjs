/** Scenario runner accepting an already provisioned Playwright Browser instance. */
export async function checkBrowser(browser,scenario){
 const url=new URL(scenario.url);if(!['http:','https:'].includes(url.protocol)||!Array.isArray(scenario.steps)||scenario.steps.length>100)throw new Error('invalid browser scenario');
 if(!Number.isSafeInteger(scenario.timeoutMs)||scenario.timeoutMs<1||scenario.timeoutMs>30000)throw new Error('timeoutMs must be 1..30000');
 const allowed=new Set(scenario.allowedOrigins||[url.origin]);if(!allowed.has(url.origin))throw new Error('entry origin not allowed');
 const context=await browser.newContext({serviceWorkers:'block',viewport:scenario.viewport||{width:1280,height:720}});const errors=[],requests=[];
 try{const page=await context.newPage();page.setDefaultTimeout(scenario.timeoutMs);
  await context.route('**/*',route=>{const u=new URL(route.request().url());if(!allowed.has(u.origin)){errors.push({type:'external',url:u.origin+u.pathname});return route.abort();}return route.continue();});
  page.on('pageerror',e=>errors.push({type:'script',message:e.message}));
  page.on('requestfailed',r=>errors.push({type:'request',url:new URL(r.url()).pathname}));
  page.on('response',r=>{const u=new URL(r.url());requests.push({path:u.pathname,status:r.status()});if(r.status()>=400)errors.push({type:'http',path:u.pathname,status:r.status()});});
  await page.goto(scenario.url,{waitUntil:'load',timeout:scenario.timeoutMs});
  for(const step of scenario.steps){const locator=page.locator(step.selector);switch(step.action){case 'click':await locator.click();break;case 'fill':await locator.fill(step.value);break;case 'press':await locator.press(step.value);break;case 'visible':await locator.waitFor({state:'visible'});break;case 'text':{const text=await locator.innerText();if(text!==step.value)throw new Error(`unexpected text at ${step.selector}`);break;}default:throw new Error('unsupported scenario action');}}
  // The last visible/text assertion must correspond to application readiness.
  if(!scenario.steps.length||!['visible','text'].includes(scenario.steps.at(-1).action))throw new Error('final readiness assertion required');
  return {passed:errors.length===0,errors,requests};
 }finally{await context.close();}
}
