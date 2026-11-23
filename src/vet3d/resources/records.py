# 文件信息：L1-03 受管资源的唯一身份、声明与清单记录。
# 作用：区分逻辑键、清单字节快照、文件内容和解释器要求，校验完整声明闭包。
# 边界：不读取磁盘、不安装依赖，不以资源声明推导执行就绪或业务验收。
"""维护独立于工作区产物的冻结资源契约。"""

from dataclasses import dataclass
import re
from typing import final
import unicodedata

from vet3d.artifacts import ContentFingerprint


class ResourceContractError(ValueError):
    """表示资源输入、清单或关联不满足当前契约。"""


def _require_type(value: object, expected: type[object]) -> None:
    """拒绝隐式转换及其他类别的记录。

    :param value: 需要核对的契约字段。
    :param expected: 唯一允许的具体类型。
    :raises TypeError: 字段类型不匹配。
    """
    if type(value) is not expected:
        raise TypeError(f"资源字段必须是 {expected.__name__}")


def _require_text(value: str) -> None:
    """核对非空白 UTF-8 文本，保留调用方原始描述。

    :param value: 资源元数据或逻辑文本。
    :raises TypeError: 输入不是字符串。
    :raises ResourceContractError: 文本空白或无法编码。
    """
    _require_type(value, str)
    if not value.strip():
        raise ResourceContractError("资源文本不得为空白")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as cause:
        raise ResourceContractError("资源文本必须可编码为 UTF-8") from cause


@final
@dataclass(frozen=True, slots=True)
class ResourceKey:
    """命名维护源中的逻辑资源，不作为产物身份或物理路径。

    :param value: 小写 ASCII 名称，段之间允许点、短横线和下划线。
    """

    value: str

    def __post_init__(self) -> None:
        """拒绝含歧义分隔或路径语义的资源键。

        :raises TypeError: 名称不是字符串。
        :raises ResourceContractError: 名称不满足规范形式。
        """
        _require_text(self.value)
        if re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", self.value) is None:
            raise ResourceContractError("资源键必须使用规范小写 ASCII 名称")


@final
@dataclass(frozen=True, slots=True)
class ResourcePath:
    """表示资源包内的规范相对路径，不包含主机根或工作区身份。

    :param value: 非空且使用正斜杠的相对 POSIX 路径。
    """

    value: str

    def __post_init__(self) -> None:
        """拒绝绝对路径、跳转段及控制字符，不解析实际文件。

        :raises TypeError: 路径不是字符串。
        :raises ResourceContractError: 路径不规范或不可编码。
        """
        _require_text(self.value)
        if self.value.startswith("/") or "\\" in self.value:
            raise ResourceContractError("资源路径必须是正斜杠相对路径")
        if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", self.value) is not None:
            raise ResourceContractError("资源路径不能含盘符或 URI 前缀")
        if any(part in ("", ".", "..") for part in self.value.split("/")):
            raise ResourceContractError("资源路径不能含空段、当前目录或上级目录")
        if any(unicodedata.category(character) == "Cc" for character in self.value):
            raise ResourceContractError("资源路径不能含控制字符")


@final
@dataclass(frozen=True, slots=True)
class ResourceFile:
    """唯一声明包内文件位置及其预期字节内容。

    :param path: 包内相对路径。
    :param content: 实际构建字节的预期指纹，不证明当前文件存在。
    """

    path: ResourcePath
    content: ContentFingerprint

    def __post_init__(self) -> None:
        """核对路径与复用的唯一内容类型。"""
        _require_type(self.path, ResourcePath)
        _require_type(self.content, ContentFingerprint)


@final
@dataclass(frozen=True, slots=True)
class ResourceReference:
    """用清单原始字节快照和逻辑键固定一个确切资源。

    :param snapshot: 原始 manifest 字节的指纹，不是解析后重编码的摘要。
    :param key: 快照内的资源键。
    """

    snapshot: ContentFingerprint
    key: ResourceKey

    def __post_init__(self) -> None:
        """核对快照及逻辑键，不复制版本标签或安装状态。"""
        _require_type(self.snapshot, ContentFingerprint)
        _require_type(self.key, ResourceKey)


@final
@dataclass(frozen=True, slots=True)
class ResourceMetadata:
    """集中保存采纳和使用说明，不把描述转为运行时能力开关。

    :param purpose: 资源用途及其适用范围。
    :param source: 维护源、上游版本及适用来源条件。
    :param inputs: 声明的输入契约或不适用说明。
    :param outputs: 声明的输出契约或不适用说明。
    :param overwrite: 覆盖与同址规则或不适用说明。
    :param failure: 失败产物和副作用说明。
    :param adoption: 当前采纳方式说明。
    :param priority: 开发优先级说明，不使用归档标签代替。
    :param evidence: 验证范围与出处，未实测时明确说明。
    """

    purpose: str
    source: str
    inputs: str
    outputs: str
    overwrite: str
    failure: str
    adoption: str
    priority: str
    evidence: str

    def __post_init__(self) -> None:
        """要求每项说明明确存在，不推断就绪或验收结论。"""
        for value in (
            self.purpose, self.source, self.inputs, self.outputs, self.overwrite,
            self.failure, self.adoption, self.priority, self.evidence,
        ):
            _require_text(value)


@final
@dataclass(frozen=True, slots=True)
class InterpreterRequirement:
    """声明脚本所需运行环境，不探测、定位或安装实际解释器。

    :param runtime: 运行环境名称，如 Python 或 Blender Python。
    :param version: 所需版本的说明，不用于资源版本解析。
    :param dependencies: 外部运行依赖说明，空元组表示未声明额外依赖。
    """

    runtime: str
    version: str
    dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        """核对环境要求的声明形状，不判断实际兼容性。"""
        _require_text(self.runtime)
        _require_text(self.version)
        _require_type(self.dependencies, tuple)
        for dependency in self.dependencies:
            _require_text(dependency)
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ResourceContractError("解释器依赖声明不得重复")


@dataclass(frozen=True, slots=True)
class _Resource:
    """维护三类资源共有字段，具体类别由公开记录类型唯一表达。

    :param key: 包内逻辑键。
    :param entry: 本资源声明文件中的入口。
    :param files: 本资源直接拥有或共享的文件引用。
    :param dependencies: 同包内依赖的资源键。
    :param metadata: 唯一采纳与使用说明。
    """

    key: ResourceKey
    entry: ResourcePath
    files: tuple[ResourcePath, ...]
    dependencies: tuple[ResourceKey, ...]
    metadata: ResourceMetadata

    def __post_init__(self) -> None:
        """核对局部引用，完整依赖关系由清单统一验证。"""
        _require_type(self.key, ResourceKey)
        _require_type(self.entry, ResourcePath)
        _require_type(self.files, tuple)
        _require_type(self.dependencies, tuple)
        _require_type(self.metadata, ResourceMetadata)
        for path in self.files:
            _require_type(path, ResourcePath)
        for key in self.dependencies:
            _require_type(key, ResourceKey)
        if len(set(self.files)) != len(self.files):
            raise ResourceContractError("同一资源不得重复声明文件")
        if self.entry not in self.files:
            raise ResourceContractError("资源入口必须属于本资源文件声明")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ResourceContractError("同一资源不得重复声明依赖")


@final
@dataclass(frozen=True, slots=True)
class DocumentResource(_Resource):
    """声明只作为数据读取的文档；字段含义继承共有资源记录。"""


@final
@dataclass(frozen=True, slots=True)
class TemplateResource(_Resource):
    """声明只作为数据读取的模板；字段含义继承共有资源记录。"""


@final
@dataclass(frozen=True, slots=True)
class ScriptResource(_Resource):
    """声明脚本及必填解释器要求，不授予执行权限。

    :param interpreter: 脚本所需运行环境声明；其他字段见共有资源记录。
    """

    interpreter: InterpreterRequirement

    def __post_init__(self) -> None:
        """在共有字段之后核对脚本专属的解释器声明。"""
        _Resource.__post_init__(self)
        _require_type(self.interpreter, InterpreterRequirement)


type ResourceDefinition = DocumentResource | ScriptResource | TemplateResource


def _validate_definitions(resources: tuple[ResourceDefinition, ...]) -> None:
    """核对资源键与同包依赖闭包，不扫描代码导入或安装依赖。

    :param resources: 需要作为一个完整包解释的资源声明。
    :raises TypeError: 容器或记录类型不符合声明。
    :raises ResourceContractError: 声明为空、键重复、依赖缺失或成环。
    """
    _require_type(resources, tuple)
    if not resources:
        raise ResourceContractError("资源包必须至少声明一个资源")
    for resource in resources:
        if type(resource) not in (DocumentResource, ScriptResource, TemplateResource):
            raise TypeError("资源必须使用明确的文档、脚本或模板记录")
    by_key = {resource.key: resource for resource in resources}
    if len(by_key) != len(resources):
        raise ResourceContractError("包内资源键不得重复")
    names = {path.value for resource in resources for path in resource.files}
    for name in names:
        parts = name.split("/")
        if any("/".join(parts[:index]) in names for index in range(1, len(parts))):
            raise ResourceContractError("资源文件路径不能同时作为另一文件的目录")
    remaining = {resource.key: len(resource.dependencies) for resource in resources}
    dependents: dict[ResourceKey, list[ResourceKey]] = {key: [] for key in by_key}
    for resource in resources:
        for dependency in resource.dependencies:
            if dependency not in by_key:
                raise ResourceContractError("资源依赖必须位于同一包内")
            dependents[dependency].append(resource.key)
    ready = [key for key, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for dependent in dependents[key]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    if visited != len(resources):
        raise ResourceContractError("资源依赖不得形成环")


@final
@dataclass(frozen=True, slots=True)
class ResourceManifest:
    """保存包内唯一文件指纹表及资源闭包，不内嵌自身摘要。

    :param files: 各文件唯一的预期字节声明。
    :param resources: 使用文件表的完整资源声明。
    """

    files: tuple[ResourceFile, ...]
    resources: tuple[ResourceDefinition, ...]

    def __post_init__(self) -> None:
        """核对文件表与资源引用完全相等，并拒绝文件前缀冲突。"""
        _require_type(self.files, tuple)
        for resource_file in self.files:
            _require_type(resource_file, ResourceFile)
        _validate_definitions(self.resources)
        paths = {resource_file.path for resource_file in self.files}
        if len(paths) != len(self.files):
            raise ResourceContractError("资源文件表不得重复声明路径")
        declared = {path for resource in self.resources for path in resource.files}
        if paths != declared:
            raise ResourceContractError("文件表必须恰好覆盖资源声明，不能缺失或夹带文件")

    def find_file(self, path: ResourcePath) -> ResourceFile | None:
        """查询唯一文件声明，不访问磁盘。

        :param path: 包内确切相对路径。
        :returns: 原文件声明；未声明时为空。
        """
        _require_type(path, ResourcePath)
        return next((item for item in self.files if item.path == path), None)

    def find_resource(self, key: ResourceKey) -> ResourceDefinition | None:
        """查询唯一资源声明，不从文件存在性推断登记。

        :param key: 包内确切逻辑键。
        :returns: 原资源声明；未声明时为空。
        """
        _require_type(key, ResourceKey)
        return next((item for item in self.resources if item.key == key), None)


@final
@dataclass(frozen=True, slots=True)
class ResourceDescription:
    """将当前固定快照与资源定义关联，不另存文件摘要或就绪状态。

    :param reference: 读取实例所固定的快照与资源键。
    :param definition: 同一逻辑键的清单定义。
    """

    reference: ResourceReference
    definition: ResourceDefinition

    def __post_init__(self) -> None:
        """拒绝用其他资源定义响应当前确切引用。"""
        _require_type(self.reference, ResourceReference)
        if type(self.definition) not in (DocumentResource, ScriptResource, TemplateResource):
            raise TypeError("资源描述必须包含具体资源定义")
        if self.reference.key != self.definition.key:
            raise ResourceContractError("资源描述必须关联引用中的同一逻辑键")
