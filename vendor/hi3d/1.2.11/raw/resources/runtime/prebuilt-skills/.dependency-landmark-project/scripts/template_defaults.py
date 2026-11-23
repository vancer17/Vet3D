"""Package-relative geometry prior; no texture-stage dependencies."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets/taro"


def resolve_template_config(config):
    result = dict(config)
    result.setdefault("template", str(ASSETS / "template.npz"))
    if not Path(result["template"]).is_file():
        raise FileNotFoundError("Missing anatomical template")
    return result
