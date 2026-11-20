/** Frame-time statistics from actual caller-provided measurements. */
export function profile(samples,{budgetMs=16.67}={}){
 if(!Array.isArray(samples)||!samples.length||samples.length>1000000||!samples.every(n=>Number.isFinite(n)&&n>0)||!Number.isFinite(budgetMs)||budgetMs<=0)throw new Error('invalid frame samples');
 const sorted=[...samples].sort((a,b)=>a-b),quantile=q=>sorted[Math.ceil(q*sorted.length)-1],mean=samples.reduce((a,b)=>a+b/samples.length,0);
 if(!Number.isFinite(mean))throw new Error('sample magnitude overflow');
 return {count:samples.length,meanMs:mean,p50Ms:quantile(.5),p95Ms:quantile(.95),p99Ms:quantile(.99),meanFps:1000/mean,overBudget:samples.filter(n=>n>budgetMs).length};
}
export function quality(current,stats,{budgetMs=16.67,min=0,max=3}={}){if(!Number.isSafeInteger(current)||!Number.isSafeInteger(min)||!Number.isSafeInteger(max)||min>max||current<min||current>max||!Number.isFinite(stats.p95Ms)||!Number.isFinite(budgetMs)||budgetMs<=0)throw new Error('invalid quality tier');return stats.p95Ms>budgetMs*1.2?Math.max(min,current-1):stats.p95Ms<budgetMs*.7?Math.min(max,current+1):current;}
