"""Resolve packaged template resources without changing explicit custom-template inputs."""
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'taro'


def resolve_template_config(config):
    """Return a copy with package-relative Taro defaults; no model loading or mutations.

    Custom templates never inherit Taro atlases. Explicit texture values, including
    None, are retained. Missing packaged resources indicate an incomplete skill copy.
    """
    result = dict(config)
    template = ASSETS / 'template.npz'
    if not result.get('template'):
        result['template'] = str(template)
    if Path(result['template']).resolve() != template:
        return result
    defaults = {'template_albedo': ASSETS / 'head_color_map.tga'}
    if result.get('dna'):
        defaults.update(template_eye_albedo=ASSETS / 'eyes_color_map.tga',
                        template_teeth_albedo=ASSETS / 'teeth_color_map.tga')
    required = [template] + [path for key, path in defaults.items() if key not in result]
    if any(not path.is_file() for path in required):
        raise FileNotFoundError('Incomplete metahuman-fit package: restore assets/taro from the skill repository')
    for key, path in defaults.items():
        result.setdefault(key, str(path))
    return result
