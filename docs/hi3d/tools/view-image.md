# view_image

## 工具名称与注册来源

模型可见名称为 `view_image`。工具由 Hi3D Agent 1.2.11（Windows x64）随包的 Codex 0.166.0 提供。Codex 在启用 `ViewImage` 特性时注册该内置函数工具，该版本默认启用。处理器在调用时检查当前模型是否支持图像输入。 [Codex 注册代码](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/spec_plan.rs#L1440) · [特性默认值](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/features/src/lib.rs#L1122)

## 暴露给 LLM 的描述

以下原文已从本机安装包的 `codex.exe` 核对。

```text
View a local image file from the filesystem when visual inspection is needed. Use this for images already available on disk.
```

## 参数与结果

| 参数 | 必填性与默认值 | 可见条件与行为 |
| --- | --- | --- |
| `path` | 必填字符串，无默认值。 | 执行环境文件系统中的图片文件路径。相对路径基于该环境的工作目录解析。 |
| `detail` | 可选字符串，值为 `high` 或 `original`。通常省略时使用 `high`。 | 只有模型支持请求原始细节且当前未启用统一图像预算时，才在模型可见的参数定义中出现。处理器为兼容旧调用仍解析这两个值。启用统一图像预算时，处理器内部使用 `original` 提示，实际图像准备由会话历史处理。 |
| `environment_id` | 可选字符串，省略时选择当前轮的主环境。 | 只有多执行环境模式才在参数定义中出现。提供时使用当前轮中的对应环境 ID。 |

模型可见定义设置 `strict: false`，参数 schema 声明 `additionalProperties: false`，调用应使用该会话展示的字段。环境选择和图片读取分别由宿主分派及处理器完成。 [工具输入和输出 schema](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/view_image_spec.rs#L16) · [环境选择实现](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/mod.rs#L164)

- **普通函数调用结果。** 以原 `call_id` 返回函数输出，主体含一个 `input_image` 内容项，携带内联图像 Data URL 和细节提示。宿主可据此把图像送入模型上下文。
- **代码模式结果。** 返回含 `image_url` 的对象。关闭统一图像预算时，同时返回 `detail`，其值为 `high` 或 `original`。调用脚本可将该对象交给 `image(result)`，将实际图像附加到外层工具输出。 [exec](exec.md)
- **错误。** 模型不支持图像、参数格式错误、非法 `detail`、环境未知或未就绪、路径无法解析、路径指向非文件、沙箱内无法访问或读取、图片内容无法解码，均有对应的工具错误。应按错误信息修正参数、选择可用环境或检查文件后再调用。
- **副作用。** 文件读取受所选执行环境的沙箱约束。成功时发出 `ImageView` 的开始和完成事件，携带工具调用 ID 和解析后的路径。处理器以原文件字节构造 Data URL，日志预览仅记长度。图像准备与缩放由会话历史写入路径处理。工具在本次调用内完成读取并返回，调用结果通过 `call_id` 关联。

[错误和文件读取](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/view_image.rs#L94) · [事件和输出构造](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/view_image.rs#L181)

成功结果交付指定文件的图像内容。图片对应的模型版本、姿态或帧号、相机和观察方向由调用方的取证记录提供；`view_image` 的参数与回包没有这些绑定字段。 [参数与结果](#参数与结果)

## 实现伪代码

以下是依据 Codex 0.166.0 源码重建的伪代码。宿主先为调用选出执行环境。处理器验证模型能力、函数参数和细节提示，通过环境的沙箱读取文件，再尝试解码以排除无效图片。通过校验后，从同一份字节构造普通工具输出或代码模式结果。伪代码将函数分派、处理器和结果适配合并展示。 [图片处理器与结果适配](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/view_image.rs#L94)

```python
def view_image(call, context):
    environment = resolve_environment(call.arguments, context.environments)
    require(context.model.accepts_images)
    args = parse_function_arguments(call, required=("path",))
    require(args.detail in (None, "high", "original"))

    path = environment.resolve_from_cwd(args.path)
    filesystem = environment.filesystem
    sandbox = environment.sandbox_context()
    require(filesystem.metadata(path, sandbox=sandbox).is_file)
    data = filesystem.read_file(path, sandbox=sandbox)
    require(image_can_be_decoded(data))

    original = context.unified_image_budget or (
        context.model.can_request_original_detail and args.detail == "original"
    )
    detail = "original" if original else "high"
    image_url = data_url_from_bytes("application/octet-stream", data)
    context.emit_image_view_started_and_completed(call.id, path)
    if call.is_code_mode:
        result = {"image_url": image_url}
        if not context.unified_image_budget:
            result["detail"] = detail
        return result
    return function_output(call.id, [input_image(image_url, detail)], success=True)
```

## 调用示例

通用请求示例。假定 `inputs/reference.png` 位于主执行环境的工作目录下，只传入各会话共有的 `path` 字段。

```json
{
  "path": "inputs/reference.png"
}
```

**根据已核查的工具声明重建的 Code Mode 示例。** 假定 `exports/example.png` 已写入工作目录。把读取结果交给 `image()` 后，外层工具结果才包含可供模型查看的图像。

```javascript
const result = await tools.view_image({ path: "exports/example.png" });
image(result);
```

## 核查依据

- **安装包和固定源码。** `D:/install/Hi3DAgent.__hi3d-transaction/resources/runtime/codex/vendor/x86_64-pc-windows-msvc/bin/codex.exe` 的同级平台目录内，`codex-package.json` 标明版本为 `0.166.0`。描述字符串从可执行文件的零基字节偏移 `291843042` 开始，文件 SHA-256 为 `9d563ee4e0441ff9d59d612013e0460ddf8e5709735c2d9f6b98b7ef8ca4eb42`。普通函数输出及统一图像预算分支依据固定源码。 [版本标签](https://github.com/openai/codex/tree/rust-v0.166.0) · [固定提交](https://github.com/openai/codex/commit/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856)
- **实际运行记录。** 原始描述与两份本机 rollout 第 2 行 `exec.description` 的嵌套声明逐字一致。活跃样本第 109 → 113 行记录一次读取图片及 `input_image` 输出。第 289 → 293 行、第 349 → 353 行分别记录读取 Blender 渲染到磁盘的两张图片，两次 Code Mode 工具结果各含两个 `input_image` 内容项。证据覆盖 rollout 保存的模型侧工具结果，完整出站模型请求仍待采集。 [本机 rollout](<D:/download/.sparc3d-runtime/environments/prod/codex-home/sessions/2026/11/11/rollout-2026-11-11T11-31-29-01a1c8a9-1f03-7053-b0cc-19fc6d5bee17.jsonl:289>)
