"""Load a whole native scene or freshly import one GLB in a background process."""
from pathlib import Path
import bpy
from scene_io import import_objects


def open_asset(path, *, frame=None):
    """Replace the current scene, optionally select a frame, and return objects.

    Validate the path before replacing anything. BLEND opens the whole project
    with embedded scripts disabled; GLB uses the existing reset/import adapter.
    No source files are written. Load errors can leave a partial scene.
    """
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in {'.blend', '.glb'}:
        raise ValueError('Expected .blend or .glb')
    if frame is not None and (isinstance(frame, bool) or not isinstance(frame, int)):
        raise ValueError('Frame must be an integer or None')
    if path.suffix.lower() == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    else:
        import_objects(path, reset=True)
    if frame is not None:
        bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    return list(bpy.context.scene.objects)
