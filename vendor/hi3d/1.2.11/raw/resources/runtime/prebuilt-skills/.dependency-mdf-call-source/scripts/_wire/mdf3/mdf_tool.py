"""Official MDF3 transport definitions extracted without semantic changes.

Source: TangPei/mdf3, commit 28f0983a99f40cb73a226611c3a04ca55812d4f5.
Only wire types/codecs are bundled; no worker, configuration or credentials.
"""
from __future__ import annotations
import pickle
from dataclasses import dataclass
from typing import Any

PICKLE_PROTOCOL = 4


def dumps(obj: Any) -> bytes:
    """框架统一的 pickle.dumps; 协议版本固定 PICKLE_PROTOCOL."""
    return pickle.dumps(obj, protocol=PICKLE_PROTOCOL)


def loads(data: bytes) -> Any:
    return pickle.loads(data)


@dataclass
class BinaryFile:
    """对应旧框架 mdf2 的 BinaryFile, 字段语义保持一致, 跨服务 pickle 必须能对得上.

    用法:
        BinaryFile(field_name='image', file_name='a.png', content=b'...')
    """
    field_name: str = ''
    file_name: str = ''
    content: bytes = b''
    file_size: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.content, (bytes, bytearray, memoryview)):
            raise ValueError('BinaryFile.content 必须是 bytes 类型')
        if isinstance(self.content, (bytearray, memoryview)):
            self.content = bytes(self.content)
        if self.file_size <= 0:
            self.file_size = len(self.content)
        if not self.file_name and self.field_name:
            self.file_name = f'{self.field_name}_file'

    def __getstate__(self) -> dict:
        return {
            'field_name': self.field_name,
            'file_name': self.file_name,
            'content': self.content,
            'file_size': self.file_size,
        }

    def __setstate__(self, state: dict) -> None:
        self.field_name = state.get('field_name', '')
        self.file_name = state.get('file_name', '')
        self.content = state.get('content', b'')
        self.file_size = state.get('file_size', 0) or len(self.content)

    def __str__(self) -> str:
        return (
            f"BinaryFile(field_name='{self.field_name}', "
            f"file_name='{self.file_name}', size={self.file_size} bytes)"
        )

    def __repr__(self) -> str:
        return self.__str__()
