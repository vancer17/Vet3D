"""The explicit circular-bayonet frame recipe; not a generic runtime policy."""
import math

def validate_recipe(config):
    """Validate the limited circular bayonet recipe; return a fresh mapping.

    Geometry coordinates and interfaces are fixed; relief amplitude/boundary
    fade and fit are narrowly configurable. Values are digital design inputs,
    never calibration or material strength claims.
    """
    if not isinstance(config, dict):
        raise ValueError('Configuration must be a JSON object')
    required = {'recipe', 'aperture_mm', 'outer_radius_mm', 'eccentric_x_mm',
                'hi3d_relief_mm', 'fit_clearance_mm', 'bayonet_turn_deg',
                'frame_back_mm', 'height_key'}
    allowed = required | {'title', 'source_boundary_fade_pixels'}
    if required - config.keys():
        raise ValueError('Missing configuration keys: '+', '.join(sorted(required-config.keys())))
    if config.keys() - allowed:
        raise ValueError('Unsupported configuration keys: '+', '.join(sorted(config.keys()-allowed)))
    if config['recipe'] != 'circular-bayonet':
        raise ValueError('Expected recipe circular-bayonet')
    if config['aperture_mm'] != [110, 110]:
        raise ValueError('This connector recipe requires a 110 mm circular aperture')
    for key, expected in {'outer_radius_mm': 80, 'eccentric_x_mm': -14,
                          'bayonet_turn_deg': 12, 'frame_back_mm': -1.2}.items():
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != expected:
            raise ValueError(f'{key} is fixed at {expected} for this connector layout')
    for key, lower, upper in [('hi3d_relief_mm', 0.0, 4.2), ('fit_clearance_mm', 0.20, 0.35)]:
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f'{key} must be finite in [{lower}, {upper}]')
    fade = config.get('source_boundary_fade_pixels', 18)
    if isinstance(fade, bool) or not isinstance(fade, int) or not 1 <= fade <= 64:
        raise ValueError('source_boundary_fade_pixels must be an integer in [1, 64]')
    if not isinstance(config['height_key'], str) or not config['height_key'].strip():
        raise ValueError('height_key must name an NPZ array')
    if 'title' in config and not isinstance(config['title'], str):
        raise ValueError('title must be text')
    return dict(config, source_boundary_fade_pixels=fade)
