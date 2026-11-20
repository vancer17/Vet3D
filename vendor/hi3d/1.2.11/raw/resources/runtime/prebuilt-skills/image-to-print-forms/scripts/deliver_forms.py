import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import MultiPoint, Point


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    specification = json.loads((directory / "hi3d-logo-forms.json").read_text(encoding="utf-8"))
    arrays = np.load(directory / "hi3d-logo-meshes.npz")
    checks = []
    for record in specification["models"]:
        scene = trimesh.load(directory / record["glb"], force="scene", process=False)
        node_names = set(scene.graph.nodes_geometry)
        expected = {part["name"] for part in record["objects"]}
        if node_names != expected:
            raise RuntimeError(f"GLB 部件名不匹配：{record['name']}")
        for node in scene.graph.nodes_geometry:
            transform, geometry = scene.graph[node]
            mesh = scene.geometry[geometry].copy()
            mesh.apply_transform(transform)
            mesh.merge_vertices()
            if not mesh.is_watertight or mesh.volume <= 0:
                raise RuntimeError(f"回读 GLB 非闭合：{node}")
        stl = trimesh.load(directory / record["stl"], force="mesh")
        if not stl.is_watertight or len(stl.split(only_watertight=False)) != 1:
            raise RuntimeError(f"STL 非单一闭合实体：{record['name']}")
        result = {"number": record["number"], "glb_reimport_closed": True, "stable_part_names": True, "stl_closed_connected": True, "stl_size_mm": np.ptp(stl.bounds, axis=0).tolist(), "physical_test": "未进行切片、试打或强度认证"}
        bases = [part for part in record["objects"] if part["role"] == "base"]
        if bases:
            base_vertices = np.vstack([arrays[part["key"] + "_vertices"] * 1000 for part in bases])
            low_points = base_vertices[base_vertices[:, 2] < 0.8, :2]
            support_polygon = MultiPoint(low_points).convex_hull
            center = Point(record["checks"]["uniform_density_center_mm"][:2])
            result["uniform_density_center_in_support_hull"] = bool(support_polygon.contains(center))
            result["uniform_density_support_margin_mm"] = float(support_polygon.boundary.distance(center))
            if not result["uniform_density_center_in_support_hull"]:
                raise RuntimeError(f"重心投影落在接触支承凸包外：{record['name']}")
        if record["number"] == 4:
            body = next(part for part in record["objects"] if part["role"] == "body")
            vertices = arrays[body["key"] + "_vertices"] * 1000
            faces = arrays[body["key"] + "_faces"]
            mesh = trimesh.Trimesh(vertices, faces, process=False)
            ground_faces = np.all(np.abs(vertices[faces][:, :, 2] - record["loft"]["floor_plane_mm"]) < 0.001, axis=1)
            result["loft_landing_cap_area_mm2"] = float(mesh.area_faces[ground_faces].sum())
            if result["loft_landing_cap_area_mm2"] <= 10:
                raise RuntimeError("第4款没有实际的落地封盖面积。")
        for relative in record["previews"].values():
            with Image.open(directory / relative) as image:
                image.verify()
        checks.append(result)
    (directory / "hi3d-logo-verification.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 30)
        small = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 21)
    except OSError:
        font = ImageFont.load_default(size=30)
        small = ImageFont.load_default(size=21)
    board = Image.new("RGB", (1920, 1632), "#F2F4F5")
    draw = ImageDraw.Draw(board)
    draw.text((40, 24), "同一张 Hi3D 图 · 四种实体构造", font=font, fill="#1E2C34")
    draw.text((40, 75), "固定轴测方向：方位 -45° / 仰角 35.264° · 正交投影 · 同尺度", font=small, fill="#53666F")
    notes = {3: "真实叠层与浮起字标", 4: "顺形封底 → 曲面放样 → XY 平面落地", 5: "前后镜像波浪 · 开放上口 · 内部空腔", 7: "弧形竖片 · 字标分片 · 后脊与底座连接"}
    for index, record in enumerate(specification["models"]):
        left = (index % 2) * 960
        top = 128 + (index // 2) * 744
        image = Image.open(directory / record["previews"]["isometric"]).convert("RGB")
        image.thumbnail((960, 640))
        board.paste(image, (left + (960 - image.width) // 2, top))
        draw.text((left + 35, top + 647), f"{record['number']:02d}  {record['title']}", font=font, fill="#1E2C34")
        draw.text((left + 35, top + 693), notes[record["number"]], font=small, fill="#53666F")
    board.save(directory / "hi3d-logo-four-forms-isometric.png", optimize=True)
    print(json.dumps(checks, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
