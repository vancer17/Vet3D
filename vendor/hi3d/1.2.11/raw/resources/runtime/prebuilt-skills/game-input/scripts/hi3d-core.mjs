/** Device-independent action sampling; DOM lifecycle is an explicit adapter. */
export function axis(x,y,deadzone=0.15){
 if(![x,y,deadzone].every(Number.isFinite)||deadzone<0||deadzone>=1)throw new RangeError('invalid axis');
 const length=Math.hypot(x,y);if(length<=deadzone)return [0,0];const scale=(Math.min(length,1)-deadzone)/(1-deadzone);return [x/length*scale,y/length*scale];
}
export function actions(pressed,bindings){
 const set=new Set(pressed);return Object.fromEntries(Object.entries(bindings).map(([action,keys])=>[action,keys.some(k=>set.has(k))]));
}
export function bindKeyboard(target,bindings,onChange){
 const down=new Set();let disposed=false;
 const emit=()=>onChange(actions(down,bindings));
 const key=e=>{if(disposed)return;if(e.type==='keydown'&&(e.target?.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(e.target?.tagName)))return;
 if(!Object.values(bindings).some(keys=>keys.includes(e.code)))return;
 if(e.type==='keydown')down.add(e.code);else down.delete(e.code);e.preventDefault?.();emit();};
 const blur=()=>{down.clear();emit();};
 target.addEventListener('keydown',key);target.addEventListener('keyup',key);target.addEventListener('blur',blur);
 return ()=>{if(disposed)return;disposed=true;target.removeEventListener('keydown',key);target.removeEventListener('keyup',key);target.removeEventListener('blur',blur);blur();};
}
