# 文件信息：L1-05 由 Bootstrap 拥有的唯一环境配置入口。
# 作用：用 pydantic-settings 合并显式覆盖、环境变量、显式 dotenv 和 YAML，冻结部署路径及预算。
# 边界：只向装配提供运行资源，不定义业务能力、协议、验收、发布或解释器就绪事实。
"""加载经过类型及目录边界校验的冻结配置，不创建存储或执行程序。"""

from collections.abc import Callable, Mapping
import os
from pathlib import Path
from typing import Annotated, Self, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainValidator, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

from vet3d.adapters import ResourceLimits
from vet3d.operations import DiagnosticLimits


def _integer(value: object) -> int:
    """解析部署整数，允许环境变量数字文本但拒绝布尔和浮点转换。

    :param value: 配置源中的原始字段值。
    :returns: 非布尔正整数。
    :raises ValueError: 输入不是正整数或十进制数字文本。
    """
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is not int or value <= 0:
        raise ValueError("部署预算必须是非布尔正整数")
    return value


type _PositiveInteger = Annotated[int, BeforeValidator(_integer)]


def _path(value: object) -> Path:
    """解析尚未定位的配置路径，拒绝空文本、控制字符和上级跳转。

    :param value: YAML、环境或可信装配提供的路径。
    :returns: 保留符号链接语义的路径对象。
    :raises ValueError: 路径类型或形状不合法。
    """
    if isinstance(value, Path):
        result = value
    elif isinstance(value, str) and value.strip() and not any(ord(character) < 32 for character in value):
        result = Path(value)
    else:
        raise ValueError("配置路径必须是非空路径文本或 Path")
    if ".." in result.parts:
        raise ValueError("配置路径不得包含上级跳转")
    return result


type _ConfigurationPath = Annotated[Path, BeforeValidator(_path)]


def _integer_fields(value: object) -> dict[str, int]:
    """转换唯一预算类型的输入字段，不另建镜像预算模型。

    :param value: 来自配置源的字段映射。
    :returns: 交给原预算构造器校验字段名和范围的整数映射。
    :raises ValueError: 输入不是字符串键映射或字段不是整数。
    """
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError("限额必须是字段映射")
    return {key: _integer(item) for key, item in value.items()}


def _resource_limits(value: object) -> ResourceLimits:
    """直接构造现有资源预算，避免 Pydantic 在数据类校验前把布尔转为整数。

    :param value: 可信装配的 ResourceLimits 或配置字段映射。
    :returns: 唯一 ResourceLimits 实例。
    :raises ValueError: 字段名、必填项或预算无效。
    """
    if type(value) is ResourceLimits:
        return value
    try:
        return ResourceLimits(**_integer_fields(value))
    except TypeError as cause:
        raise ValueError("资源预算字段不符合 ResourceLimits") from cause


def _diagnostic_limits(value: object) -> DiagnosticLimits:
    """直接构造诊断所有者定义的预算，保持默认值和约束只有一个来源。

    :param value: 可信装配的 DiagnosticLimits 或配置字段映射。
    :returns: 唯一 DiagnosticLimits 实例。
    :raises ValueError: 字段名或预算无效。
    """
    if type(value) is DiagnosticLimits:
        return value
    try:
        return DiagnosticLimits(**_integer_fields(value))
    except TypeError as cause:
        raise ValueError("诊断预算字段不符合 DiagnosticLimits") from cause


class WorkspaceSettings(BaseModel):
    """保存工作区装配需要的根和实际文件线程限额。

    :param root: 工作区持久注册及文件存储根。
    :param max_file_operations: 文件操作实际并行上限，不控制业务动作。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    root: _ConfigurationPath
    max_file_operations: _PositiveInteger = 2


class FileSettings(BaseModel):
    """保存受信输入范围和文件消费者的实际读取上限。

    :param input_root: 由宿主提供的输入文件根，不是工作区授权。
    :param max_file_bytes: 每个文件实际 I/O 的字节预算。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    input_root: _ConfigurationPath
    max_file_bytes: _PositiveInteger


class ResourceSettings(BaseModel):
    """保存固定资源安装及读取装配所需的具体参数。

    :param root: 已安装资源的受管根。
    :param source_root: 受信构建包来源根。
    :param limits: 适配器唯一 ResourceLimits，不复制字段定义。
    :param max_readers: 实际资源读取并行上限。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    root: _ConfigurationPath
    source_root: _ConfigurationPath
    limits: Annotated[ResourceLimits, PlainValidator(_resource_limits)]
    max_readers: _PositiveInteger = 2


class DiagnosticSettings(BaseModel):
    """保存私有诊断目录及其所有者定义的唯一预算。

    :param root: 独立于资产、资源和输入的诊断目录。
    :param limits: 唯一诊断预算，省略时使用其原始默认值。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    root: _ConfigurationPath
    limits: Annotated[DiagnosticLimits, PlainValidator(_diagnostic_limits)] = Field(default_factory=DiagnosticLimits)


class InterpreterLocation(BaseModel):
    """把资源原 runtime 名称关联到一个配置位置，不声明可执行性。

    :param runtime: 与 InterpreterRequirement.runtime 精确匹配的原名称。
    :param path: 解释器候选位置，不探测版本、依赖或设备。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    runtime: str
    path: _ConfigurationPath

    @field_validator("runtime")
    @classmethod
    def _validate_runtime(cls, value: str) -> str:
        """保留运行环境名称原值，不制造别名或枚举投影。

        :param value: 配置中的运行环境名称。
        :returns: 原样返回的合法文本。
        :raises ValueError: 名称空白或不能编码为 UTF-8。
        """
        if not value.strip():
            raise ValueError("解释器运行环境名称不得为空白")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as cause:
            raise ValueError("解释器运行环境名称必须能编码为 UTF-8") from cause
        return value


class Settings(BaseSettings):
    """由 load_settings 生成的冻结装配配置，不传入业务内核。

    :param workspaces: 现有工作区宿主的装配参数。
    :param files: 现有受管文件消费者的装配参数。
    :param resources: 现有固定资源宿主的装配参数。
    :param diagnostics: 运维诊断输出及读取的装配参数。
    :param interpreters: 按原运行环境名称查询的候选位置元组。
    """

    model_config = SettingsConfigDict(
        frozen=True, extra="forbid", env_prefix="VET3D_", env_nested_delimiter="__",
        env_file=None, env_file_encoding="utf-8", yaml_file=None, yaml_file_encoding="utf-8",
    )

    workspaces: WorkspaceSettings
    files: FileSettings
    resources: ResourceSettings
    diagnostics: DiagnosticSettings
    interpreters: tuple[InterpreterLocation, ...] = ()

    @classmethod
    def settings_customise_sources(
        cls, settings_cls: type[BaseSettings], init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource, dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """集中规定覆盖顺序，不把 YAML 内容注入为最高优先级的构造参数。

        :param settings_cls: 此次显式文件路径绑定的配置类。
        :param init_settings: 可信装配显式覆盖，优先级最高。
        :param env_settings: 当前进程环境变量。
        :param dotenv_settings: 显式选择的 dotenv 文件；未选择时不读取。
        :param file_secret_settings: 本期无凭证目录消费者，因此不启用此来源。
        :returns: 按优先级从高到低排列的标准来源。
        """
        return init_settings, env_settings, dotenv_settings, YamlConfigSettingsSource(settings_cls)

    @classmethod
    def _base_directory(cls) -> Path:
        """从本次 YAML 来源取得唯一相对路径基准。

        :returns: 由 load_settings 绑定的绝对配置文件父目录。
        :raises ValueError: 调用方绕过统一入口，没有绑定单个配置文件。
        """
        source = cls.model_config.get("yaml_file")
        if not isinstance(source, Path) or not source.is_absolute():
            raise ValueError("请通过 load_settings 显式选择 YAML 配置")
        return source.parent

    @field_validator("workspaces")
    @classmethod
    def _workspace_paths(cls, value: WorkspaceSettings) -> WorkspaceSettings:
        """冻结工作区根，后续 cwd 变化不改变装配位置。

        :param value: 已通过类型校验的工作区配置。
        :returns: 具有绝对根的冻结配置。
        """
        return value.model_copy(update={"root": _absolute(value.root, cls._base_directory())})

    @field_validator("files")
    @classmethod
    def _file_paths(cls, value: FileSettings) -> FileSettings:
        """冻结实际输入根，不探测目录或授予读取权限。

        :param value: 已通过类型校验的文件配置。
        :returns: 具有绝对输入根的冻结配置。
        """
        return value.model_copy(update={"input_root": _absolute(value.input_root, cls._base_directory())})

    @field_validator("resources")
    @classmethod
    def _resource_paths(cls, value: ResourceSettings) -> ResourceSettings:
        """冻结资源安装根及受信来源根，保留唯一预算对象。

        :param value: 已通过类型校验的资源配置。
        :returns: 两个根均为绝对位置的冻结配置。
        """
        base = cls._base_directory()
        return value.model_copy(update={"root": _absolute(value.root, base), "source_root": _absolute(value.source_root, base)})

    @field_validator("diagnostics")
    @classmethod
    def _diagnostic_paths(cls, value: DiagnosticSettings) -> DiagnosticSettings:
        """冻结诊断目录，目录隔离校验在整体配置完成后执行。

        :param value: 已通过类型校验的诊断配置。
        :returns: 具有绝对诊断根的冻结配置。
        """
        return value.model_copy(update={"root": _absolute(value.root, cls._base_directory())})

    @field_validator("interpreters")
    @classmethod
    def _interpreter_paths(cls, value: tuple[InterpreterLocation, ...]) -> tuple[InterpreterLocation, ...]:
        """拒绝重复 runtime，并冻结每个候选路径。

        :param value: 配置来源解析的不可变定位记录。
        :returns: 保留原顺序和运行环境名称的绝对位置记录。
        :raises ValueError: 同一运行环境名称被重复配置。
        """
        if len({item.runtime for item in value}) != len(value):
            raise ValueError("同一 runtime 只能配置一个候选解释器位置")
        base = cls._base_directory()
        return tuple(item.model_copy(update={"path": _absolute(item.path, base)}) for item in value)

    @model_validator(mode="after")
    def _separate_roots(self) -> Self:
        """在产生任何目录副作用前拒绝配置、输入和受管数据相互覆盖。

        :returns: 目录职责互不嵌套的本配置。
        :raises ValueError: 数据根相同、嵌套、指向系统根或覆盖配置文件。
        """
        roots = (
            self.workspaces.root, self.files.input_root, self.resources.root,
            self.resources.source_root, self.diagnostics.root,
        )
        for index, root in enumerate(roots):
            if root == Path(root.anchor):
                raise ValueError("部署数据根不得是文件系统根")
            for other in roots[index + 1:]:
                if root.is_relative_to(other) or other.is_relative_to(root):
                    raise ValueError("工作区、资源、输入、来源及诊断根必须各自独立且互不嵌套")
            for source in (type(self).model_config.get("yaml_file"), type(self).model_config.get("env_file")):
                if isinstance(source, Path) and (source.is_relative_to(root) or root.is_relative_to(source)):
                    raise ValueError("数据根不得覆盖配置文件位置")
        return self


def _absolute(path: Path, base: Path) -> Path:
    """按已固定基准形成绝对路径，不用 resolve 跟随链接改变安全边界。

    :param path: 已校验的绝对或相对路径。
    :param base: 单一绝对配置目录。
    :returns: 词法绝对路径；真实目录安全性由各适配器继续验证。
    """
    return path if path.is_absolute() else base / path


def load_settings(
    config_file: Path, *, env_file: Path | None = None, overrides: Mapping[str, object] | None = None,
) -> Settings:
    """从一个显式 YAML 入口加载完整冻结配置，不创建目录或初始化日志。

    :param config_file: 必须存在的 YAML 文件；其父目录是所有相对路径的基准。
    :param env_file: 可选显式 dotenv 文件；不自动查找 cwd 或父目录中的 .env。
    :param overrides: 可信 Bootstrap 的最高优先级覆盖，不提供给业务或 LLM。
    :returns: 经来源合并、类型和根边界校验的冻结 Settings。
    :raises TypeError: 配置文件路径不是 Path。
    :raises OSError: 指定文件缺失或不可读取。
    :raises ValueError: 配置字段、目录关系或预算无效。
    """
    if not isinstance(config_file, Path) or (env_file is not None and not isinstance(env_file, Path)):
        raise TypeError("配置入口必须显式提供 Path")
    configuration = _absolute(_path(config_file), Path(os.getcwd()))
    dotenv = _absolute(_path(env_file), configuration.parent) if env_file is not None else None
    for source in (configuration, dotenv):
        if source is not None and not source.is_file():
            raise FileNotFoundError(f"指定的配置文件不存在或不是普通文件：{source}")
    values = dict(overrides or {})
    if any(key not in Settings.model_fields for key in values):
        raise ValueError("显式覆盖只能使用当前配置字段，不能覆盖加载器选项")

    class _FileSettings(Settings):
        """绑定本次文件来源，不修改共享类状态或建立第二份配置字段。"""

        model_config = SettingsConfigDict(**{
            **Settings.model_config, "yaml_file": configuration, "env_file": dotenv,
        })

    # 配置来源先产生未知字段；具体类型由同一个 Pydantic Schema 验证。
    configured_type = cast(Callable[..., Settings], _FileSettings)
    return configured_type(**values)
