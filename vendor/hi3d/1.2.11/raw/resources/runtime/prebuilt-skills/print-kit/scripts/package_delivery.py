"""Build the three final deliverables from validated print STL bytes.

The HTML embeds its viewer, geometry and downloadable files. No server, CDN or
network access is required. Output files replace matching names in --out only.
"""
import argparse
import csv
import html
import io
import json
from pathlib import Path, PurePosixPath
from page_assets import read_asset, encode_asset, image_figure, render_template
import struct
import zipfile

import trimesh
from kitlib import assembly_geometry
from verify_kit import verify


def json_bytes(value):
    """Serialize finite JSON to UTF-8 bytes without filesystem access."""
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')


def read_parts(plan_path):
    """Read plan and each referenced STL once; reject changed hashes and unsafe paths."""
    path = Path(plan_path).resolve()
    plan = json.loads(path.read_text(encoding='utf-8'))
    files, meshes = {}, {}
    for part in plan['parts']:
        relative = PurePosixPath(part['file'])
        if relative.is_absolute() or '..' in relative.parts or relative.suffix.lower() != '.stl':
            raise ValueError('part path must be a relative STL path')
        raw, _ = read_asset(path.parent,part['file'],expected_sha256=part['sha256'])
        if len(raw) < 84 or len(raw) != 84 + 50 * struct.unpack_from('<I', raw, 80)[0]:
            raise ValueError('viewer requires binary STL; re-export part and plan: ' + part['id'])
        if part['file'] in files:
            raise ValueError('duplicate part file')
        files[part['file']] = raw
        meshes[part['id']] = trimesh.load_mesh(io.BytesIO(raw), file_type='stl', process=True)
    return plan, files, meshes


def printing_notes(plan):
    """Return readable assembly/print instructions from the task plan, without IO."""
    lines = [plan['title'], '', 'STL 单位 mm，已按打印姿态贴床。不要单独缩放配合件。',
             'GLB 单位 m，仅供装配查看。按清单数量打印，重复件共用同一 STL。', '',
             '打印空间 mm：' + str(plan['bed_mm']),
             '本任务工艺：' + json.dumps(plan.get('profile', {}), ensure_ascii=False), '',
             '装配顺序：']
    lines.extend(f'{i}. {step}' for i, step in enumerate(plan.get('assembly_steps', []), 1))
    if not plan.get('assembly_steps'):
        lines.append('计划中未填写操作说明；须补全可执行的装配步骤。')
    for heading, key in [('外购配件', 'hardware'), ('设计说明', 'notes')]:
        lines += ['', heading + '：'] + [str(x) for x in plan.get(key, [])]
    lines += ['', '连接与保持：']
    lines.extend(f"{j['a']} ↔ {j['b']}：{j['kind']}；单边/径向间隙 {j['clearance_per_side_mm']} mm；{j['retention']}"
                 for j in plan['joints'])
    lines += ['', '零件与打印说明：']
    lines.extend(f"{p['file']} × {p['qty']}：{p.get('support', 'not_assessed')}；{p.get('print_notes', '')}"
                 for p in plan['parts'])
    lines += ['', '先以目标材料、朝向与切片配置打印试片，实测后回写公差。',
              '几何检查不证明切片、弹性、五金安装、保持力或实体试配成功。',
              '任务中声明的外部证据状态：' + json.dumps(plan.get('evidence', {}), ensure_ascii=False)]
    return '\n'.join(lines) + '\n'


def parts_csv(plan):
    """Return a BOM with one row per unique STL and required print quantity."""
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['part_id', 'stl_file', 'print_quantity', 'size_mm', 'support', 'print_notes'])
    for p in plan['parts']:
        writer.writerow([p['id'], p['file'], p['qty'], ' x '.join(map(str, p['size_mm'])),
                         p.get('support', 'not_assessed'), p.get('print_notes', '')])
    return stream.getvalue().encode('utf-8-sig')


def zip_bytes(entries):
    """Return a ZIP from name→bytes; reject unsafe names, never extract to disk."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(entries.items()):
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:
                raise ValueError('unsafe ZIP entry: ' + name)
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return stream.getvalue()


def read_supplements(sources, coupons):
    """Read explicitly selected source files and coupon STL/JSON/Markdown; no writes."""
    entries = {}
    paths = [('source/' + Path(p).name, Path(p)) for p in sources]
    if coupons:
        root = Path(coupons)
        if not root.is_dir():
            raise ValueError('coupon directory does not exist')
        paths += [('coupons/' + p.relative_to(root).as_posix(), p) for p in root.rglob('*')
                  if p.is_file() and p.suffix.lower() in ('.stl', '.json', '.md')]
    for name, path in paths:
        if name in entries:
            raise ValueError('duplicate supplementary filename: ' + name)
        entries[name] = path.read_bytes()
    return entries


def image_gallery(root):
    """Read existing final render PNGs and return embedded figures; no invented imagery."""
    items = []
    for name, label in [('assembly.png', '装配效果'), ('exploded.png', '拆解效果'),
                        ('plates.png', '打印摆盘'), ('operation.png', '功能位置')]:
        path = root / name
        if path.is_file():
            raw,_=read_asset(root,name)
            items.append(image_figure(raw,label))
    return '<h2>效果展示</h2><div class="gallery">' + ''.join(items) + '</div>' if items else ''


def render_page(plan, files, glb, archive, notes, report, assets, gallery=''):
    """Render a self-contained HTML from loaded data/assets; no file/network access."""
    encode = encode_asset
    data = {'plan': plan, 'stl': {p['id']: encode(files[p['file']]) for p in plan['parts']},
            'downloads': {'download-glb': {'filename': 'assembly.glb', 'mime': 'model/gltf-binary', 'base64': encode(glb)},
                          'download-stl': {'filename': 'parts-stl.zip', 'mime': 'application/zip', 'base64': encode(archive)}}}
    rows = []
    for part in plan['parts']:
        cells = [part['id'], str(part['qty']), ' × '.join(f'{v:.2f}' for v in part['size_mm']),
                 part.get('support', 'not_assessed') + ' · ' + part.get('print_notes', '')]
        rows.append('<tr>' + ''.join('<td>' + html.escape(c) + '</td>' for c in cells) + '</tr>')
    return render_template(assets['page.html'],dict(
        title=html.escape(plan['title']),
        stats=f"{len(plan['parts'])} 种零件 · {len(plan['instances'])} 个打印件 · {max(p['plate'] for p in plan['plates'])} 盘",
        part_rows=''.join(rows), gallery=gallery, instructions=html.escape(notes),
        validation=html.escape(json_bytes(report).decode('utf-8')),
        license=html.escape(assets['vendor/LICENSE-three.txt']),
        payload=json_bytes(data).decode('utf-8').replace('<', '\\u003c'),
        downloads_js=assets['downloads.js'], three_js=assets['vendor/three.min.js'], viewer_js=assets['viewer.js']),syntax='dollar')


def build_delivery(plan_path, out, sources=(), coupons=None, include_renders=False):
    """Validate inputs, create same-version GLB/ZIP/offline page, write three outputs.

    Existing matching outputs are replaced only after payload construction. Failures
    propagate; no model rebuild, slicing, hosting or printing is performed.
    """
    report = verify(plan_path)
    if report['status'] != 'pass':
        raise ValueError('geometry validation failed: ' + '; '.join(report['errors']))
    plan, files, meshes = read_parts(plan_path)
    scene, _ = assembly_geometry(plan, meshes)
    glb = scene.export(file_type='glb')
    notes = printing_notes(plan)
    entries = dict(files, **{'kit.json': json_bytes(plan), 'parts.csv': parts_csv(plan),
                            'PRINTING.md': notes.encode('utf-8'), 'validation.json': json_bytes(report)})
    entries.update(read_supplements(sources, coupons))
    archive = zip_bytes(entries)
    asset_root = Path(__file__).resolve().parents[1] / 'assets/viewer'
    names = ['page.html', 'downloads.js', 'viewer.js', 'vendor/three.min.js', 'vendor/LICENSE-three.txt']
    assets = {name: (asset_root / name).read_text(encoding='utf-8') for name in names}
    gallery = image_gallery(Path(plan_path).resolve().parent) if include_renders else ''
    page = render_page(plan, files, glb, archive, notes, report, assets, gallery)
    target = Path(out)
    target.mkdir(parents=True, exist_ok=True)
    for name, raw in [('assembly.glb', glb), ('parts-stl.zip', archive), ('viewer.html', page.encode('utf-8'))]:
        (target / name).write_bytes(raw)
    return {key: str(target / name) for key, name in [('assembly_glb', 'assembly.glb'),
            ('parts_stl_zip', 'parts-stl.zip'), ('showcase', 'viewer.html')]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan')
    parser.add_argument('--out', required=True)
    parser.add_argument('--source', action='append', default=[])
    parser.add_argument('--coupons')
    parser.add_argument('--include-renders', action='store_true', help='Include reviewed same-version PNGs beside the plan')
    args = parser.parse_args()
    print(json.dumps(build_delivery(args.plan, args.out, args.source, args.coupons, args.include_renders), ensure_ascii=False))


if __name__ == '__main__':
    main()
