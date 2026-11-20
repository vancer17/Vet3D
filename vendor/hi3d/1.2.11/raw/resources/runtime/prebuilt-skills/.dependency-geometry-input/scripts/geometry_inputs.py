"""Prepare image and ZIP inputs between geometry atoms; no network or model loading."""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import re
import zipfile


def prepare_image(image, *, size=1536, padding=1.15):
    """RGBA PIL image -> aligned white RGB and RGBA. Preserve soft alpha, reject empty masks."""
    from PIL import Image
    if type(size) is not int or size < 1:
        raise ValueError('size must be a positive integer')
    if not math.isfinite(padding) or padding < 1:
        raise ValueError('padding must be finite and >= 1')
    if 'A' not in image.getbands():
        raise ValueError('an explicit foreground alpha channel is required')
    rgba = image.convert('RGBA')
    alpha = rgba.getchannel('A')
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError('empty foreground')
    if alpha.getextrema()[0] == 255:
        raise ValueError('opaque full-frame alpha is not a foreground mask')
    left, top, right, bottom = bbox
    side = max(right-left, bottom-top)
    x = left - (side-(right-left))//2
    y = top - (side-(bottom-top))//2
    cropped = rgba.crop((x, y, x+side, y+side))
    padded_side = max(side, int(side*padding))
    canvas = Image.new('RGBA', (padded_side, padded_side), (255,255,255,0))
    # A masked paste multiplies alpha twice. Copy RGBA directly into the transparent canvas.
    canvas.paste(cropped, ((padded_side-side)//2, (padded_side-side)//2))
    prepared = canvas.resize((size,size), Image.Resampling.LANCZOS)
    white = Image.new('RGBA', prepared.size, (255,255,255,255))
    rgb = Image.alpha_composite(white, prepared).convert('RGB')
    return rgb, prepared


def read_bridge(content, *, count=4):
    """Read a Geometry V4 rendered-views ZIP into indexed bytes, without extracting paths."""
    if type(count) is not int or count < 1:
        raise ValueError('count must be positive')
    groups = {key:{} for key in ('normal','ccm_png','ccm_exr','mask')}
    patterns = {
        'normal': r'normal_v(\d+)(?:_[^.]+)?\.png',
        'ccm_png': r'ccm_v(\d+)(?:_[^.]+)?\.png',
        'ccm_exr': r'View(\d+)_(?:B)?CCM\.exr',
        'mask': r'View(\d+)_GrayMask\.png',
    }
    camera = None
    with zipfile.ZipFile(BytesIO(content)) as zf:
        for item in zf.infolist():
            if item.is_dir():
                continue
            name = Path(item.filename).name
            if name == 'camera_info.txt':
                if camera is not None:
                    raise ValueError('duplicate camera_info.txt')
                camera = zf.read(item)
            for key, pattern in patterns.items():
                match = re.fullmatch(pattern, name)
                if match:
                    index = int(match[1])
                    if index in groups[key]:
                        raise ValueError(f'duplicate {key} view {index}')
                    groups[key][index] = zf.read(item)
                    break
    for key in ('normal','ccm_png','ccm_exr'):
        if set(groups[key]) != set(range(count)) or any(not b for b in groups[key].values()):
            raise ValueError(f'{key} must contain nonempty views 0..{count-1}')
    return {**{key:[values.get(i) for i in range(count)] for key,values in groups.items()},
            'camera_info':camera}


def build_prep_zip(gray_images, bridge):
    """Ordered GrayColor PNG bytes + same-stage bridge -> Geo2 ZIP, with no mesh embedded."""
    from PIL import Image
    count = len(bridge['ccm_exr'])
    if count != 4:
        raise ValueError('this builder requires four views; extra face views need explicit metadata')
    if not gray_images or len(gray_images) != count or len(bridge['mask']) != count:
        raise ValueError('GrayColor/CCM/mask view counts must agree')
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as zf:
        for i, content in enumerate(gray_images):
            with Image.open(BytesIO(content)) as im:
                im.load()
                if im.format != 'PNG':
                    raise ValueError('GrayColor input must be real PNG bytes')
            ccm = bridge['ccm_exr'][i]
            if not ccm or ccm[:4] != b'v/1\x01':
                raise ValueError('CCM must be an EXR, not its 8-bit PNG preview')
            zf.writestr(f'View{i}_GrayColor.png', content)
            zf.writestr(f'View{i}_CCM.exr', ccm)
            if bridge['mask'][i] is not None:
                zf.writestr(f'View{i}_GrayMask.png', bridge['mask'][i])
        if bridge.get('camera_info') is not None:
            zf.writestr('camera_info.txt', bridge['camera_info'])
    return buffer.getvalue()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    image=sub.add_parser('prepare')
    image.add_argument('--input',type=Path,required=True)
    image.add_argument('--out',type=Path,required=True)
    image.add_argument('--size',type=int,default=1536)
    image.add_argument('--padding',type=float,default=1.15)
    bridge=sub.add_parser('bridge')
    bridge.add_argument('--rendered-views',type=Path,required=True)
    bridge.add_argument('--gray',type=Path,action='append',required=True)
    bridge.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    if a.command=='prepare':
        from PIL import Image
        with Image.open(a.input) as im:
            rgb,rgba=prepare_image(im,size=a.size,padding=a.padding)
        a.out.mkdir(parents=True,exist_ok=False)
        rgb.save(a.out/'prepared_rgb.png')
        rgba.save(a.out/'prepared_rgba.png')
        print(json.dumps({'prepared_rgb':str(a.out/'prepared_rgb.png'),
                          'prepared_rgba':str(a.out/'prepared_rgba.png'),'size':a.size}))
    else:
        inputs=read_bridge(a.rendered_views.read_bytes(),count=len(a.gray))
        content=build_prep_zip([f.read_bytes() for f in a.gray],inputs)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        with a.out.open('xb') as f:
            f.write(content)
        print(json.dumps({'prep_zip':str(a.out),'views':len(a.gray)}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
