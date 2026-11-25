# 文件信息：L2-02 阶段 A 的原生 Agent 实验材料准备。
# 作用：复用已归档 Hi3D 文档和共享模块，准备可变工作工程、参考图及旧材质参数。
# 边界：仅是受信实验夹具消费者，不是资源安装器、执行后端或正式资产登记入口。
# 证据：准备成功不证明原生 Agent 已读取 Skill、理解错误、收到图片或自主完成修订。
"""为真实 Agent 闭环准备独立任务材料，不向模型泄露参考图的生成参数。"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


_REFERENCE_FILES = (
    ".dependency-blender-tools/REFERENCE.md",
    ".dependency-blender-tools/references/material-nodes.md",
    ".dependency-blender-tools/scripts/material_nodes.py",
    ".dependency-model-preview/REFERENCE.md",
    ".dependency-model-preview/references/preview-atoms.md",
    ".dependency-model-preview/scripts/preview_scene.py",
)


@dataclass(frozen=True, slots=True)
class TaskMaterials:
    """保存实验材料的位置，不冻结工作文件或声明模型已消费这些资料。

    :param task_dir: 本次独占创建的可变任务目录。
    :param skill: 原生运行时可读取的实验 Skill 入口。
    :param scene: 供 Agent 检查和修订的初始工程。
    :param reference_image: 只通过图片表达目标外观的参考。
    :param legacy_material: 包含旧版材质参数的任务输入。
    :param preparation_log: 受信准备进程的本次诊断文件。
    :param initial_goal: 首轮业务目标，不含修复方案或参考图答案。
    """

    task_dir: Path
    skill: Path
    scene: Path
    reference_image: Path
    legacy_material: Path
    preparation_log: Path
    initial_goal: str


_SKILL = """---
name: vet3d-stage-a
description: 读取已有 Blender 工程和图片要求，复用 Hi3D 模块，在本任务目录自主编程、检查和修订。
---

# 阶段 A 建模实验

本入口用于合成夹具，不提供动物质量、正式发布或业务验收结论。
根据任务目标自行安排检查、代码、执行和视觉修订；真实错误、输出和图片沿原生工具处理。
只在当前任务目录工作，保留输入，在 outputs/ 保存修订结果和实际预览。

## 已提供的共享资源

六份 Hi3D 1.2.11 原件位于 resources/hi3d/，相对目录布局保留；它们不是新的 Tool。
原件的完整工作流和未提供资源不属于本实验，不要求执行 PCG、发布或独立打包流程。

- [Blender 参考](../../../resources/hi3d/.dependency-blender-tools/REFERENCE.md)
- [材质契约](../../../resources/hi3d/.dependency-blender-tools/references/material-nodes.md)
- [预览参考](../../../resources/hi3d/.dependency-model-preview/REFERENCE.md)
- [预览原子](../../../resources/hi3d/.dependency-model-preview/references/preview-atoms.md)

可在自己编写的 Blender Python 中将两个共享 scripts/ 目录加入 sys.path，调用
material_nodes.principled_material 和 preview_scene 的相机、灯光函数；不要复制其实现。
资源原件保持只读。需要的动态脚本直接写在任务目录，无需登记或发布。
Blender 使用当前授权环境提供的可执行入口，后台运行时用 --python-exit-code 1 传播错误。
使用 --disable-autoexec，不自动运行工程内嵌代码。

## 工作材料

inputs/source.blend 是初始工程；inputs/reference.png 是目标外观，只能实际看图取得视觉依据。
inputs/legacy_material.json 是待沿用并适配当前接口的旧材质设置。
starter.py 是尚未适配的现有入口，先运行取得实际诊断，再自主修改；不提供修复步骤。
脚本成功、文件存在和图像已送入模型是不同事实；如未能完成，说明真实缺口。
"""


_STARTER_SCRIPT = '''# 文件信息：阶段 A 输入中的旧版建模入口。
# 作用：读取现有工程和旧材质参数；保留真实 API 错误作为任务诊断。
"""尚未适配当前 Blender 的任务脚本，由原生 Agent 自主修订。"""

import json
from pathlib import Path
import bpy


def main() -> None:
    """应用旧材质设置并尝试保存预览。

    :raises KeyError: 当前接口不支持旧材质输入名称。
    """
    root = Path(__file__).parent
    bpy.ops.wm.open_mainfile(filepath=str(root / "inputs/source.blend"))
    settings = json.loads((root / "inputs/legacy_material.json").read_text())
    node = bpy.data.materials[settings["material"]].node_tree.nodes.get("Principled BSDF")
    for name, value in settings["inputs"].items():
        node.inputs[name].default_value = value
    bpy.context.scene.render.filepath = str(root / "outputs/preview.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
'''


_PREPARE_SCRIPT = '''# 文件信息：阶段 A 受信合成场景生成脚本，运行于临时准备目录。
# 边界：不交付给建模 Agent，不作为执行输入冻结或建模修复方案。
"""用 Hi3D 共享原语生成初始工程和只有图片可见的目标。"""

from __future__ import annotations

from pathlib import Path
import resource
import sys

import bpy
from mathutils import Vector


def main() -> None:
    """生成一个小型 CPU 参考图和可变初始工程，不保存目标参数或目标工程。

    :raises RuntimeError: 当前 Blender 不适合此旧参数错误夹具。
    """
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    sys.dont_write_bytecode = True
    task = Path(sys.argv[sys.argv.index("--") + 1])
    scripts = task / "resources" / "hi3d"
    sys.path.insert(0, str(scripts / ".dependency-blender-tools" / "scripts"))
    sys.path.insert(0, str(scripts / ".dependency-model-preview" / "scripts"))
    from material_nodes import principled_material
    from preview_scene import area_light

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    scene.render.resolution_x = 384
    scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.color = (0.15, 0.15, 0.15)

    bpy.ops.mesh.primitive_plane_add(size=200)
    floor = bpy.context.object
    floor.name = "surface"
    floor.data.materials.append(principled_material("surface_material", (0.42, 0.42, 0.42)))
    bpy.ops.mesh.primitive_cube_add(size=0.85, location=(-1.15, 0.0, 0.425))
    first = bpy.context.object
    first.name = "object_0"
    first.data.materials.append(principled_material("material_0", (0.05, 0.6, 0.08)))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.5, location=(0.0, 0.0, 0.5))
    second = bpy.context.object
    second.name = "object_1"
    second.data.materials.append(principled_material("material_1", (0.04, 0.14, 0.7)))
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=0.5, depth=1.0, location=(1.15, 0.9, 0.5))
    third = bpy.context.object
    third.name = "object_2"
    third.data.materials.append(principled_material("material_2", (0.8, 0.55, 0.03)))

    center = Vector((0.0, 0.0, 0.45))
    camera_data = bpy.data.cameras.new("camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 4.7
    camera = bpy.data.objects.new("camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (4.0, -7.0, 5.0)
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    area_light("light_0", (-3.0, -4.0, 6.0), center, 500, 4, (1, 1, 1), collection=scene.collection, shape="SQUARE")
    area_light("light_1", (4.0, 2.0, 5.0), center, 350, 4, (1, 1, 1), collection=scene.collection, shape="SQUARE")

    node = first.data.materials[0].node_tree.nodes.get("Principled BSDF")
    if "Specular" in node.inputs:
        raise RuntimeError("此版本仍支持旧 socket；不能声称实验包含真实错误恢复")
    scene.render.filepath = "//../outputs/preview.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(task / "inputs" / "source.blend"))
    first.data.materials.clear()
    first.data.materials.append(principled_material("reference_material", (0.8, 0.04, 0.025)))
    third.location.y = 0.0
    scene.render.filepath = str(task / "inputs" / "reference.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
'''


def _copy_reference_files(repo_root: Path, destination: Path) -> None:
    """核对既有发行锁后复制六份原件，保持原字节与相对目录。

    :param repo_root: 当前可信仓库根。
    :param destination: 本次新建任务中的独立资源目录。
    :raises ValueError: 所需原件缺失、仍是 LFS 指针或与既有发行锁不符。
    :raises OSError: 读取或复制失败，调用方保留现场。
    """
    reference = repo_root / "vendor" / "hi3d" / "1.2.11"
    lock = json.loads((reference / "reference.lock.json").read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in lock["artifacts"]}
    for name in _REFERENCE_FILES:
        relative = "raw/resources/runtime/prebuilt-skills/" + name
        expected = entries[relative]
        content = (reference / relative).read_bytes()
        if (
            content.startswith(b"version https://git-lfs.github.com/spec/v1")
            or len(content) != expected["size"]
            or hashlib.sha256(content).hexdigest() != expected["sha256"]
        ):
            raise ValueError(f"Hi3D 原件与既有发行锁不符：{name}")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        target.chmod(0o444)


def prepare_task_materials(repo_root: Path, task_dir: Path, blender: Path) -> TaskMaterials:
    """准备独立实验材料，真实执行受信 Blender 夹具，不启动建模 Agent。

    :param repo_root: 用于读取已锁定 Hi3D 原件的可信仓库根。
    :param task_dir: 必须尚不存在的实验任务目录；失败后保留现场，重做使用新目录。
    :param blender: 已选定且可执行的 Blender 程序绝对路径。
    :returns: 原生运行时可接收的位置与初始目标，不包含视觉答案。
    :raises OSError: 路径或程序不可用，或文件创建失败。
    :raises ValueError: 原件身份不符或材料结果不完整。
    :raises subprocess.CalledProcessError: 受信准备进程失败，日志保留。
    :raises subprocess.TimeoutExpired: 准备超过 90 秒，直接准备进程被终止并等待回收。
    """
    repo_root = repo_root.resolve(strict=True)
    blender = blender.resolve(strict=True)
    task_dir = task_dir.absolute()
    task_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs = task_dir / "inputs"
    inputs.mkdir()
    (task_dir / "outputs").mkdir()
    _copy_reference_files(repo_root, task_dir / "resources" / "hi3d")
    skill = task_dir / ".agents" / "skills" / "vet3d-stage-a" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(_SKILL, encoding="utf-8")
    (task_dir / "starter.py").write_text(_STARTER_SCRIPT, encoding="utf-8")
    legacy = inputs / "legacy_material.json"
    legacy.write_text(
        json.dumps({"material": "material_0", "roughness": 0.5, "inputs": {"Specular": 0.5}}, indent=2) + "\n",
        encoding="utf-8",
    )
    log = task_dir / "preparation.log"
    with TemporaryDirectory(prefix="vet3d-stage-a-prepare-") as temporary:
        script = Path(temporary) / "prepare.py"
        script.write_text(_PREPARE_SCRIPT, encoding="utf-8")
        with log.open("wb") as output:
            subprocess.run(
                [str(blender), "--background", "--factory-startup", "--disable-autoexec",
                 "--threads", "2", "--python-exit-code", "1", "--python", str(script), "--", str(task_dir)],
                cwd=task_dir,
                env={"PATH": os.defpath, "HOME": temporary, "LANG": "C.UTF-8",
                     "PYTHONDONTWRITEBYTECODE": "1"},
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=90,
                check=True,
            )
    scene = inputs / "source.blend"
    reference_image = inputs / "reference.png"
    if not scene.is_file() or not reference_image.is_file():
        raise ValueError("受信准备进程退出但缺少实际工程或参考图")
    initial_goal = (
        "使用 vet3d-stage-a Skill 处理本任务。先运行现有 starter.py 取得实际失败诊断，"
        "再自主修复并完成建模；保留初次运行日志。检查 inputs/source.blend，实际查看 "
        "inputs/reference.png，让最终模型的物件布局和材质外观匹配该参考；保留物件、"
        "场景机位和工作文件。沿用 inputs/legacy_material.json 的旧材质设置并适配实际接口。"
        "请自行编写并执行 Python，复用提供的 Hi3D 共享模块；依据真实日志和实际预览自行修订，"
        "在 outputs/ 交付可编辑工程与最终 PNG。无需等待逐步确认；若无法完成，报告实际原因。"
    )
    return TaskMaterials(task_dir, skill, scene, reference_image, legacy, log, initial_goal)
