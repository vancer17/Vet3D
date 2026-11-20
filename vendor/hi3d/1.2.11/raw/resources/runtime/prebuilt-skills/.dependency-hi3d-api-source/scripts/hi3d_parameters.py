"""Local request planning and integrity-checked multipart assembly."""

import hashlib
import json
import mimetypes
import tempfile
import urllib.parse
import uuid
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

from hi3d_storage import digest, load

SKILL = Path(__file__).resolve().parents[1]


def load_defaults():
    return load(SKILL / "defaults.json")


FORMATS = {
    "model": {"obj": 1, "glb": 2, "stl": 3, "fbx": 4, "usdz": 5, "3mf": 6},
    "relief": {"exr": 1, "png": 2, "stl": 3, "glb": 4, "3mf": 5, "bmp": 6},
    "split": {"obj": 1, "glb": 2, "stl": 3, "fbx": 4, "usdz": 5, "3mf": 6},
    "multicolor": {"obj": 1, "glb": 2, "fbx": 4, "3mf": 6},
}

MODELS = {
    "hi3dv3.0": ["2048quality", "2048master"],
    "hitem3dv2.1": ["1536fast", "1536pro"],
    "hitem3dv2.0": ["1536", "1536pro"],
    "hitem3dv1.5": ["512", "1024", "1536", "1536pro"],
    "scene-portraitv2.1": ["1536profast", "1536pro"],
    "scene-portraitv2.0": ["1536pro"],
    "scene-portraitv1.5": ["1536"],
}

ALLOWED = {
    "model": {
        "model",
        "resolution",
        "request_type",
        "pbr",
        "shading",
        "face",
        "format",
        "callback_url",
    },
    "relief": {
        "model_type",
        "height_relief",
        "rmbg",
        "degree_rmbg",
        "shape_base",
        "thickness_base",
        "width",
        "sculpmode",
        "response_format",
        "format",
        "callback_url",
    },
    "split": {"model", "part", "joint", "merge", "level", "format", "callback_url"},
    "multicolor": {"model", "number_color", "format", "callback_url"},
}


def enum(p, k, values):
    if p.get(k) not in values:
        raise ValueError(k + " must be one of " + str(list(values)))


def number(p, k, lo, hi, step=None):
    try:
        v = Decimal(str(p[k]))
    except (InvalidOperation, KeyError):
        raise ValueError("Invalid numeric parameter: " + k)
    if (
        not v.is_finite()
        or not Decimal(str(lo)) <= v <= Decimal(str(hi))
        or (step is not None and v % Decimal(str(step)))
    ):
        raise ValueError(k + " is outside its range or step.")


def file_info(field, path, exts, max_bytes=None):
    p = Path(path).expanduser().resolve()
    if not p.is_file() or p.suffix.lower() not in exts:
        raise ValueError("Unsupported or missing input file: " + p.name)
    if p.stat().st_size == 0 or (max_bytes and p.stat().st_size > max_bytes):
        raise ValueError("Input size is invalid: " + p.name)
    return {
        "field": field,
        "path": str(p),
        "bytes": p.stat().st_size,
        "sha256": digest(p),
    }


def secure_url(url):
    value = urllib.parse.urlparse(url)
    if value.scheme != "https" or not value.netloc or value.username or value.password:
        raise ValueError("Use an absolute HTTPS URL without embedded credentials")
    return url


def normalize_parameters(kind, overrides, defaults):
    p = dict(
        (defaults if defaults is not None else load_defaults())["parameters"][kind]
    )
    changes = {}
    for item in overrides:
        if "=" not in item:
            raise ValueError("--set requires key=value")
        k, v = item.split("=", 1)
        if k not in ALLOWED[kind]:
            raise ValueError("Unknown parameter for " + kind + ": " + k)
        try:
            v = json.loads(v)
        except ValueError:
            pass
        changes[k] = v
    p.update(changes)
    for k in (
        "request_type",
        "pbr",
        "face",
        "rmbg",
        "shape_base",
        "width",
        "sculpmode",
        "number_color",
    ):
        if k in p:
            number(p, k, -10000000, 10000000, 1)
            p[k] = int(Decimal(str(p[k])))
    fmt = str(p["format"]).lower()
    if fmt in FORMATS[kind]:
        p["format"] = FORMATS[kind][fmt]
    else:
        number(p, "format", 1, 6, 1)
        p["format"] = int(Decimal(str(p["format"])))
    enum(p, "format", FORMATS[kind].values())
    if p.get("callback_url"):
        secure_url(p["callback_url"])
    if set(p) - ALLOWED[kind]:
        raise ValueError("Unknown parameter in defaults")
    return p, changes


def model_inputs(p, changes, images, views, image_url, mesh, mesh_url):
    files = []
    enum(p, "model", MODELS)
    p["resolution"] = str(p["resolution"])
    enum(p, "resolution", MODELS[p["model"]])
    enum(p, "request_type", [1, 2, 3])
    number(p, "face", 100000, 5000000, 1)
    if image_url or not 1 <= len(images) <= 4:
        raise ValueError("Model input requires 1 to 4 local image files.")
    if len(images) > 1:
        views = (views or "").split(",")
        order = ["front", "back", "left", "right"]
        if (
            len(views) != len(images)
            or len(set(views)) != len(views)
            or "front" not in views
            or not set(views) <= set(order)
        ):
            raise ValueError(
                "Multi-view needs unique --views front,back,left,right labels matching the files and including front."
            )
        ordered = sorted(zip(views, images), key=lambda x: order.index(x[0]))
        images = [x[1] for x in ordered]
        p["multi_images_bit"] = "".join("1" if x in views else "0" for x in order)
    elif views and views != "front":
        raise ValueError("Use --views only for a labeled multi-view set.")
    field = "images" if len(images) == 1 else "multi_images"
    files.extend(
        file_info(field, x, {".png", ".jpg", ".jpeg", ".webp"}, 20 * 1024 * 1024)
        for x in images
    )
    if p["request_type"] == 2:
        if "v2.0" in p["model"] or "v2.1" in p["model"]:
            raise ValueError("v2.0/v2.1 do not support standalone texturing.")
        if not (mesh or mesh_url):
            raise ValueError("Texturing requires mesh or mesh_url.")
    elif mesh or mesh_url:
        raise ValueError("mesh input requires request_type=2.")
    if "v1.5" in p["model"]:
        if changes.get("pbr") not in (None, 0):
            raise ValueError("v1.5 does not support PBR.")
        p.pop("pbr", None)
        p.pop("shading", None)
    else:
        enum(p, "pbr", [0, 1])
        number(p, "shading", 0, 1, "0.1")
    if p["request_type"] == 1:
        p.pop("pbr", None)
    mesh_ext = {".glb"}
    mesh_limit = None
    return files, mesh_ext, mesh_limit


def relief_inputs(p, images, views, image_url, mesh, mesh_url):
    files = []
    if (
        mesh
        or mesh_url
        or views
        or (bool(images) == bool(image_url))
        or len(images) > 1
    ):
        raise ValueError("Relief requires exactly one image file OR image URL.")
    if images:
        files.append(
            file_info(
                "image",
                images[0],
                {".png", ".jpg", ".jpeg", ".webp"},
                20 * 1024 * 1024,
            )
        )
    else:
        p["image_url"] = secure_url(image_url)
    enum(p, "model_type", ["base", "pro"])
    enum(p, "rmbg", [0, 1])
    enum(p, "sculpmode", [0, 1])
    enum(p, "response_format", ["url"])
    number(p, "height_relief", ".1", 50)
    number(p, "width", 20, 600, 1)
    if p["rmbg"] == 1:
        number(p, "degree_rmbg", 0, 1, ".01")
        p.pop("shape_base", None)
        p.pop("thickness_base", None)
    else:
        p.pop("degree_rmbg", None)
        p.setdefault("shape_base", 0)
        p.setdefault("thickness_base", "1.0")
        enum(p, "shape_base", [0, 1])
        number(p, "thickness_base", ".1", 20, ".1")
    return files, set(), None


def mesh_inputs(kind, p, images, views, image_url, mesh, mesh_url):
    files = []
    if images or image_url or views or not (mesh or mesh_url):
        raise ValueError(
            "This capability requires one mesh file OR mesh URL, not images."
        )
    mesh_ext = {".glb", ".stl", ".obj"} if kind == "split" else {".glb"}
    mesh_limit = 200 * 1024 * 1024
    if kind == "split":
        enum(p, "model", ["character", "general"])
        if p["model"] == "general":
            for k in ("part", "joint", "merge"):
                p.pop(k, None)
            p.setdefault("level", "medium")
            enum(p, "level", ["low", "medium", "high"])
        else:
            p.pop("level", None)
            enum(p, "part", list("abcdef"))
            enum(p, "joint", ["none", "ball", "dovetail", "pin"])
            if p["joint"] == "none":
                p.pop("merge", None)
            else:
                enum(p, "merge", ["yes", "no"])
    else:
        enum(p, "model", ["multicolor"])
        number(p, "number_color", 0, 8, 1)
    return files, mesh_ext, mesh_limit


def build_plan(
    kind,
    *,
    images=(),
    views=None,
    image_url=None,
    mesh=None,
    mesh_url=None,
    overrides=(),
    defaults=None,
):
    if kind not in ALLOWED:
        raise ValueError("Unsupported task kind")
    p, changes = normalize_parameters(kind, overrides, defaults)
    images = list(images)
    if mesh and mesh_url:
        raise ValueError("Choose mesh file OR mesh URL")
    if kind == "model":
        files, mesh_ext, mesh_limit = model_inputs(
            p, changes, images, views, image_url, mesh, mesh_url
        )
    elif kind == "relief":
        files, mesh_ext, mesh_limit = relief_inputs(
            p, images, views, image_url, mesh, mesh_url
        )
    else:
        files, mesh_ext, mesh_limit = mesh_inputs(
            kind, p, images, views, image_url, mesh, mesh_url
        )
    if mesh:
        files.append(file_info("mesh", mesh, mesh_ext, mesh_limit))
    if mesh_url:
        p["mesh_url"] = secure_url(mesh_url)
        if Path(urllib.parse.urlparse(mesh_url).path).suffix.lower() not in mesh_ext:
            raise ValueError("mesh_url must identify a supported model format.")
    result = {"kind": kind, "parameters": p, "files": files}
    result["fingerprint"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return result


@contextmanager
def multipart(parameters, files):
    """Assemble multipart while verifying the exact bytes still match the plan."""
    boundary = "hi3d-" + uuid.uuid4().hex
    with tempfile.TemporaryFile("w+b") as stream:
        for key, value in parameters.items():
            stream.write(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
                ).encode()
            )
        for index, item in enumerate(files):
            path = Path(item["path"])
            name = "input-" + str(index) + path.suffix.lower()
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
            stream.write(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{item["field"]}"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'
                ).encode()
            )
            fingerprint = hashlib.sha256()
            size = 0
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    fingerprint.update(block)
                    size += len(block)
                    stream.write(block)
            if fingerprint.hexdigest() != item["sha256"] or size != item["bytes"]:
                raise ValueError("Input changed after planning; no task was submitted")
            stream.write(b"\r\n")
        stream.write(("--" + boundary + "--\r\n").encode())
        length = stream.tell()
        stream.seek(0)
        yield stream, "multipart/form-data; boundary=" + boundary, length
