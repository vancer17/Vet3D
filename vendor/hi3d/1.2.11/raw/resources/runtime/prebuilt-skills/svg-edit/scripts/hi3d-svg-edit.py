"""Edit local SVG nodes and export with explicit Inkscape, preserving the source."""
import argparse,copy,json,re
from pathlib import Path
import xml.etree.ElementTree as ET
import importlib
_job_api=importlib.import_module('hi3d-edit-job')
EditJob=_job_api.EditJob
local_file=_job_api.local_file
dump=_job_api.dump
number=_job_api.number
NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)
TAGS={'svg','g','rect','circle','ellipse','path','line','polyline','polygon','text','tspan','defs','linearGradient','radialGradient','stop','clipPath'}
ATTRS={'id','x','y','x1','y1','x2','y2','width','height','cx','cy','r','rx','ry','d','points','fill','stroke','stroke-width','opacity','fill-opacity','stroke-opacity','transform','font-family','font-size','font-weight','text-anchor','viewBox','version','offset','stop-color','stop-opacity','gradientUnits','gradientTransform','clip-path','fill-rule'}

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_.-]*',value):raise ValueError('unsafe SVG id')
    return value

def attributes(attrs):
    if set(attrs)-ATTRS:raise ValueError('unsupported SVG attribute')
    result={}
    for k,v in attrs.items():
        if not isinstance(v,(str,int,float)) or isinstance(v,bool):raise ValueError('scalar attribute required')
        v=str(v)
        if any(x in v.lower() for x in ('javascript:','data:','://','@import')):raise ValueError('external or active SVG reference')
        if 'url(' in v.lower() and not re.fullmatch(r'url\(#[A-Za-z_][A-Za-z0-9_.-]*\)',v):raise ValueError('only local fragment references allowed')
        if k=='id':identifier(v)
        result[k]=v
    return result

def inspect(root):
    ids=set()
    if root.tag!='{'+NS+'}svg':raise ValueError('SVG namespace root required')
    for e in root.iter():
        if e.tag.removeprefix('{'+NS+'}') not in TAGS:raise ValueError('unsupported SVG element')
        attributes(e.attrib)
        if e.get('id'):
            if e.get('id') in ids:raise ValueError('duplicate id')
            ids.add(e.get('id'))
    return ids

def strip_editor_metadata(root):
    # Preserve supported artwork; drop only non-rendering editor view metadata.
    editor_ns=('http://www.inkscape.org/namespaces/inkscape','http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd')
    for parent in root.iter():
        for child in list(parent):
            if child.tag=='{'+editor_ns[1]+'}namedview':parent.remove(child)
        for key in list(parent.attrib):
            if any(key.startswith('{'+ns+'}') for ns in editor_ns):del parent.attrib[key]
    return root

def edit(spec,source=None):
    if spec.get('schemaVersion')!=1 or set(spec)-{'schemaVersion','source','width','height','operations','boolean','formats','budgetSeconds'}:raise ValueError('invalid SVG schema')
    if source:
        text=Path(source).read_text()
        if '<!DOCTYPE' in text or '<!ENTITY' in text:raise ValueError('DTD disallowed')
        root=strip_editor_metadata(ET.fromstring(text))
    else:
        number(spec['width'],'width',0,True);number(spec['height'],'height',0,True)
        root=ET.Element('{'+NS+'}svg',{'width':str(spec['width']),'height':str(spec['height']),'viewBox':f"0 0 {spec['width']} {spec['height']}"})
    inspect(root)
    for op in spec.get('operations',[]):
        if set(op)-{'op','id','parent','tag','attrs','text','newId'}:raise ValueError('unknown SVG operation field')
        byid={e.get('id'):e for e in root.iter() if e.get('id')}
        action=op['op'];key=identifier(op['id'])
        if action=='add':
            if key in byid or op['tag'] not in TAGS-{'svg','defs'}:raise ValueError('invalid add')
            parent=byid[op['parent']] if op.get('parent') else root
            node=ET.SubElement(parent,'{'+NS+'}'+op['tag'],attributes({**op.get('attrs',{}),'id':key}));node.text=op.get('text')
        elif action=='set':
            node=byid[key];node.attrib.update(attributes(op.get('attrs',{})))
            if 'text' in op:node.text=op['text']
        elif action=='remove':
            node=byid[key]
            for parent in root.iter():
                if node in list(parent):parent.remove(node);break
        elif action=='duplicate':
            node=byid[key]
            if len(list(node.iter()))>1:raise ValueError('duplicate leaf only; group descendants require explicit ids')
            new=copy.deepcopy(node);new.set('id',identifier(op['newId']));root.append(new)
        else:raise ValueError('unknown SVG operation')
        inspect(root)
    return root

def execute(spec_path,output,inkscape):
    path=Path(spec_path).resolve();spec=json.loads(path.read_text());src=local_file(spec['source'],path.parent) if spec.get('source') else None
    root=edit(spec,src);formats=spec.get('formats',['png','pdf'])
    if not formats or set(formats)-{'png','pdf'}:raise ValueError('formats png/pdf only')
    for op in spec.get('boolean',[]):
        if op['op'] not in ('union','difference','intersection') or len(op['ids'])<2:raise ValueError('invalid boolean')
        for k in op['ids']:identifier(k)
        if not set(op['ids'])<=inspect(root):raise ValueError('unknown boolean id')
    job=EditJob(output,spec,[path,*([src] if src else [])],Path(__file__).resolve().parents[1],spec.get('budgetSeconds',120))
    if job.reused:return job.result
    with job:
        svg=job.root/'hi3d-artwork.svg';ET.ElementTree(root).write(svg,encoding='utf-8',xml_declaration=True)
        for i,op in enumerate(spec.get('boolean',[])):
            current=ET.parse(svg).getroot();byid={e.get('id'):e for e in current.iter()}
            if not set(op['ids'])<=set(byid):raise ValueError('boolean uses removed id')
            style={k:v for k,v in byid[op['ids'][0]].attrib.items() if k in ('fill','stroke','stroke-width','opacity','fill-rule')}
            # Only controlled ids/operators reach Inkscape actions; never arbitrary action strings.
            action='select-by-id:'+','.join(op['ids'])+';path-'+op['op']+';export-filename:'+str(svg)+';export-do'
            job.run([inkscape,svg,'--export-type=svg','--actions='+action],'boolean'+str(i))
            current=strip_editor_metadata(ET.parse(svg).getroot());result=next((e for e in current.iter() if e.get('id')==op['ids'][0]),None)
            if result is None:raise ValueError('boolean result id not retained')
            result.attrib.update(style);inspect(current);ET.ElementTree(current).write(svg,encoding='utf-8',xml_declaration=True)
        files=[svg]
        for fmt in formats:
            out=job.root/('hi3d-artwork.'+fmt)
            job.run([inkscape,svg,'--export-type='+fmt,'--export-filename='+str(out)],'export'+fmt);files.append(out)
            if fmt=='png':
                from PIL import Image
                with Image.open(out) as im:im.verify()
                with Image.open(out) as im:im.load()
            else:
                if out.read_bytes()[:5]!=b'%PDF-':raise ValueError('PDF signature missing')
                preview=job.root/'hi3d-pdf-review.png'
                job.run([inkscape,out,'--pdf-poppler','--export-type=png','--export-filename='+str(preview)],'pdfreadback')
                from PIL import Image
                with Image.open(preview) as im:im.load()
                files.append(preview)
        # Inkscape may add metadata namespaces; parse the saved document, then reopen via CLI export.
        parsed=ET.parse(svg)
        if parsed.getroot().tag!='{'+NS+'}svg':raise ValueError('saved SVG invalid')
        return job.finish(files,{'svgReparsed':True,'inkscapeReopened':True,'pdfValidation':'Inkscape PDF import and PNG decode' if 'pdf' in formats else 'not requested','nodeCount':len(list(parsed.getroot().iter()))})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--output',required=True);p.add_argument('--inkscape',required=True);a=p.parse_args();print(json.dumps(execute(a.spec,a.output,a.inkscape)))
