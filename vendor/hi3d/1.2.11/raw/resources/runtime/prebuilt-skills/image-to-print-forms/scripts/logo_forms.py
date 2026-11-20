import argparse
import io
import json
import math
from pathlib import Path

import cv2
import manifold3d as manifold
import numpy as np
import trimesh
from PIL import Image
from shapely import make_valid
from shapely.affinity import translate
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union


TITLES = {3: "分层标牌", 4: "轮廓封底曲面落地放样", 5: "波浪镜像围合", 7: "弧形竖片"}
NAMES = {3: "layered-plaque", 4: "grounded-sweep", 5: "mirrored-wave", 7: "curved-slats"}
COLORS = {"front": "#1C252B", "body": "#3C545E", "edge": "#69818B", "white": "#F6F7F5", "accent": "#74BC38", "base": "#222D33"}


def polygons(geometry):
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if not hasattr(geometry, "geoms"):
        return []
    return [part for child in geometry.geoms for part in polygons(child)]


def cross_section(geometry):
    contours = []
    for polygon in polygons(make_valid(geometry)):
        if polygon.area < 0.0001:
            continue
        polygon = orient(polygon, sign=1)
        contours.append(np.asarray(polygon.exterior.coords[:-1], dtype=np.float64))
        contours.extend(np.asarray(ring.coords[:-1], dtype=np.float64) for ring in polygon.interiors)
    return manifold.CrossSection(contours)


def upright(geometry, front, back, bottom=0):
    return cross_section(geometry).extrude(back - front).rotate((90, 0, 0)).translate((0, back, bottom))


def flat(geometry, bottom, top):
    return cross_section(geometry).extrude(top - bottom).translate((0, 0, bottom))


def to_mesh(solid):
    generated = solid.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(generated.vert_properties[:, :3], dtype=np.float64), faces=np.asarray(generated.tri_verts, dtype=np.int64), process=False)


def to_solid(mesh):
    return manifold.Manifold(manifold.Mesh(np.asarray(mesh.vertices, dtype=np.float32), np.asarray(mesh.faces, dtype=np.uint32)))


def warped(solid, mapping, max_edge=2.6):
    mesh = to_mesh(solid)
    vertices, faces = trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces, max_edge=max_edge, max_iter=9)
    return to_solid(trimesh.Trimesh(vertices=mapping(vertices), faces=faces, process=False))


def write_stl(mesh, path):
    serialized = trimesh.load(io.BytesIO(mesh.export(file_type="stl")), file_type="stl", force="mesh")
    discarded = 0
    if not serialized.is_watertight:
        components = serialized.split(only_watertight=False)
        actual = [component for component in components if abs(component.volume) > 0.00001 or component.area > 0.0001]
        if len(actual) != 1 or not actual[0].is_watertight:
            raise RuntimeError("STL 序列化后存在真实开口或多个实体，不能自动丢弃。")
        discarded = len(components) - 1
        serialized = actual[0]
    serialized.export(path)
    checked = trimesh.load(path, force="mesh")
    if not checked.is_watertight or len(checked.split(only_watertight=False)) != 1:
        raise RuntimeError("最终 STL 回读未通过闭合及连通检查。")
    return {"closed_connected_after_reload": True, "discarded_zero_area_serialization_fragments": discarded}


def trace(mask, transform):
    contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return Polygon()
    shapes = []
    for index, contour in enumerate(contours):
        if hierarchy[0][index][3] != -1 or cv2.contourArea(contour) < 0.8:
            continue
        holes = []
        child = hierarchy[0][index][2]
        while child != -1:
            if len(contours[child]) >= 3:
                holes.append(transform(contours[child].reshape(-1, 2)))
            child = hierarchy[0][child][0]
        if len(contour) >= 3:
            shapes.append(make_valid(Polygon(transform(contour.reshape(-1, 2)), holes)))
    return unary_union(shapes)


def extract(image_path, width):
    image = np.asarray(Image.open(image_path).convert("RGBA"))
    rgb = image[:, :, :3].astype(np.float32)
    border = np.vstack((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]))
    background = np.median(border, axis=0)
    distance = np.linalg.norm(rgb - background, axis=2)
    mask = (distance > 95) & (image[:, :, 3] > 128)
    if np.any(image[:, :, 3] < 128):
        mask = image[:, :, 3] > 128
    coordinates = np.column_stack(np.where(mask))
    if len(coordinates) < 12:
        raise ValueError("未识别到清晰前景；请提供纯色/透明背景的标志，或先确认前景蒙版。")
    top, left = coordinates.min(axis=0)
    bottom, right = coordinates.max(axis=0)
    scale = width / (right - left)
    height = (bottom - top) * scale
    accent_mask = mask & (rgb[:, :, 1] > rgb[:, :, 0] * 1.16) & (rgb[:, :, 1] > rgb[:, :, 2] * 1.1)
    white_mask = mask & ~accent_mask

    def transform(points):
        return np.column_stack(((points[:, 0] - (left + right) / 2) * scale, (bottom - points[:, 1]) * scale + 10))

    white = trace(white_mask, transform)
    accent = trace(accent_mask, transform)
    return white, accent, height + 20, {"source_size_px": [image.shape[1], image.shape[0]], "foreground_box_px": [int(left), int(top), int(right), int(bottom)], "background_rgb": background.tolist(), "logo_width_mm": width, "detached_islands": len(polygons(white)) + len(polygons(accent)), "interpretation": "单张平面标志转实体背板与浮起笔画；绿色为点缀色，其余为浅色"}


def build(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    white, accent, height, analysis = extract(args.input, args.width)
    half_width = args.width / 2 + 10
    rounded = box(-half_width + 4, 4, half_width - 4, height - 4).buffer(4, quad_segs=8)
    models = []
    arrays = {}
    if args.update:
        previous = json.loads((output / "hi3d-logo-forms.json").read_text(encoding="utf-8"))
        models = [record for record in previous["models"] if record["number"] not in args.forms]
        previous_arrays = np.load(output / "hi3d-logo-meshes.npz")
        arrays = {key: previous_arrays[key] for key in previous_arrays.files if not any(key.startswith(f"m{number}_") for number in args.forms)}

    def begin(number):
        record = {"number": number, "title": TITLES[number], "name": f"logo-{NAMES[number]}", "objects": [], "checks": {}}
        models.append(record)
        return record

    def add(record, name, solid, color, role):
        if solid.status() != manifold.Error.NoError or solid.is_empty():
            raise RuntimeError(f"实体构造失败：{name}: {solid.status()}")
        mesh = to_mesh(solid)
        if not mesh.is_watertight or mesh.volume <= 0:
            raise RuntimeError(f"非闭合或体积异常：{name}")
        key = f"m{record['number']}_{len(record['objects'])}"
        arrays[key + "_vertices"] = mesh.vertices / 1000
        arrays[key + "_faces"] = mesh.faces.astype(np.int32)
        record["objects"].append({"name": name, "key": key, "color": color, "role": role, "watertight": True, "volume_mm3": float(mesh.volume), "components": len(solid.decompose())})
        record.setdefault("_solids", []).append(solid)

    def logo(record, front, back, mapping=None, clipping=None, suffix=""):
        for name, shape, color in (("white_letters_star", white, COLORS["white"]), ("green_i", accent, COLORS["accent"])):
            if clipping is not None:
                shape = shape.intersection(clipping)
            if shape.is_empty or shape.area < 0.01:
                continue
            solid = upright(shape, front, back)
            if mapping is not None:
                solid = warped(solid, mapping)
            add(record, f"{record['number']:02d}_{name}{suffix}", solid, color, "logo")

    if 3 in args.forms:
        record = begin(3)
        add(record, "03_backplate", upright(rounded.buffer(2.2), 0, 3), COLORS["base"], "backplate")
        add(record, "03_offset_edge", upright(rounded.buffer(1.1), -1.4, 0.2), COLORS["edge"], "layer")
        add(record, "03_dark_face", upright(rounded, -3.0, -1.2), COLORS["front"], "face")
        logo(record, -4.1, -2.8)
        record["print_note"] = "打印 STL 已将平背朝下；建议在切片中设置颜色分区，颜色本身不等于有装配接口。"

    if 4 in args.forms:
        record = begin(4)
        angle = math.radians(16)
        glyph_outsides = unary_union([Polygon(polygon.exterior) for polygon in polygons(white.union(accent))])
        outline = None
        for offset in (4, 6, 8, 10, 12, 16):
            expanded = glyph_outsides.buffer(offset, quad_segs=8)
            if len(polygons(expanded)) == 1:
                outline = Polygon(polygons(expanded)[0].exterior)
                break
        if outline is None:
            raise RuntimeError("离散笔画无法建立连通背板，需要明确背板形状。")
        vertical_shift = max(0, 1.5 - outline.bounds[1])
        outline = translate(outline, yoff=vertical_shift)

        def tilted(vertices):
            mapped = vertices.copy()
            local_height = vertices[:, 2] + vertical_shift
            mapped[:, 1] = 14 + local_height * math.sin(angle) + vertices[:, 1] * math.cos(angle)
            mapped[:, 2] = 4.8 + local_height * math.cos(angle) - vertices[:, 1] * math.sin(angle)
            return mapped

        loft_seed = cross_section(outline).extrude(1, n_divisions=48).rotate((90, 0, 0)).translate((0, 1, 0))
        loft_mesh = to_mesh(loft_seed)
        vertices = loft_mesh.vertices.copy()
        angles = angle + vertices[:, 1] * (math.pi / 2 - angle)
        loft_mesh.vertices = np.column_stack((vertices[:, 0], 14 + vertices[:, 2] * np.sin(angles), 4.8 + vertices[:, 2] * np.cos(angles)))
        add(record, "04_grounded_curved_body", to_solid(loft_mesh), COLORS["body"], "body")

        def panel_tilt(vertices):
            shifted = vertices.copy()
            shifted[:, 2] -= vertical_shift
            return tilted(shifted)

        add(record, "04_tilted_front_panel", warped(upright(outline, -2.0, 0.25), panel_tilt), COLORS["front"], "face")
        logo(record, -3.1, -1.8, tilted)
        floor_depth = 14 + outline.bounds[3]
        base_shape = box(outline.bounds[0] - 4, 8, outline.bounds[2] + 4, floor_depth + 4).buffer(3, quad_segs=8)
        add(record, "04_common_base", flat(base_shape, 0, 6), COLORS["base"], "base")
        record["rear_ground_depth_mm"] = floor_depth
        record["ground_contact_overlap_mm"] = 1.2
        record["loft"] = {"method": "以封闭外轮廓为前盖，在倾斜立面与 XY 落地盖之间建立对应轮廓的弧形放样", "front_lean_degrees": 16, "loft_sections": 50, "floor_plane_mm": 4.8, "outline_offset_mm": offset, "assumption": "离散标志以外扩连通的顺形背板连接星标及字母；底部盖位于底座内部，不以压低网格替代放样"}
        record["print_note"] = "底座朝下；后部是封闭轮廓至 XY 平面的曲面放样实体。曲面下侧、星标局部及细节仍须切片评估支撑，不承诺免支撑。"

    if 5 in args.forms:
        record = begin(5)

        def wave(vertices):
            mapped = vertices.copy()
            progress = vertices[:, 2] / height
            half_depth = 18 + 5 * np.sin(2 * np.pi * progress) + 2 * np.cos(np.pi * vertices[:, 0] / (2 * half_width)) * np.sin(np.pi * progress)
            mapped[:, 1] = vertices[:, 1] / 18 * half_depth
            mapped[:, 2] += 5.7
            return mapped

        add(record, "05_wave_front_skin", warped(upright(rounded, -18, -15.2), wave), COLORS["front"], "skin")
        add(record, "05_wave_back_skin", warped(upright(rounded, 15.2, 18), wave), COLORS["front"], "skin")
        inner = box(-half_width + 2.8, 2.8, half_width - 2.8, height + 10)
        perimeter = rounded.difference(inner)
        add(record, "05_open_top_perimeter", warped(upright(perimeter, -15.5, 15.5), wave), COLORS["body"], "sidewall")
        logo(record, -19.1, -17.8, wave, suffix="_front")
        logo(record, 17.8, 19.1, wave, suffix="_mirrored_back")
        base_shape = box(-half_width - 3, -27, half_width + 3, 27).buffer(3, quad_segs=8)
        add(record, "05_shared_base", flat(base_shape, 0, 6), COLORS["base"], "base")
        record["cavity"] = "前后镜像，左右及底边围合，上口开放，不加水平封顶桥接"
        record["skin_thickness_nominal_mm"] = 2.8
        record["print_note"] = "底座朝下，开放上口便于观察空腔并减少封顶桥接；波浪与字标仍需切片检查。"

    if 7 in args.forms:
        record = begin(7)
        radius = max(210, half_width * 2.5)

        def curved(vertices):
            mapped = vertices.copy()
            theta = vertices[:, 0] / radius
            mapped[:, 0] = (radius - vertices[:, 1]) * np.sin(theta)
            mapped[:, 1] = radius - (radius - vertices[:, 1]) * np.cos(theta) + 3.0 * np.sin(np.pi * vertices[:, 2] / (height + 6))
            return mapped

        count = max(12, int(half_width * 2 / 7))
        pitch = half_width * 2 / count
        for index in range(count):
            left = -half_width + index * pitch
            right = left + pitch - 1.1
            fin_height = height + 5 * ((left + right) / (2 * half_width)) ** 2
            clipping = box(left, 0, right, fin_height)
            add(record, f"07_fin_{index + 1:02d}", warped(upright(clipping, 0, 22, bottom=5.5), curved), COLORS["body"], "fin")

            def logo_curve(vertices):
                shifted = vertices.copy()
                shifted[:, 2] += 5.5
                return curved(shifted)

            logo(record, -1.15, 0.2, logo_curve, clipping, suffix=f"_{index + 1:02d}")
        add(record, "07_rear_lower_crossbar", warped(upright(box(-half_width, 12, half_width, 15), 19.7, 23), curved), COLORS["base"], "crossbar")
        add(record, "07_rear_upper_crossbar", warped(upright(box(-half_width, height - 2, half_width, height + 1), 19.7, 23), curved), COLORS["base"], "crossbar")
        base_shape = box(-half_width - 4, -5, half_width + 4, 27).buffer(2.5, quad_segs=8)
        add(record, "07_curved_shared_base", warped(flat(base_shape, 0, 6), curved), COLORS["base"], "base")
        record["radius_mm"] = radius
        record["fin_gap_mm"] = 1.1
        record["print_note"] = "底座朝下；字标分布在真实竖片前缘，不用整面贴图遮住片间空隙；背部横梁与底座连接各片。"

    for record in models:
        if "_solids" not in record:
            continue
        solid = manifold.Manifold.batch_boolean(record.pop("_solids"), manifold.OpType.Add).simplify(0.005)
        mesh = to_mesh(solid)
        components = solid.decompose()
        if len(components) != 1 or not mesh.is_watertight:
            raise RuntimeError(f"{record['title']}不是一体连通闭合实体：{len(components)} 个连通体")
        record["checks"] = {"assembled_watertight": bool(mesh.is_watertight), "assembled_components": len(components), "stl_boolean_cleanup_tolerance_mm": 0.005, "assembled_volume_mm3": float(mesh.volume), "uniform_density_center_mm": mesh.center_mass.tolist(), "bounds_mm": mesh.bounds.tolist(), "size_mm": np.ptp(mesh.bounds, axis=0).tolist()}
        record["stl"] = f"hi3d-{record['name']}-print.stl"
        printable = mesh.copy()
        if record["number"] == 3:
            printable.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
        printable.apply_translation([0, 0, -printable.bounds[0, 2]])
        record["checks"]["stl_serialization"] = write_stl(printable, output / record["stl"])
        print(f"BUILT {record['number']} {record['title']} closed, connected, {len(mesh.faces)} triangles", flush=True)
    np.savez_compressed(output / "hi3d-logo-meshes.npz", **arrays)
    models.sort(key=lambda record: record["number"])
    manifest = {"input": str(args.input.name), "analysis": analysis, "palette": COLORS, "models": models, "preview": {"projection": "orthographic", "azimuth_degrees": -45, "elevation_degrees": 35.26438968, "direction": [1, -1, 1], "shared_ortho_scale_m": max(0.23, args.width / 1000 * 1.60)}, "limits": ["图片无法确定背面及真实尺寸；结构是设计假设。", "单密度重心、闭合与连通检查不等于实物打印或强度认证。", "STL 以毫米导出并融合颜色部件；GLB 以米导出并保留颜色及部件名。", "仅支持纯色或透明背景的清晰双色标志；复杂照片应先准备并核对蒙版。"]}
    (output / "hi3d-logo-forms.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=float, default=144)
    parser.add_argument("--forms", type=int, nargs="+", choices=[3, 4, 5, 7], default=[3, 4, 5, 7])
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file() or not 60 <= args.width <= 300:
        parser.error("输入必须存在，标志宽度须为 60–300 毫米；这是演示脚本范围，不是打印能力认证。")
    build(args)


if __name__ == "__main__":
    main()
