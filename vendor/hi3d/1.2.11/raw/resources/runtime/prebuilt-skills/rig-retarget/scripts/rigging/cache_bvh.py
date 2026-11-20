"""Import BVH through Blender and cache evaluated rest/pose matrices at target fps."""

import argparse
import json
from pathlib import Path
import bpy
import numpy as np


def cache_motion(input_path, output_path, fps=30, scale=0.0254, forward="-Z", up="Y"):
    """Run cache_bvh with explicit inputs; see the skill reference for its contract."""
    input_path, output_path = Path(input_path), Path(output_path)
    if output_path.exists():
        raise ValueError("Choose a new cache output path")
    bpy.context.scene.render.fps = fps
    bpy.ops.import_anim.bvh(
        filepath=str(input_path),
        global_scale=scale,
        use_fps_scale=True,
        update_scene_duration=True,
        axis_forward=forward,
        axis_up=up,
    )
    rig = bpy.context.object
    bones = list(rig.data.bones)
    start, end = map(int, rig.animation_data.action.frame_range)
    poses = []
    for frame in range(start, end + 1):
        bpy.context.scene.frame_set(frame)
        poses.append(np.array([np.array(rig.pose.bones[b.name].matrix) for b in bones]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        names=np.array([b.name for b in bones]),
        rest=np.array([np.array(b.matrix_local) for b in bones]),
        poses=np.array(poses),
        fps=fps,
    )
    return {"frames": len(poses), "bones": len(bones), "fps": fps}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--scale", type=float, default=0.0254)
    p.add_argument("--forward", default="-Z")
    p.add_argument("--up", default="Y")
    a = p.parse_args(argv)
    result = cache_motion(a.input, a.output, a.fps, a.scale, a.forward, a.up)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
