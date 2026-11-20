"""Manifest-only nominal checks. Never certifies geometry or an assembled luminaire.
Exit 0: stated nominal checks pass (warnings may remain); 2: blockers/invalid input.
"""
import argparse,json,math,sys
from pathlib import Path

def check_nominal(data,existing_files):
    """Pure nominal validation against an explicit set of existing file strings."""
    errors=[];warnings=[]
    def need(ok,msg):
        if not ok:errors.append(msg)
    def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
    def positive(x):return finite(x) and x>0
    def vector(v):return isinstance(v,list) and len(v)==3 and all(positive(x) for x in v)
    need(data.get('units')=='mm','Manufacturing units must be mm')
    mode=data.get('mode');need(mode in ['concept','fdm','engineering'],'mode must be concept, fdm, or engineering')
    if mode=='concept':warnings.append('Concept scope only: no fabrication validation performed')
    if mode in ['fdm','engineering']:
        hardware=data.get('hardware',{});power=hardware.get('power_W');voltage=hardware.get('voltage_V')
        need(positive(power) and positive(voltage),'Specify positive finite LED voltage/power')
        need(bool(hardware.get('model')) and bool(hardware.get('source_url')),'Hardware model and source are required')
        env=hardware.get('envelope_mm');cavity=hardware.get('installation_envelope_mm')
        need(vector(env) and vector(cavity),'Provide hardware and installation envelope XYZ mm')
        if vector(env) and vector(cavity):need(all(c>=v for c,v in zip(cavity,env)),'Hardware exceeds installation envelope')
        if positive(power) and positive(voltage):warnings.append(f'Nominal power/voltage current: {power/voltage:.3f} A; not a measured startup current')
        for key in ['switch','cable_route','strain_relief','retention','service_access','thermal_plan']:
            val=data.get('engineering',{}).get(key)
            need(isinstance(val,str) and bool(val.strip()),f'Missing engineering description: {key}')
        if data.get('hardware_dimensions_measured') is not True:warnings.append('Purchased hardware dimensions have not been physically measured')
        for joint in data.get('fits',[]):
            name=joint.get('name','unnamed');male=joint.get('male_diameter_mm');female=joint.get('female_diameter_mm');gap=joint.get('radial_gap_mm')
            need(positive(male) and positive(female) and finite(gap) and gap>=0,f'Invalid fit dimensions: {name}')
            if positive(male) and positive(female) and finite(gap):
                need(female>=male and math.isclose((female-male)/2,gap,abs_tol=.001),f'Fit radial/diametral mismatch: {name}')
        parts=data.get('parts',[]);need(isinstance(parts,list) and len(parts)>0,'List manufacturing parts')
        bed=data.get('printer',{}).get('bed_mm');margin=data.get('printer',{}).get('edge_margin_mm',5)
        if mode=='fdm':need(vector(bed) and finite(margin) and margin>=0,'Valid printer bed and nonnegative edge margin required')
        for part in parts if isinstance(parts,list) else []:
            n=part.get('name','unnamed');dims=part.get('oriented_bounds_mm');path=part.get('file')
            need(vector(dims),f'Missing positive print-oriented XYZ bounds: {n}')
            need(isinstance(path,str) and path in existing_files,f'Missing manufacturing file: {n}')
            if mode=='fdm' and vector(dims) and vector(bed) and finite(margin):
                need(dims[0]+2*margin<=bed[0] and dims[1]+2*margin<=bed[1] and dims[2]<=bed[2],f'Part exceeds stated build volume with margin: {n}')
            if not positive(part.get('nominal_wall_mm')):warnings.append(f'No nominal wall recorded: {n}')
        evidence=data.get('evidence',{})
        for name in ['mesh','assembly','slicing','physical_fit','thermal']:
            item=evidence.get(name,{})
            if item.get('status')=='pass':
                path=item.get('file');need(isinstance(path,str) and path in existing_files,f'Missing claimed pass evidence: {name}')
            elif item.get('status')=='fail':errors.append(f'Failed evidence gate: {name}')
            else:warnings.append(f'Not validated: {name}')
    return {'nominal_preflight':'blocked' if errors else 'pass','errors':errors,'warnings':warnings,
      'scope':'Manifest dimensions/file presence only; does not read mesh geometry or validate truth/completeness of evidence. No physical or electrical safety certification.'}

def referenced_files(data):
    """Collect explicitly declared file references; do not discover unrelated data."""
    paths=[]
    for part in data.get('parts',[]):
        if isinstance(part,dict) and isinstance(part.get('file'),str):paths.append(part['file'])
    for item in data.get('evidence',{}).values():
        if isinstance(item,dict) and isinstance(item.get('file'),str):paths.append(item['file'])
    return paths

def check(data,root):
    """File-presence adapter; never reads manufacturing or evidence contents."""
    existing={path for path in referenced_files(data) if (Path(root)/path).is_file()}
    return check_nominal(data,existing)

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--output');a=p.parse_args();path=Path(a.manifest).resolve()
    try:result=check(json.loads(path.read_text()),path.parent)
    except (OSError,ValueError,TypeError,AttributeError) as ex:result={'nominal_preflight':'blocked','errors':[f'Invalid input: {ex}'],'warnings':[]}
    text=json.dumps(result,ensure_ascii=False,indent=2);print(text)
    if a.output:Path(a.output).write_text(text)
    return 2 if result['errors'] else 0

if __name__=='__main__':sys.exit(main())
