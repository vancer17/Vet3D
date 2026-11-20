"""Executable CPU text demo. Replace this adapter with the actual algorithm.

Production Session must load once in __init__, implement the same path API,
validate output semantically, and close only resources it owns.
"""
import os
from pathlib import Path


class Session:
    input_suffixes = {".txt"}
    output_suffix = ".txt"
    profile = "cpu-text-demo"

    def __init__(self, model_dir, device):
        if os.getenv("ALLOW_CPU_DEMO") != "1":
            raise RuntimeError("Implement the real Session, or explicitly set ALLOW_CPU_DEMO=1 for the text demo")
        if device != "cpu":
            raise ValueError("The text demo requires DEVICE=cpu")
        self.model_dir = Path(model_dir).resolve()
        self.closed = False

    @staticmethod
    def validate_options(options):
        if not isinstance(options, dict) or set(options) - {"uppercase"}:
            raise ValueError("Supported text demo option: uppercase")
        uppercase = options.get("uppercase", True)
        if type(uppercase) is not bool:
            raise ValueError("uppercase must be boolean")
        return {"uppercase": uppercase}

    def infer(self, source, target, options):
        if self.closed:
            raise RuntimeError("Session has been closed")
        text = Path(source).read_text(encoding="utf-8")
        Path(target).write_text(text.upper() if options["uppercase"] else text, encoding="utf-8")

    def validate_output(self, source, target, options):
        actual = Path(target).read_text(encoding="utf-8")
        expected = Path(source).read_text(encoding="utf-8")
        if options["uppercase"]:
            expected = expected.upper()
        if not actual or actual != expected:
            raise ValueError("Text output failed semantic validation")
        return {"characters": len(actual)}

    def close(self):
        self.closed = True
