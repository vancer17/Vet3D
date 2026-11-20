/** Integer soft-currency ledger. Not a payment processor. */
export function transact(state,{id,cost,reward}){
 if(typeof id!=='string'||!id||id.length>128||![state.balance,cost,reward].every(n=>Number.isSafeInteger(n)&&n>=0))throw new Error('invalid transaction');
 const old=state.receipts?.find(r=>r.id===id);if(old){if(old.cost!==cost||old.reward!==reward)throw new Error('idempotency conflict');return state;}
 if(state.balance<cost)throw new Error('insufficient currency');
 const balance=state.balance-cost+reward;if(!Number.isSafeInteger(balance))throw new Error('balance overflow');
 if((state.receipts?.length||0)>=10000)throw new Error('ledger limit; persist/archive before continuing');
 return {...state,balance,receipts:[...(state.receipts||[]),{id,cost,reward}]};
}
export function offlineReward(elapsed,rate,cap){if(![elapsed,rate,cap].every(n=>Number.isFinite(n)&&n>=0))throw new Error('invalid reward parameters');const reward=Math.floor(Math.min(elapsed,cap)*rate);if(!Number.isSafeInteger(reward))throw new Error('reward overflow');return reward;}
