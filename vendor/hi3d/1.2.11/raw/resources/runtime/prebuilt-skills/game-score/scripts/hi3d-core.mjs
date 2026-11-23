/** Rank already validated score records, scoped to one game. */
export function rankScores(records,{game,player=null,limit=10}={}){
 if(typeof game!=='string'||!game||!Array.isArray(records)||records.length>100000||!Number.isSafeInteger(limit)||limit<1||limit>1000)throw new Error('invalid leaderboard request');
 const best=new Map();for(const r of records){if(r.game!==game)continue;if(typeof r.player!=='string'||!r.player||!Number.isSafeInteger(r.score)||r.score<0)throw new Error('invalid score');if(!best.has(r.player)||r.score>best.get(r.player).score)best.set(r.player,{player:r.player,score:r.score});}
 const all=[...best.values()].sort((a,b)=>b.score-a.score||(a.player<b.player?-1:a.player>b.player?1:0));let rank=0;const ranked=all.map((r,i)=>{if(i===0||r.score!==all[i-1].score)rank=i+1;return {...r,rank};});return {top:ranked.slice(0,limit),self:ranked.find(r=>r.player===player)||null,total:ranked.length};
}
