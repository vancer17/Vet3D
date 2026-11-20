"""Ordered images and labels → contact sheet and explicit cell mapping."""
from pathlib import Path
from hashlib import sha256
import math
from PIL import Image, ImageDraw, ImageFont


def compose_sheet(items, *, columns, image_size, label_height, gap=0,
                  background='#101722', foreground='#dce8ef', font=None,
                  font_size=None, label_offset=(8,4), resize='contain',
                  resample=Image.Resampling.LANCZOS, label_position='top'):
    """Return (new RGB image, ordered cell records); never alter input images."""
    items = list(items)
    if (not items or type(columns) is not int or columns < 1 or len(image_size) != 2
            or any(type(v) is not int or v <= 0 for v in image_size)
            or any(type(v) is not int or v < 0 for v in [label_height,gap])):
        raise ValueError('Nonempty images and valid integer layout dimensions required')
    if resize not in {'contain','stretch'}:
        raise ValueError('Choose contain (no upscaling) or stretch explicitly')
    if label_position not in {'top', 'bottom'}:
        raise ValueError('Choose top or bottom labels explicitly')
    width, height = image_size; rows = math.ceil(len(items)/columns)
    sheet = Image.new('RGB', (columns*width+(columns+1)*gap,
                     rows*(height+label_height)+(rows+1)*gap), background)
    draw = ImageDraw.Draw(sheet)
    if font is None:
        font = ImageFont.load_default(size=font_size) if font_size is not None else ImageFont.load_default()
    cells = []
    for index, item in enumerate(items):
        if ('path' in item) == ('image' in item):
            raise ValueError('Each item needs exactly one path or PIL image')
        path = Path(item['path']).resolve() if 'path' in item else None
        if item.get('sha256') is not None:
            if path is None or sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Source image hash mismatch')
        if path:
            with Image.open(path) as source:
                source.load(); image = source.convert('RGB')
        else:
            image = item['image'].convert('RGB')
        original_size = list(image.size)
        if resize == 'stretch': image = image.resize((width,height),resample)
        else: image.thumbnail((width,height),resample)
        row, column = divmod(index,columns)
        x, y = gap+column*(width+gap), gap+row*(height+label_height+gap)
        label = str(item.get('label',''))
        image_y = y + (label_height if label_position == 'top' else 0)
        label_y = y + (height if label_position == 'bottom' else 0)
        draw.text((x+label_offset[0],label_y+label_offset[1]),label,font=font,fill=foreground)
        sheet.paste(image,(x,image_y))
        cells.append(dict(index=index,row=row,column=column,label=label,
                          source=str(path) if path else None,source_size=original_size,
                          image_box=[x,image_y,x+image.width,image_y+image.height],
                          cell_box=[x,y,x+width,y+label_height+height]))
    return sheet, cells


def write_sheet(items, output, *, overwrite=False, save_options=None, **layout):
    """Compose and save one PNG/JPEG, returning the image path, size and cells."""
    items = list(items); output = Path(output).resolve()
    if any('path' in item and Path(item['path']).resolve() == output for item in items):
        raise ValueError('Sheet must not overwrite a source image')
    formats = {'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG'}
    if output.suffix.lower() not in formats:
        raise ValueError('Sheet output must be PNG or JPEG')
    if output.exists() and not overwrite:
        raise FileExistsError(output)
    sheet, cells = compose_sheet(items, **layout)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb' if overwrite else 'xb') as stream:
        sheet.save(stream,format=formats[output.suffix.lower()],**(save_options or {}))
    return dict(output=str(output),size=list(sheet.size),cells=cells)


def main(argv=None):
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mapping',type=Path,required=True)
    parser.add_argument('--overwrite',action='store_true')
    args = parser.parse_args(argv)
    data = json.loads(args.manifest.read_text())
    items = [dict(item,path=str((args.manifest.resolve().parent/item['path']).resolve())) for item in data['images']]
    protected = [args.manifest.resolve(),*[Path(item['path']) for item in items]]
    if args.output.resolve() in protected or args.mapping.resolve() in protected+[args.output.resolve()]:
        raise ValueError('Output and mapping must be distinct from each other and all inputs')
    if args.mapping.exists() and not args.overwrite:
        raise FileExistsError(args.mapping)
    layout = dict(data['layout'])
    if layout.get('font'):
        layout['font'] = ImageFont.truetype(str((args.manifest.resolve().parent/layout['font']).resolve()),layout.get('font_size',22))
    result = write_sheet(items,args.output,overwrite=args.overwrite,**layout)
    args.mapping.parent.mkdir(parents=True,exist_ok=True)
    with args.mapping.open('w' if args.overwrite else 'x') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__ == '__main__': main()
