"""Build a static asset page from existing, explicitly versioned local files."""
import argparse
import html
import json
from pathlib import Path
from page_assets import read_asset,encode_asset,image_figure,render_template

MIME={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp',
      '.mp4':'video/mp4','.glb':'model/gltf-binary','.zip':'application/zip',
      '.stl':'model/stl','.3mf':'model/3mf','.pdf':'application/pdf'}


def load_assets(spec, root):
    """Validate an explicit revision and asset list; return records and payloads."""
    if not isinstance(spec.get('title'),str) or not spec['title'].strip() or not isinstance(spec.get('revision'),str) or not spec['revision'].strip():
        raise ValueError('Title and explicit revision required')
    if not isinstance(spec.get('assets'),list) or not spec['assets']:raise ValueError('Nonempty asset list required')
    records=[];payloads={}
    for asset in spec['assets']:
        name=asset['file'];role=asset['role'];label=asset.get('label',name)
        if role not in ('image','model','video','download') or not isinstance(label,str):
            raise ValueError('Unique assets, explicit role and text label required')
        mime=MIME.get(Path(name).suffix.lower(),'application/octet-stream')
        if role=='image' and not mime.startswith('image/') or role=='model' and mime!='model/gltf-binary' or role=='video' and mime!='video/mp4':
            raise ValueError('Asset suffix does not match display role')
        raw,record=read_asset(root,name,expected_sha256=asset.get('sha256'))
        if record['file'] in payloads:raise ValueError('Duplicate normalized asset path')
        if role=='model':
            from glb_clips import read_glb
            doc,_=read_glb(raw)
            if not doc.get('meshes') or any(item.get('uri') and not str(item['uri']).startswith('data:') for item in doc.get('buffers',[])+doc.get('images',[])):
                raise ValueError('Model must be a self-contained mesh GLB')
        record.update(role=role,label=label,mime=mime,revision=spec['revision']);records.append(record);payloads[record['file']]=raw
    return records,payloads


def render_page(title, revision, records, payloads, template):
    """Compose escaped labels and embedded assets; original bytes downloadable."""
    cards=[];has_models=False
    for record in records:
        raw=payloads[record['file']];label=html.escape(record['label'],quote=True)
        data='data:'+record['mime']+';base64,'+encode_asset(raw)
        download=f'<a download="{html.escape(Path(record["file"]).name,quote=True)}" href="{data}">下载 {label}</a>'
        if record['role']=='image':body=image_figure(raw,record['label'],mime=record['mime'])
        elif record['role']=='model':
            has_models=True;body=f'<model-viewer camera-controls src="{data}" alt="{label}"></model-viewer><p>{label}</p>'
        elif record['role']=='video':body=f'<video controls preload="metadata" src="{data}" aria-label="{label}"></video><p>{label}</p>'
        else:body=f'<p>{label}</p>'
        cards.append('<article>'+body+download+'</article>')
    runtime='<script type="module" src="https://cdn.jsdelivr.net/npm/@google/model-viewer@4.0.0/dist/model-viewer.min.js"></script>' if has_models else ''
    return render_template(template,{'__TITLE__':html.escape(title),'__REVISION__':html.escape(revision),
                                    '__CARDS__':''.join(cards),'__RUNTIME__':runtime,
                                    '__NETWORK__':'3D 查看器需要联网；原始文件下载不依赖查看器加载。' if has_models else '资产已嵌入本页，可离线查看和下载。'})


def build_page(spec, root, output):
    records,payloads=load_assets(spec,root)
    template=Path(__file__).resolve().parents[1]/'assets/page.html'
    page=render_page(spec['title'],spec['revision'],records,payloads,template.read_text())
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'index.html').write_text(page,encoding='utf-8')
    report={'title':spec['title'],'revision':spec['revision'],'assets':records,
            'viewer_requires_network':any(r['role']=='model' for r in records),'browser_interaction_tested':False}
    (output/'asset-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=build_page(json.loads(args.manifest.read_text()),args.manifest.parent,args.output)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
