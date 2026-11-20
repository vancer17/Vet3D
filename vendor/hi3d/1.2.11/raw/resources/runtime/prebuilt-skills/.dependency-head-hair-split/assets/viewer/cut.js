/* Static-mesh binary graph cut. Integer Dinic, no recursion, no network. */
const SplitCut = (() => {
  function views(buffer, meta) {
    const d={}; for(const [k,f] of Object.entries(meta.fields)) {
      const T=f.dtype.endsWith('f8')?Float64Array:f.dtype.endsWith('f4')?Float32Array:Uint32Array;
      d[k]=new T(buffer,f.offset,f.length);
    } return d;
  }
  function adjacency(d,n) {
    const row=new Uint32Array(n+1), m=d.a.length;
    for(let e=0;e<m;e++){row[d.a[e]+1]++;row[d.b[e]+1]++;}
    for(let i=1;i<=n;i++)row[i]+=row[i-1];
    const col=new Uint32Array(2*m),edge=new Uint32Array(2*m),ptr=row.slice();
    for(let e=0;e<m;e++){let k=ptr[d.a[e]]++;col[k]=d.b[e];edge[k]=e;k=ptr[d.b[e]]++;col[k]=d.a[e];edge[k]=e;}
    return {row,col,edge};
  }
  function roundEven(v){const f=Math.floor(v),r=v-f;return r===.5?(f%2?f+1:f):Math.round(v);}
  const quant=x=>Math.min(Math.max(roundEven(x*200),0),1073741824);
  function distances(d,adj,initial,limit) {
    const n=initial.length,dist=new Float64Array(n).fill(Infinity),heap=new Int32Array(n),pos=new Int32Array(n).fill(-1);let size=0;
    function up(i){const u=heap[i];while(i>0){const p=(i-1)>>1;if(dist[heap[p]]<=dist[u])break;heap[i]=heap[p];pos[heap[i]]=i;i=p;}heap[i]=u;pos[u]=i;}
    for(let e=0;e<d.a.length;e++)if(initial[d.a[e]]!==initial[d.b[e]]){
      for(const v of [d.a[e],d.b[e]])if(dist[v]!==0){dist[v]=0;pos[v]=size;heap[size++]=v;}
    }
    while(size){
      const u=heap[0];pos[u]=-2;const last=heap[--size];
      if(size){let k=0;while(2*k+1<size){let c=2*k+1;if(c+1<size&&dist[heap[c+1]]<dist[heap[c]])c++;if(dist[last]<=dist[heap[c]])break;heap[k]=heap[c];pos[heap[k]]=k;k=c;}heap[k]=last;pos[last]=k;}
      for(let k=adj.row[u];k<adj.row[u+1];k++){
        const v=adj.col[k],nd=dist[u]+d.distance[adj.edge[k]];
        if(pos[v]===-2||nd>limit||nd>=dist[v])continue;
        dist[v]=nd;if(pos[v]<0){pos[v]=size;heap[size++]=v;}up(pos[v]);
      }
    }return dist;
  }
  function dinic(n,edges,S,T,progress) {
    const head=new Int32Array(n).fill(-1),to=new Int32Array(edges.length*2),next=new Int32Array(edges.length*2),cap=new Float64Array(edges.length*2);let count=0;
    function add(u,v,c,r){to[count]=v;cap[count]=c;next[count]=head[u];head[u]=count++;to[count]=u;cap[count]=r;next[count]=head[v];head[v]=count++;}
    for(const e of edges)add(...e);edges.length=0;
    const level=new Int32Array(n),cur=new Int32Array(n),queue=new Int32Array(n),pv=new Int32Array(n),pe=new Int32Array(n);let flow=0,rounds=0;
    function bfs(){level.fill(-1);let h=0,t=1;queue[0]=S;level[S]=0;while(h<t){const u=queue[h++];for(let e=head[u];e>=0;e=next[e])if(cap[e]>0&&level[to[e]]<0){level[to[e]]=level[u]+1;queue[t++]=to[e];}}return level[T]>=0;}
    while(bfs()){
      cur.set(head);let depth=0;pv[0]=S;
      while(true){
        const u=pv[depth];
        if(u===T){let f=Infinity;for(let k=0;k<depth;k++)f=Math.min(f,cap[pe[k]]);for(let k=0;k<depth;k++){const e=pe[k];cap[e]-=f;cap[e^1]+=f;}flow+=f;depth=0;continue;}
        let e=cur[u];while(e>=0&&!(cap[e]>0&&level[to[e]]===level[u]+1))e=next[e];cur[u]=e;
        if(e<0){level[u]=-1;if(depth===0)break;depth--;cur[pv[depth]]=next[pe[depth]];}
        else{pe[depth]=e;pv[++depth]=to[e];}
      }
      if(++rounds%10===0)progress(`最小割 · ${rounds} 轮`);
    }
    const reach=new Uint8Array(n);let h=0,t=1;queue[0]=S;reach[S]=1;
    while(h<t){const u=queue[h++];for(let e=head[u];e>=0;e=next[e])if(cap[e]>0&&!reach[to[e]]){reach[to[e]]=1;queue[t++]=to[e];}}
    return {reach,flow,rounds};
  }
  function cleanup(d,meta,lab,initial){
    const n=lab.length,parent=new Int32Array(n),mass=new Float64Array(n);
    function find(a){let r=a;while(parent[r]!==r)r=parent[r];while(parent[a]!==a){let k=parent[a];parent[a]=r;a=k;}return r;}
    for(let iter=0;iter<4;iter++){
      let changed=0;
      for(let L=0;L<2;L++){
        for(let i=0;i<n;i++)parent[i]=i;mass.fill(0);
        for(let e=0;e<d.a.length;e++){const a=d.a[e],b=d.b[e];if(lab[a]!==L||lab[b]!==L||d.component[a]!==meta.mainComponent)continue;let u=find(a),v=find(b);if(u!==v)parent[Math.max(u,v)]=Math.min(u,v);}
        let best=-1,bestMass=-1;
        for(let i=0;i<n;i++)if(lab[i]===L&&d.component[i]===meta.mainComponent)mass[find(i)]+=d.area[i];
        for(let i=0;i<n;i++)if(mass[i]>bestMass){bestMass=mass[i];best=i;}
        if(bestMass<=0)continue;
        for(let i=0;i<n;i++)if(lab[i]===L&&d.component[i]===meta.mainComponent&&find(i)!==best){lab[i]=1-L;changed++;}
      }if(!changed)break;
    }
    for(const s of meta.shells){let label=0;if(s.hidden){let total=0;for(const i of s.nearest)total+=lab[i];label=+(total>.5*s.nearest.length);}else{let total=0,white=0;for(const i of s.faces){total+=d.area[i];white+=d.area[i]*initial[i];}label=+(white>.5*total);}for(const i of s.faces)lab[i]=label;}
  }
  function solve(d,meta,threshold,progress=()=>{},adj=null){
    if(!(threshold>0&&threshold<1))throw Error('阈值必须在 0 和 1 之间');
    const start=performance.now(),n=meta.faces,initial=new Uint8Array(n);let whites=0;
    for(let i=0;i<n;i++){initial[i]=+(d.lum[i]>threshold);whites+=initial[i];}
    if(!whites||whites===n)throw Error('当前阈值只有一个类别，请调整阈值');
    let boundary=false;for(let e=0;e<d.a.length;e++)if(initial[d.a[e]]!==initial[d.b[e]]){boundary=true;break;}
    if(!boundary)return {labels:initial,stats:{threshold,faces:n,head:n-whites,hair:whites,free_triangles:0,cut_value:0,flow_value:0,rounds:0,seconds:(performance.now()-start)/1000}};
    progress('构建边界距离');adj=adj||adjacency(d,n);const diag=meta.diagonal,bb=.12*diag,wb=.005*diag,dist=distances(d,adj,initial,bb*1.01);
    const index=new Int32Array(n).fill(-1),seeds=new Int8Array(n).fill(-1);let free=0;
    for(let i=0;i<n;i++){if(initial[i]&&!(dist[i]<=wb))seeds[i]=1;else if(!initial[i]&&!(dist[i]<=bb))seeds[i]=0;else index[i]=free++;}
    const S=free,T=free+1,cs=new Float64Array(free),ct=new Float64Array(free);
    for(let i=0;i<n;i++)if(index[i]>=0){const u=(initial[i]?1:-1)*Math.min(dist[i],bb)/diag*d.area[i];cs[index[i]]=Math.max(u,0);ct[index[i]]=Math.max(-u,0);}
    // Flat JS edge records are released before maxflow; only boundary band enters graph.
    const edges=[];const pair=[];
    for(let e=0;e<d.a.length;e++){
      const a=d.a[e],b=d.b[e],ia=index[a],ib=index[b],w=d.weight[e];
      if(ia>=0&&ib>=0){const q=Math.max(quant(w),1);edges.push([ia,ib,q,q]);pair.push([ia,ib,q]);}
      else if(ia>=0){if(seeds[b])cs[ia]+=w;else ct[ia]+=w;}
      else if(ib>=0){if(seeds[a])cs[ib]+=w;else ct[ib]+=w;}
    }
    for(let i=0;i<free;i++){cs[i]=quant(cs[i]);ct[i]=quant(ct[i]);if(cs[i]>0)edges.push([S,i,cs[i],0]);if(ct[i]>0)edges.push([i,T,ct[i],0]);}
    progress(`最小割 · ${free.toLocaleString()} 个可变面`);
    const {reach,flow,rounds}=dinic(free+2,edges,S,T,progress);let cut=0;
    for(let i=0;i<free;i++)cut+=reach[i]?ct[i]:cs[i];for(const [i,j,w] of pair)if(reach[i]!==reach[j])cut+=w;
    if(cut!==flow)throw Error('最大流/最小割校验失败');
    const labels=new Uint8Array(n);for(let i=0;i<n;i++)labels[i]=index[i]>=0?reach[index[i]]:seeds[i];
    progress('连通域与隐藏壳整理');cleanup(d,meta,labels,initial);let hair=0;for(const x of labels)hair+=x;
    if(!hair||hair===n)throw Error('图割后类别为空，未生成导出');
    return {labels,stats:{threshold,faces:n,head:n-hair,hair,free_triangles:free,cut_value:cut,flow_value:flow,rounds,seconds:(performance.now()-start)/1000}};
  }
  return {views,adjacency,solve,roundEven};
})();
if(typeof module!=='undefined')module.exports=SplitCut;
