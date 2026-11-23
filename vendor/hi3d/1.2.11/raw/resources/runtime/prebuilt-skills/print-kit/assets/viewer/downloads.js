/* Downloads are independent of WebGL and work from an embedded offline payload. */
const printKitURLs=[];
function printKitBlob(base64,mime){
 const bytes=Uint8Array.from(atob(base64),c=>c.charCodeAt(0));
 const url=URL.createObjectURL(new Blob([bytes],{type:mime}));printKitURLs.push(url);return url;
}
for(const [id,item] of Object.entries(window.PRINT_KIT.downloads)){
 const link=document.getElementById(id);link.href=printKitBlob(item.base64,item.mime);link.download=item.filename;
}
addEventListener('pagehide',event=>{if(!event.persisted)printKitURLs.forEach(url=>URL.revokeObjectURL(url));});
