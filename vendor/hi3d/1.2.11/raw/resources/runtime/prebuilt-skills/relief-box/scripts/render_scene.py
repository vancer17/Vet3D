"""Render an existing scene from an explicit frame and renderer specification."""
from pathlib import Path
from render_engine import set_engine, set_samples


def render_scene(source, output, frames, *, engine, resolution, fps=None, threads=None,
                 samples=None, device=None, denoise=None, prefix='', animation=False,
                 overwrite=True):
    """Open a BLEND and write PNGs; never rebuild geometry or save over its source."""
    frames = list(frames)
    if not frames or any(type(f) is not int for f in frames) or len(set(frames)) != len(frames):
        raise ValueError('Nonempty unique integer frames required')
    if animation and frames != list(range(frames[0], frames[-1]+1)):
        raise ValueError('Animation mode requires ascending contiguous frames')
    if (len(resolution) != 2 or any(type(v) is not int or v <= 0 for v in resolution)
            or any(v is not None and (type(v) is not int or v <= 0) for v in [fps, threads, samples])):
        raise ValueError('Positive integer resolution, fps, threads and samples required')
    if '/' in prefix or '\\' in prefix or '#' in prefix:
        raise ValueError('Filename prefix must not contain paths or frame placeholders')
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    paths = [output / f'{prefix}{f:04d}.png' for f in frames]
    if not overwrite and any(p.exists() for p in paths):
        raise FileExistsError('Requested frame output already exists')
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    set_engine(scene, engine)
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.use_file_extension = True
    if fps is not None:
        scene.render.fps = fps
        scene.render.fps_base = 1
    if threads is not None:
        scene.render.threads_mode = 'FIXED'; scene.render.threads = threads
    if samples is not None: set_samples(scene, samples)
    if device is not None: scene.cycles.device = device
    if denoise is not None: scene.cycles.use_denoising = denoise
    output.mkdir(parents=True, exist_ok=True)
    if animation:
        scene.frame_start, scene.frame_end, scene.frame_step = frames[0], frames[-1], 1
        scene.render.filepath = str(output / (prefix+'####.png'))
        scene.render.use_overwrite = overwrite
        result = bpy.ops.render.render(animation=True)
        if 'FINISHED' not in result: raise RuntimeError('Animation rendering did not finish')
    else:
        for frame, path in zip(frames, paths):
            scene.frame_set(frame); scene.render.filepath = str(path)
            result = bpy.ops.render.render(write_still=True)
            if 'FINISHED' not in result: raise RuntimeError(f'Frame {frame} rendering did not finish')
    if any(not p.is_file() or p.stat().st_size == 0 for p in paths):
        raise RuntimeError('Renderer did not produce all requested frames')
    return paths
