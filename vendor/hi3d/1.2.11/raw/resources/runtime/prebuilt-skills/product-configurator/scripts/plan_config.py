"""Validate configurator options against a GLB inventory. Does not invent prices."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

STYLES = {'simple', 'product', 'fullscreen'}
HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
ORBIT = re.compile(r'^[A-Za-z0-9.+%_-]+ [A-Za-z0-9.+%_-]+ [A-Za-z0-9.+%_-]+$')


def load_styles(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1:
        raise ValueError('styles.json must be schemaVersion 1')
    return data


def _names(items, key='name'):
    return {item[key] for item in items}


def validate_plan(brief, inventory, styles=None):
    if not isinstance(brief, dict) or brief.get('schemaVersion') != 1:
        raise ValueError('brief schemaVersion must be 1')
    if not isinstance(inventory, dict):
        raise ValueError('inventory required')
    if not inventory.get('selectableParts') and brief.get('splitDecision') not in ('continue-as-whole', 'need-split'):
        raise ValueError('model has no independently selectable parts; set splitDecision')
    if brief.get('splitDecision') == 'need-split':
        raise ValueError('need-split: stop and use a split model before configuring')
    node_names = _names(inventory.get('nodes') or [])
    material_names = _names(inventory.get('materials') or [])
    colors = brief.get('colorOptions') or []
    vis = brief.get('visibilityOptions') or []
    if not colors and not vis:
        raise ValueError('need at least one color or visibility option')
    ids = []
    for option in colors:
        ident = option.get('id')
        if not isinstance(ident, str) or ident in ids:
            raise ValueError('color option id must be unique')
        if option.get('target') not in material_names:
            raise ValueError('color target must be a material from the model')
        swatches = option.get('swatches') or []
        if len(swatches) < 2 or any(not HEX.match(s) for s in swatches):
            raise ValueError('each color option needs at least two #RRGGBB swatches')
        ids.append(ident)
    for option in vis:
        ident = option.get('id')
        if not isinstance(ident, str) or ident in ids:
            raise ValueError('visibility option id must be unique')
        if option.get('target') not in node_names:
            raise ValueError('visibility target must be a node from the model')
        ids.append(ident)
    groups = brief.get('exclusiveGroups') or []
    defaults_on = [option['id'] for option in vis if option.get('default') is not False]
    for group in groups:
        members = group.get('optionIds') or []
        if sum(1 for ident in members if ident in defaults_on) > 1:
            raise ValueError('exclusive group cannot default more than one option on')
    for group in groups:
        members = group.get('optionIds') or []
        if len(members) < 2 or any(m not in ids for m in members):
            raise ValueError('exclusive group must name at least two known options')
    style = brief.get('style', 'simple')
    if style not in STYLES:
        raise ValueError('style must be simple, product or fullscreen')
    pricing = brief.get('pricing')
    if pricing is not None:
        if not isinstance(pricing, dict) or not isinstance(pricing.get('currency'), str) or not pricing['currency'].strip():
            raise ValueError('pricing requires currency')
        base = pricing.get('base')
        if type(base) not in (int, float) or isinstance(base, bool) or base < 0:
            raise ValueError('pricing.base must be a nonnegative number')
        extras = pricing.get('options') or {}
        if any(key not in ids for key in extras):
            raise ValueError('pricing.options keys must match option ids')
        if any(type(v) not in (int, float) or isinstance(v, bool) for v in extras.values()):
            raise ValueError('option prices must be numbers')
    cameras = brief.get('cameras') or (styles or {}).get('orbits') or []
    for camera in cameras:
        if not ORBIT.match(str(camera.get('orbit', ''))):
            raise ValueError('camera orbit must be three safe tokens')
    title = brief.get('title')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('title is required')
    return {
        'title': title.strip(),
        'style': style,
        'colorOptions': colors,
        'visibilityOptions': vis,
        'exclusiveGroups': groups,
        'pricing': pricing,
        'cameras': cameras,
        'appId': brief.get('appId') or 'product-configurator',
        'modelFile': brief.get('modelFile') or 'model.glb',
        'externalTextures': list(inventory.get('externalTextures') or []),
        'unimplemented': brief.get('unimplemented') or ['支付', '库存', '订单'],
        'note': '颜色切换只改变显示颜色，不是物理材质验证。',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Plan a product-configurator')
    parser.add_argument('--brief', required=True)
    parser.add_argument('--inventory', required=True)
    parser.add_argument('--styles', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit('output must be a new file')
    plan = validate_plan(
        json.loads(Path(args.brief).read_text(encoding='utf-8')),
        json.loads(Path(args.inventory).read_text(encoding='utf-8')),
        load_styles(args.styles),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
