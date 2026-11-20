"""Bake final neutral lowpoly from the untouched high mesh, then pack textures."""

import json
import sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_engine import set_engine

from texture_bake import bake_image


def bake(config):
    root = Path(config["output"])
    tex = root / "textures"
    tex.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(root / "Lowpoly_Rigged.blend"), load_ui=False)
    scene = bpy.context.scene
    scene.frame_set(1)
    low = bpy.data.objects["Lowpoly_Head"]
    high = bpy.data.objects["Source_High"]
    for obj in scene.objects:
        if obj.type == "MESH":
            obj.hide_render = obj not in [low, high]
    for obj in [low, high]:
        obj.hide_set(False)
        obj.hide_render = False
    mat = bpy.data.materials.new("Lowpoly baked high detail")
    mat.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(mat)
    nt = mat.node_tree
    shader = nt.nodes.get("Principled BSDF")
    height = max(high.dimensions)
    bake_settings = dict(cage=config.get("cage_fraction",0.009)*height,
                         ray=config.get("ray_fraction",0.04)*height,
                         margin=max(8,config["texture_size"]//170),use_clear=True,
                         device="METAL",fallback_cpu=True)
    sources = []
    try:
        for source_mat in high.data.materials:
            if not source_mat.use_nodes:
                raise ValueError("Source material requires an explicit node adapter")
            nodes = source_mat.node_tree
            p = next((n for n in nodes.nodes if n.type == "BSDF_PRINCIPLED"), None)
            out = next(
                (
                    n
                    for n in nodes.nodes
                    if n.type == "OUTPUT_MATERIAL" and n.is_active_output
                ),
                None,
            )
            if p is None or out is None:
                raise ValueError("Only inspected Principled source materials are supported")
            original = [link.from_socket for link in out.inputs["Surface"].links]
            emission = nodes.nodes.new("ShaderNodeEmission")
            sources.append((nodes, p, out, emission, original))
        report = {
            "resolution": config["texture_size"],
            "normal_convention": "OpenGL tangent +Y; 16-bit PNG",
            "source_geometry": "original high, not the remesher working surface",
            "textures": {},
            "constant_channels": {},
        }
        for label, socket, space in [
            ("BaseColor", "Base Color", "sRGB"),
            ("Roughness", "Roughness", "Non-Color"),
            ("Metallic", "Metallic", "Non-Color"),
            ("Normal", None, "Non-Color"),
        ]:
            if label in ["Roughness", "Metallic"] and config.get("bake_pbr_extras", "auto") == "auto":
                sockets = [p.inputs[socket] for _, p, _, _, _ in sources]
                if sockets and all(not s.is_linked for s in sockets):
                    values = [float(s.default_value) for s in sockets]
                    if max(values) == min(values):
                        shader.inputs[socket].default_value = values[0]
                        report["constant_channels"][label] = {"value": values[0], "reason": "identical source scalar; no texture bake needed"}
                        continue
            for nodes, p, out, emission, original in sources:
                for link in list(out.inputs["Surface"].links):
                    nodes.links.remove(link)
                if socket:
                    for link in list(emission.inputs["Color"].links):
                        nodes.links.remove(link)
                    src = p.inputs[socket]
                    if src.is_linked:
                        nodes.links.new(src.links[0].from_socket, emission.inputs["Color"])
                    else:
                        value = src.default_value
                        emission.inputs["Color"].default_value = (
                            (value, value, value, 1)
                            if isinstance(value, (float, int))
                            else value
                        )
                    nodes.links.new(emission.outputs[0], out.inputs["Surface"])
                else:
                    for original_socket in original:
                        nodes.links.new(original_socket, out.inputs["Surface"])
            path = tex / ("Lowpoly_" + label + ".png")
            print("BAKE", label, flush=True)
            image, baked = bake_image([high],low,path=path,name="Lowpoly_"+label,
                                     size=config["texture_size"],kind="EMIT" if socket else "NORMAL",
                                     colorspace=space,normal_16=label=="Normal",overwrite=True,**bake_settings)
            node=nt.nodes.new("ShaderNodeTexImage");node.name=label;node.image=image
            report["textures"][label] = {"file":str(path.relative_to(root)),"seconds":baked["seconds"]}
    finally:
        for nodes, p, out, emission, original in sources:
            for link in list(out.inputs["Surface"].links):
                nodes.links.remove(link)
            for original_socket in original:
                nodes.links.new(original_socket, out.inputs["Surface"])
            nodes.nodes.remove(emission)
    for label, socket in [
        ("BaseColor", "Base Color"),
        ("Roughness", "Roughness"),
        ("Metallic", "Metallic"),
    ]:
        if label in nt.nodes:
            nt.links.new(nt.nodes[label].outputs["Color"], shader.inputs[socket])
    normal = nt.nodes.new("ShaderNodeNormalMap")
    normal.name = "Baked normal strength"
    nt.links.new(nt.nodes["Normal"].outputs["Color"], normal.inputs["Color"])
    nt.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    high.hide_render = True
    high.hide_set(True)
    for obj in scene.objects:
        if obj.type == "MESH" and obj.name.startswith("Lowpoly_"):
            obj.hide_render = False
    set_engine(scene)
    bpy.ops.wm.save_as_mainfile(
        filepath=str(root / "Lowpoly_Baked.blend"), compress=True
    )
    (root / "bake_report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    bake(json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text()))
