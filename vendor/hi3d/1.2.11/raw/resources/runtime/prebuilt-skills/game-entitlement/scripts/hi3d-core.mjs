/** Reducer for already verified provider events. No payment verification here. */
export function applyEvent(state,event){
 const {id,order,user,product,revision,status}=event;
 if(![id,order,user,product].every(x=>typeof x==='string'&&x.length>0&&x.length<=128)||!Number.isSafeInteger(revision)||revision<1||!['paid','refunded','revoked'].includes(status))throw new Error('invalid entitlement event');
 if(state.order!==order||state.user!==user||state.product!==product)throw new Error('identity mismatch');
 const old=state.events.find(e=>e.id===id);if(old){if(old.revision!==revision||old.status!==status)throw new Error('event id conflict');return state;}
 if(revision<=state.revision)throw new Error('stale or conflicting event revision');
 if(state.events.length>=10000)throw new Error('event limit');
 if(['refunded','revoked'].includes(state.status)&&status==='paid')throw new Error('terminal order; purchase requires new order');
 return {...state,revision,status,events:[...state.events,{id,revision,status}]};
}
export function canDownload(state,{user,product}){return state.user===user&&state.product===product&&state.status==='paid';}
