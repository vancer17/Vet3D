# `glb_clips.py`

## 资源身份与模型可见方式

Hi3D Agent 1.2.11（Windows x64）把 `skills/glb-clips/scripts/glb_clips.py` 物化到 `.dependency-mesh-audit/scripts/`。`glb_bounds.py` 从这个确切路径导入 `read_glb`，该文件是 P1 归档的同目录依赖。模块也保留上游 GLB 动画片段合并的 Python 入口和 CLI。模型可从相关 Skill 资料发现调用契约，实际命令由本地执行工具承担。安装包核查范围内未发现此脚本的独立 LLM Tool 注册或模型可见 `description`。 [归档原件](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_clips.py) · [安装包同步合并契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-glb-clips/references/contract.md>)

**源码模块说明原文**

```text
Merge explicitly simultaneous GLB clips, preserving authored sample times.
```

## 参数、返回与写入

| 入口 | 参数与默认值 | 返回与操作 |
| --- | --- | --- |
| `read_glb(data)` | GLB 容器的完整字节。 | 返回 `(doc, chunks)`，分别为 JSON 对象及后续 `(kind, payload)` 列表。校验 GLB 2.0 首部、总长度、4 字节对齐、chunk 范围和首个且唯一的 JSON chunk。 |
| `merge_bytes(data, *, clips, name, timeline="preserve", allowed_paths=None)` | `data/clips/name` 必填；`clips` 为明确的动画索引序列或 `"all"`。调用方应给非空新动画名，源码对 `name` 只作真值检查，未严格强制字符串。`timeline` 默认 `preserve`，另可选 `shared_accessor`；`allowed_paths` 默认 `None`，可进一步限制目标属性。 | 返回 `(result_bytes, report)`。在最早被选中的位置放入合并动画，保留未选动画顺序。新动画含新名称、samplers 和 channels。后续的所有 chunk 保持字节内容，非动画 JSON 保持数据语义。 |
| `merge_file(source, output, *, clips, name, timeline="preserve", allowed_paths=None, overwrite=False, in_place=False)` | 输入、输出路径，及转换的同名参数。同一解析后路径需要 `in_place=True`。不同路径的已存在目标需要 `overwrite=True`。 | 读取源，校验并转换后以输出目录下的临时文件写入。默认用 `os.link` 独占创建不同路径的输出，允许覆盖时用 `os.replace`。返回报告，最后清理临时文件。 |

合并逐个检查被选动画及其采样器、输出 accessor、节点引用和通道。时间 accessor 必须是单个内嵌 buffer 中的非 sparse float `SCALAR`，样本必须有限、非负且严格递增。允许 `LINEAR`、`STEP`、`CUBICSPLINE`，目标属性限于 `translation`、`rotation`、`scale`、`weights`。同一节点与属性出现冲突时拒绝。默认时间策略保留各自采样时间。`shared_accessor` 额外要求所有 sampler 的 input 指向同一个 accessor。调用方负责确认这些动画应同时播放。 [安装包同步合并契约](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-glb-clips/references/contract.md>)

该操作只合并明确应同时播放的通道，不串联动作，不重定向骨架，也不自动证明源片段的业务语义。`read_glb` 仅验证容器；合并对输出 accessor 检查索引存在，但没有完整解码、校验其全部数据值、形状与动作语义。时间检查及冲突检查通过，不能替代 skin、骨骼、材质、实际加载器和完整动作验收。 [容器读取](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_clips.py:13>) · [合并校验范围](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_clips.py:64>)

`report` 含转换前后 SHA-256、片段数、选中索引、合并通道数、时间策略和各时间 accessor 的起止及样本数。共享 time accessor 存在时返回其索引。报告还给出 `retimed`、`binary_chunks_unchanged` 和 `non_animation_json_unchanged`。老动画本身的名称、extras 和 extensions 随所选动画替换，sampler 与 channel 字段复制到新动画。

空选择、重复索引、空动画、无效引用、时间存储不支持、通道冲突或非法 `timeline` 会失败，解析和文件 I/O 异常向上传播。CLI 必传 `--input`、`--output`、`--name`，选择 `--clips N …` 或 `--all-simultaneous`。可选 `--weights-only` 将允许属性收窄为 `weights`，另有 `--timeline`、`--overwrite`、`--in-place` 和 `--report`。报告打印为 JSON，指定 `--report` 时另写并可覆盖该报告文件。CLI 拒绝报告路径等于输入或输出 GLB。报告另行落盘，报告写入出错时已完成的 GLB 仍保留。 [归档实现](../../upstream/1.2.11/archived-p1/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_clips.py)

`merge_bytes` 是纯字节转换，不改输入字节、不写文件。`merge_file` 在全部转换成功后才创建输出父目录和同目录临时文件；没有 `fsync` 或多文件事务。默认独占发布可拒绝竞态中出现的已有目标；允许覆盖时的替换不提供整组产物回滚。CLI 普通写报告失败可留下完整新 GLB及缺失／部分报告，不能重新执行转换来冒充原写入续跑。返回报告没有统一质量 `pass`，按输出摘要、字节内容和明确转换范围核对结果。 [实际文件适配](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_clips.py:116>) · [CLI 报告写入](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/scripts/glb_clips.py:138>)

## 实现伪代码

**根据已核实源码重建的伪代码。** 单个 GLB 发布与可选报告写入是分步完成的。

```python
def merge_file(source, output, clips, name, timeline="preserve",
               allowed_paths=None, overwrite=False, in_place=False):
    source, output = resolve_paths(source, output)
    require_explicit_in_place_if_same(source, output, in_place)
    require_overwrite_if_existing_other_output(source, output, overwrite)
    result, report = merge_bytes(
        source.read_bytes(), clips=clips, name=name,
        timeline=timeline, allowed_paths=allowed_paths,
    )
    create_output_parent(output)
    temporary = create_same_directory_temporary(output)
    try:
        write_and_close_temporary(temporary, result)
        if source != output and not overwrite:
            link_exclusively(temporary, output)
        else:
            replace_target(temporary, output)
    finally:
        remove_temporary_if_present(temporary)
    return report


def cli(args):
    require_report_distinct_from_glb_paths(args)
    report = merge_file_from_arguments(args)
    if args.report:
        write_json_overwriting(args.report, report)
    print_json(report)
```

## 依赖、权限与前置 Hook

该文件仅导入 Python 标准库。容器读取与字节合并可在普通 Python 进程中执行，落盘接口需要目标父目录写入许可及相应的链接或替换能力。临时文件与目标位于同目录。经宿主发起 CLI 时适用对应工具的权限、沙箱与前置检查。 [本地执行工具](../../tools/exec-command.md)

## 调用示例与核查依据

**调用示例。** 在归档 `.dependency-mesh-audit/scripts/` 已加入模块搜索路径时，读取容器并查看声明动画数量和剩余块类型。

```python
from pathlib import Path

from glb_clips import read_glb

doc, chunks = read_glb(Path("fixtures/scene.glb").read_bytes())
print(len(doc.get("animations", [])), [kind for kind, _ in chunks])
```

**命令示例。** 在同一脚本目录下调用 CLI。样件须已包含索引 0 和 1 的非冲突同步通道。

```powershell
python -B glb_clips.py --input fixtures/scene.glb --output out/preview.glb --clips 0 1 --name "Combined Preview" --report out/merge.json
```

P1 已核实的直接消费者是包围盒检查的容器读取。随包夹具覆盖坏首部、坏总长、重复 JSON、未对齐 chunk 及未知尾块原样返回。用归档脚本与合成 GLB 实测两个非冲突通道合并、BIN 字节保持、报告输出和已有目标拒绝。真实同步片段、多播放器播放行为、压缩 accessor 和动物动作语义仍各自待验。 [P1 精确文件表](../../upstream/1.2.11/extraction/p1/priority.md) · [安装包容器测试](<D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/prebuilt-skills/.dependency-mesh-audit/tests/test_glb_bounds.py>)

归档与安装副本 SHA-256 同为 `9a6be55268d9156efcccbd9572206cbbc4ffef4a462d1615e89e1560ecd89412`。`name` 真值、输出 accessor 校验范围、无 `fsync` 及分步报告写入属于源码核查；本次没有新增竞态、报告写入中断或断电持久化实测。 [P1 归档收据](../../upstream/1.2.11/archived-p1/archive.lock.json)
