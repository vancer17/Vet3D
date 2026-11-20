let data,meta,adj,last;
self.onmessage=async({data:m})=>{
 try{
  if(m.type==='init'){meta=m.meta;data=SplitCut.views(m.buffer,meta);adj=SplitCut.adjacency(data,meta.faces);postMessage({type:'ready'});}
  if(m.type==='cut'){last=SplitCut.solve(data,meta,m.threshold,text=>postMessage({type:'progress',text}),adj);postMessage({type:'cut',labels:last.labels,stats:last.stats});}
  if(m.type==='export'){
    if(!last||last.stats.threshold!==m.threshold)throw Error('阈值已改变，请重新运行 mincut');
    const buffer=await StaticFBX.exportFile(data,last.labels,new Uint8Array(m.image),text=>postMessage({type:'progress',text}),meta.material);postMessage({type:'fbx',buffer,stats:last.stats},[buffer]);
  }
 }catch(e){postMessage({type:'error',message:e.message,stack:e.stack});}
};
