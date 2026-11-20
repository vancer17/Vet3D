"""Explicit-input business stage and thin command-line adapter."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse, json, struct, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from types import SimpleNamespace
from functools import partial
from frame_runtime import cli_arguments, validate_paths

def render_sections(*, input, output):
    """Run this named business stage. Inputs and all output paths are explicit.

    Mutates the active Blender scene when applicable; never runs on import.
    Files are generated only under the explicit destination. See code-contract.md.
    """
    a=SimpleNamespace(input=input, output=output)
    validate_paths(a)
    D = Path(a.input)
    def raw(path):
        b = path.read_bytes()
        return np.frombuffer(b, dtype=np.dtype([('n', '<f4', (3,)), ('v', '<f4', (3, 3)), ('a', '<u2')]), offset=84, count=struct.unpack_from('<I', b, 80)[0])['v'].astype(float)
    def segments(t, z):
        edges = t[:, [[0, 1], [1, 2], [2, 0]], :]
        hit = (edges[:, :, 0, 2] < z) != (edges[:, :, 1, 2] < z)
        result = []
        for f, mask in zip(edges, hit):
            q = f[mask]
            if len(q) == 2:
                k = (z - q[:, 0, 2]) / (q[:, 1, 2] - q[:, 0, 2])
                result.append(q[:, 0, :2] + (q[:, 1, :2] - q[:, 0, :2]) * k[:, None])
        return np.asarray(result)
    found = [D/'print'/n for n in ('continuous-flowing-frame-and-integral-feather-leaves.stl','eccentric-frame-with-measured-relief.stl') if (D/'print'/n).is_file()]
    if len(found) != 1: raise ValueError('Expected one supported frame STL')
    frame = raw(found[0])
    stand = raw(D / 'print/one-piece-detachable-rear-easel.stl')
    im = Image.new('RGB', (2000, 710), '#f4f0e8')
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default(size=23)
    small = ImageFont.load_default(size=18)
    info = []
    draw.text((35, 25), 'Actual STL plane sections | millimetres | geometry inspection, not sliced G-code', font=font, fill='#40362a')
    for k, (t, z, title) in enumerate(zip([frame, frame, frame, stand], [1.5, 4.2, 7.8, -1.5], ['Rear artwork seat', 'Visible opening', 'Ornament section', 'Easel mount clearance'])):
        seg = segments(t, z)
        if not len(seg):
            info.append({'title':title,'z_mm':z,'segments':0})
            draw.text((k*500+30,85), title+' (no intersection)',font=small,fill='#40362a')
            continue
        low = seg.reshape(-1, 2).min(0)
        high = seg.reshape(-1, 2).max(0)
        center = (low + high) / 2
        scale = min(420 / (high[0] - low[0]), 480 / (high[1] - low[1]))
        ox = k * 500 + 250
        oy = 385
        draw.text((k * 500 + 30, 85), title, font=font, fill='#40362a')
        draw.text((k * 500 + 30, 118), 'Z = %.1f mm' % z, font=small, fill='#615747')
        for pair in seg:
            q = (pair - center) * [scale, -scale] + [ox, oy]
            draw.line([tuple(q[0]), tuple(q[1])], fill='#75572d', width=2)
        draw.line((k * 500 + 35, 645, k * 500 + 465, 645), fill='#b7aa96', width=1)
        draw.text((k * 500 + 35, 660), 'X span %.2f mm / Y span %.2f mm' % tuple(high - low), font=small, fill='#615747')
        info.append({'title': title, 'z_mm': z, 'segments': len(seg), 'xy_span_mm': (high - low).tolist()})
    im.save(a.output)
    Path(a.output).with_suffix('.json').write_text(json.dumps(info, indent=2))

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    options=p.parse_args(cli_arguments(argv))
    return render_sections(**vars(options))

if __name__ == "__main__":
    main()
