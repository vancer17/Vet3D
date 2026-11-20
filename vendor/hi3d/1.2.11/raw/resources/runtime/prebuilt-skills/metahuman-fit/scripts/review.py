"""Bake visible skin detail and render a static registration review in Blender."""

import json
import sys
import time
import subprocess
from pathlib import Path
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_io import load_source
from head_preview import make_mesh, material, studio, render_view
from neck import validate_neck_mask
from preview_export import export_preview
from texture_bake import bake_image


def bake_mask(data, settings, config):
    if settings.get("neck_fairing_indices"):
        validate_neck_mask(
            settings["neck_fairing_indices"],
            settings.get("identity_protected_indices", []),
        )
    mask = np.zeros(len(data["vertices"]), bool)
    mask[settings.get("bake_indices", settings["fit_indices"])] = True
    mask[settings.get("neck_fairing_indices", [])] = False
    mask[settings.get("bake_template_color_indices", [])] = False
    for region in settings.get("ear_regions", []):
        mask[region["core_indices"] + region["blend_indices"]] = False
    return mask


def bake_skin(high, head, data, settings, config):
    """Bake only the observed exterior UV region; leave protected skin flat."""
    root = Path(config["output"])
    tex = root / "textures"
    tex.mkdir(exist_ok=True)
    mask = bake_mask(data, settings, config)
    selected = mask[data["quads"]].sum(1) >= 3
    patch = make_mesh(
        "Bake exterior",
        data["vertices"],
        data["quads"][selected],
        data["quad_uvs"][selected],
    )
    try:
        mat = material("Registered skin", (0.48, 0.42, 0.38, 1))
        head.data.materials.append(mat)
        patch.data.materials.append(mat)
        nt = mat.node_tree
        shader = nt.nodes.get("Principled BSDF")
        scene = bpy.context.scene
        height = max(high.dimensions)
        bake_settings = dict(cage=config.get("cage_fraction",0.012)*height,
                             ray=config.get("ray_fraction",0.06)*height,margin=8,use_clear=False,
                             device=config.get("cycles_device","CPU"),fallback_cpu=False)
        report = dict(
            resolution=config.get("texture_size", 2048),
            exterior_quads=int(selected.sum()),
            normal_convention="OpenGL tangent +Y, 16-bit PNG",
            excluded_regions="Unobserved UV regions keep uniform albedo and flat normals; inspect eye/lip boundaries and seams",
            textures={},
        )
        passes = [
            ("Albedo", "DIFFUSE", "sRGB", (0.48, 0.42, 0.38, 1)),
            ("Normal", "NORMAL", "Non-Color", (0.5, 0.5, 1, 1)),
        ]
        if config.get("template_albedo"):
            passes.append(("Coverage", "EMIT", "Non-Color", (0, 0, 0, 1)))
        for name, kind, space, color in passes:
            head.hide_render = True
            replacements = []
            try:
                if name == "Coverage":
                    for source_material in high.data.materials:
                        nodes = source_material.node_tree
                        output = next(
                            n
                            for n in nodes.nodes
                            if n.type == "OUTPUT_MATERIAL" and n.is_active_output
                        )
                        original = [link.from_socket for link in output.inputs["Surface"].links]
                        emission = nodes.nodes.new("ShaderNodeEmission")
                        emission.inputs["Color"].default_value = (1, 1, 1, 1)
                        nodes.links.new(emission.outputs[0], output.inputs["Surface"])
                        replacements.append((nodes, output, original, emission))
                path = tex / ("MetaHuman_" + name + ".png")
                image, baked = bake_image([high],patch,path=path,name="MetaHuman_"+name,
                                         size=report["resolution"],kind=kind,colorspace=space,fill=color,
                                         normal_16=name=="Normal",overwrite=True,**bake_settings)
            finally:
                for nodes, output, original, emission in replacements:
                    for link in list(output.inputs["Surface"].links):
                        nodes.links.remove(link)
                    for socket in original:
                        nodes.links.new(socket, output.inputs["Surface"])
                    nodes.nodes.remove(emission)
            node=nt.nodes.new("ShaderNodeTexImage");node.image=image;node.name=name
            report["textures"][name] = dict(file=str(path.relative_to(root)),seconds=baked["seconds"])
        if config.get("template_albedo"):
            start = time.monotonic()
            path = root / "texture_config.json"
            path.write_text(json.dumps(config, indent=2))
            subprocess.run(
                [
                    config["texture_python"],
                    str(Path(__file__).with_name("skin_tone.py")),
                    str(path),
                ],
                check=True,
            )
            for label in ["Albedo", "Normal"]:
                img = bpy.data.images.load(
                    str(tex / ("MetaHuman_" + label + "_Fused.png")), check_existing=False
                )
                img.colorspace_settings.name = "sRGB" if label == "Albedo" else "Non-Color"
                img.pack()
                nt.nodes[label].image = img
            report["fusion_seconds"] = time.monotonic() - start
        nt.links.new(nt.nodes["Albedo"].outputs["Color"], shader.inputs["Base Color"])
        normal = nt.nodes.new("ShaderNodeNormalMap")
        normal.name = "Detail normal"
        nt.links.new(nt.nodes["Normal"].outputs["Color"], normal.inputs["Color"])
        nt.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    finally:
        bpy.data.objects.remove(patch, do_unlink=True)
    (root / "bake_report.json").write_text(json.dumps(report, indent=2))
    return mat, normal


def textured_material(root, config):
    mat = material("Registered skin")
    nt = mat.node_tree
    shader = nt.nodes.get("Principled BSDF")
    suffix = "_Fused" if config.get("template_albedo") else ""
    for label in ["Albedo", "Normal"]:
        node = nt.nodes.new("ShaderNodeTexImage")
        node.name = label
        node.image = bpy.data.images.load(
            str(root / "textures" / f"MetaHuman_{label}{suffix}.png"),
            check_existing=False,
        )
        node.image.colorspace_settings.name = (
            "sRGB" if label == "Albedo" else "Non-Color"
        )
        node.image.pack()
    nt.links.new(nt.nodes["Albedo"].outputs["Color"], shader.inputs["Base Color"])
    normal = nt.nodes.new("ShaderNodeNormalMap")
    normal.name = "Detail normal"
    nt.links.new(nt.nodes["Normal"].outputs["Color"], normal.inputs["Color"])
    nt.links.new(normal.outputs["Normal"], shader.inputs["Normal"])
    return mat, normal


def review(config, mode="full"):
    if mode not in ["full", "bake", "preview"]:
        raise ValueError("Unknown review mode")
    root = Path(config["output"])
    root.joinpath("renders").mkdir(exist_ok=True)
    data = np.load(root / "registered.npz", allow_pickle=False)
    target = np.load(config["target"], allow_pickle=False)
    settings = json.loads(Path(config["settings"]).read_text())
    high = load_source(config["source_scene"], config.get("source_object"))
    head = make_mesh(
        "MetaHuman registered neutral — review",
        data["vertices"],
        data["quads"],
        data["quad_uvs"],
    )
    if mode in ["full", "bake"]:
        mat, normal = bake_skin(high, head, data, settings, config)
        if mode == "bake":
            return
    else:
        mat, normal = textured_material(root, config)
        head.data.materials.append(mat)
    high.hide_render = True
    high.hide_set(True)
    sampled = "normals" in target
    low = (
        None
        if sampled
        else make_mesh("Source lowpoly reference", target["vertices"], target["quads"])
    )
    if low:
        low.data.materials.append(material("Reference clay"))
    source_materials = list(high.data.materials)
    clay = material("Geometry clay")
    attachments = []
    preview = root / "MetaHuman_Review.preview.npz"
    eye_material = None
    if config.get("template_eye_albedo"):
        if not config.get("dna") or not preview.exists():
            raise ValueError("Template eyes need a DNA preview with original UVs")
        eye_config = root / "eye_config.json"
        eye_config.write_text(json.dumps(config, indent=2))
        subprocess.run(
            [
                config["texture_python"],
                str(Path(__file__).with_name("eyes.py")),
                str(eye_config),
            ],
            check=True,
        )
        eye_material = material("Template eyes", roughness=0.22)
        nt = eye_material.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(root / "textures/MetaHuman_Eyes.png"))
        node.image.pack()
        nt.links.new(
            node.outputs["Color"], nt.nodes.get("Principled BSDF").inputs["Base Color"]
        )
    if config.get("dna") and preview.exists():
        parts = np.load(preview, allow_pickle=False)
        for key in parts.files:
            if key.endswith("_vertices") and any(
                key.startswith(n) for n in ["eyeLeft_", "eyeRight_", "teeth_"]
            ):
                name = key[:-9]
                uv_key = name + "_triangle_uvs"
                obj = make_mesh(
                    name,
                    parts[key],
                    parts[name + "_triangles"],
                    parts[uv_key] if uv_key in parts else None,
                )
                if eye_material and name.startswith(("eyeLeft_", "eyeRight_")):
                    if uv_key not in parts:
                        raise ValueError(
                            "DNA preview lacks template eye UVs; regenerate it"
                        )
                    obj.data.materials.append(eye_material)
                else:
                    obj.data.materials.append(material(name, (0.7, 0.68, 0.62, 1)))
                if name.startswith("teeth_") and config.get("template_teeth_albedo"):
                    if uv_key not in parts:
                        raise ValueError("DNA preview lacks template teeth UVs")
                    nt = obj.data.materials[0].node_tree
                    node = nt.nodes.new("ShaderNodeTexImage")
                    node.image = bpy.data.images.load(config["template_teeth_albedo"])
                    # Load the original pixels before changing a lazily loaded file path.
                    node.image.pack()
                    node.image.filepath_raw = str(root / "textures/MetaHuman_Teeth.png")
                    node.image.file_format = "PNG"
                    node.image.save()
                    node.image.pack()
                    nt.links.new(
                        node.outputs["Color"],
                        nt.nodes.get("Principled BSDF").inputs["Base Color"],
                    )
                obj["preview_only"] = (
                    "Neutral assembly. RigLogic is in the DNA; this Blender object is static."
                )
                attachments.append(obj)
    camera, center, span = studio(
        [target["vertices"].min(0), target["vertices"].max(0)],
        config.get("render_size", 800),
    )
    scene = bpy.context.scene
    scene.render.image_settings.color_depth = "8"
    angles = [
        ("front", (0, -3, 0)),
        ("threequarter", (1.7, -3, 0)),
        ("side", (3, 0, 0)),
    ]
    for mode in ["highpoly", "lowpoly", "geometry", "detail"]:
        high.hide_render = mode != "highpoly" and not (sampled and mode == "lowpoly")
        if sampled:
            for i, source_mat in enumerate(source_materials):
                high.data.materials[i] = clay if mode == "lowpoly" else source_mat
        else:
            low.hide_render = mode != "lowpoly"
        head.hide_render = mode in ["highpoly", "lowpoly"]
        for part in attachments:
            part.hide_render = mode in ["highpoly", "lowpoly"]
        head.data.materials[0] = mat if mode == "detail" else clay
        for angle, direction in angles:
            render_view(
                camera,
                center,
                span,
                direction,
                root / "renders" / (mode + "_" + angle + ".png"),
            )
    head.data.materials[0] = mat
    if low:
        low.hide_render = True
        low.hide_set(True)
    # The high mesh remains an external source; packed review files contain only the registered result/reference.
    bpy.data.objects.remove(high, do_unlink=True)
    bpy.ops.wm.save_as_mainfile(
        filepath=str(root / "MetaHuman_Review.blend"), compress=True
    )
    report = export_preview([head] + attachments, head, root / "MetaHuman_Review.glb")
    (root / "glb_report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1 :]
    review(json.loads(Path(args[0]).read_text()), args[1] if len(args) > 1 else "full")
