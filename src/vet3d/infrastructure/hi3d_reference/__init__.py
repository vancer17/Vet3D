"""Build and verify byte-preserving, portable Hi3D reference bundles."""

from .bundle import export_reference, materialize_reference, verify_reference

__all__ = ["export_reference", "materialize_reference", "verify_reference"]
