/** Bounded four-neighbour shortest path for binary grids. */
export function findPath(grid,start,goal,{maxVisited=100000}={}){
 const h=grid.length,w=grid[0]?.length;if(!h||!w||h*w>1000000||!grid.every(r=>r.length===w&&r.every(v=>v===0||v===1)))throw new Error('invalid binary grid');
 if(!Number.isSafeInteger(maxVisited)||maxVisited<1||maxVisited>1000000)throw new Error('invalid budget');
 const valid=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isSafeInteger)&&p[0]>=0&&p[0]<w&&p[1]>=0&&p[1]<h;
 if(!valid(start)||!valid(goal))throw new Error('coordinate out of bounds');
 if(grid[start[1]][start[0]]||grid[goal[1]][goal[0]])return {status:'blocked',path:[],visited:0};
 const key=(x,y)=>y*w+x,first=key(...start),last=key(...goal),queue=[first],parents=new Map([[first,null]]);let head=0;
 while(head<queue.length&&head<maxVisited){const k=queue[head++];if(k===last){const path=[];for(let p=k;p!==null;p=parents.get(p))path.push([p%w,Math.floor(p/w)]);return {status:'found',path:path.reverse(),visited:head};}const x=k%w,y=Math.floor(k/w);for(const [nx,ny] of [[x+1,y],[x,y+1],[x-1,y],[x,y-1]]){if(nx<0||nx>=w||ny<0||ny>=h||grid[ny][nx])continue;const n=key(nx,ny);if(!parents.has(n)){parents.set(n,k);queue.push(n);}}}
 return {status:head<queue.length?'budget':'unreachable',path:[],visited:head};
}
