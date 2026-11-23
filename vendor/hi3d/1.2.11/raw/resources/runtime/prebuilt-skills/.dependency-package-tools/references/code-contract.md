# 代码契约导航

完整 [模块与接口](../../.dependency-doc/package-tools.md) 由 doc 唯一维护；运行依赖和边界见 [入口](../REFERENCE.md)。分发时 package-tools 随包提供所链接文档。缺 `pcg/architecture.yaml` 时由 [pcg_architecture.py](../scripts/pcg_architecture.py) 按 kind 生成 linear（skill）或 tree（workflow）。
