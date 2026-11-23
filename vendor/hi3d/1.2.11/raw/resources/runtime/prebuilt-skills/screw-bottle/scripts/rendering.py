"""Process-local Cycles setup and per-pose framing, without a fixed art direction."""
from pathlib import Path
import bpy
from preview_scene import projected_bounds as _projected_bounds, fit_projected_orthographic_camera
from geometry import finite, integer
from cycles_device import select_cycles_device


def image_margin(value):
    margin = finite(value, 'margin')
    if not 0 <= margin < 0.45:
        raise ValueError('margin must be in [0, .45)')
    return margin


def configure_cycles(scene, preferred='AUTO'):
    result = select_cycles_device(scene, preferred, fallback_cpu=preferred == 'AUTO')
    scene.render.engine = 'CYCLES'
    return result


def _bounds_report(bounds):
    return {'min': [bounds['min_x'], bounds['min_y']],
            'max': [bounds['max_x'], bounds['max_y']]}


def projected_bounds(scene, camera, objects):
    return _bounds_report(_projected_bounds(scene, camera, objects, evaluated=True,
                                           check_depth=True, require_mesh=True))


def fit_orthographic(scene, camera, objects, margin=0.05):
    return _bounds_report(fit_projected_orthographic_camera(
        scene, camera, objects, evaluated=True, margin=image_margin(margin)))


def render_png(scene, camera, objects, output, *, frame, width, height, samples,
               device='AUTO', fit=False, margin=0.05):
    path = Path(output).expanduser().resolve()
    if path.exists() or path.suffix.lower() != '.png':
        raise ValueError('Use a new PNG path')
    margin = image_margin(margin)
    for name, value in [('width', width), ('height', height), ('samples', samples)]:
        integer(value, name, 1)
    scene.camera = camera; scene.frame_set(frame)
    scene.render.resolution_x = width; scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    actual_device = configure_cycles(scene, device)
    scene.cycles.samples = samples; scene.cycles.use_denoising = True
    bounds = fit_orthographic(scene, camera, objects, margin) if fit else projected_bounds(scene, camera, objects)
    if min(bounds['min']) < margin-1e-5 or max(bounds['max']) > 1-margin+1e-5:
        raise ValueError('Product exceeds the requested image margins')
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        size = list(image.size)
        if size != [width, height]:
            raise RuntimeError('Rendered dimensions differ from the requested output')
    finally:
        bpy.data.images.remove(image)
    return {'file': path.name, 'pixels': size, 'max_samples': samples, 'frame': frame,
            'device': actual_device, 'projected_bounds': bounds, 'visual_quality': 'not_tested'}
