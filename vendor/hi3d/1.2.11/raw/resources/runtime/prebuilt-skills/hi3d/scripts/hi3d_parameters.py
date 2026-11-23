"""Account-backed request planning and integrity-checked multipart assembly."""
import hashlib
import json
import mimetypes
import tempfile
import urllib.parse
import uuid
from contextlib import contextmanager
from pathlib import Path
from hi3d_client import BACKEND, CREATE, IMAGE_KINDS
from hi3d_storage import digest, load, workspace_path

SKILL = Path(__file__).resolve().parent
IMAGES = {".png", ".jpg", ".jpeg", ".webp"}
MESHES = {".glb", ".obj", ".stl", ".fbx", ".ply"}
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
VIEW_NAMES = ["front", "back", "left", "right"]
VIEW_KEYS = ["front_view", "back_view", "left_side_view", "right_side_view"]
IMAGE_PROMPT_MAX_LENGTH = 4000


def load_defaults():
    return json.loads((SKILL / "defaults.json").read_text(encoding="utf-8"))


def image_prompt_budget(prompt):
    """Count Unicode characters without trimming or rewriting the supplied text."""
    if not isinstance(prompt, str):
        raise ValueError("Image prompt must be a string")
    length = len(prompt)
    return {"characters": length, "max_characters": IMAGE_PROMPT_MAX_LENGTH,
            "valid": length <= IMAGE_PROMPT_MAX_LENGTH}


def file_info(field, path, exts, max_bytes=None):
    p = workspace_path(path, must_exist=True)
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


def build_plan(kind, *, images=(), views=None, image_url=None, mesh=None, mesh_url=None,
               overrides=(), defaults=None, request=None, image_slots=None):
    if kind not in CREATE:
        raise ValueError("Unsupported task kind")
    configured = defaults if defaults is not None else load_defaults()
    if request is not None:
        body = load(request) if isinstance(request, (str, Path)) else json.loads(json.dumps(request))
    else:
        body = json.loads(json.dumps(configured["parameters"][kind]))
    if not isinstance(body, dict):
        raise ValueError("Request must be a JSON object")
    params = body if kind in IMAGE_KINDS else body.setdefault("otherParam", {})
    if not isinstance(params, dict):
        raise ValueError("otherParam must be an object")
    changes = {}
    for item in overrides:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError("--set requires key=value")
        try:
            value = json.loads(value)
        except ValueError:
            pass
        changes[key] = value
    # Keep downstream model commands working where the public API mapping is explicit.
    model = changes.pop("model", None)
    resolution = changes.pop("resolution", None)
    request_type = changes.pop("request_type", None)
    if model is not None or resolution is not None or request_type is not None:
        if kind != "model" or model not in (None, "hi3dv3.0") or resolution not in (None, "2048quality", "2048master"):
            raise ValueError("Legacy model/resolution unsupported; use --request with native scene/version/otherParam")
        body.update(scene="general", version="v3.0")
        if resolution:
            # Public resolution names describe UI tiers, not native modelType values.
            params.update(modelType="quality" if resolution == "2048master" else "standard", voxelResolution="2048")
        if request_type is not None:
            if request_type not in (1, 2, 3):
                raise ValueError("request_type must be 1, 2 or 3")
            body["scene"] = "texture" if request_type == 2 else "general"
            params["generationType"] = {1: "mesh", 2: "texture", 3: "both"}[request_type]
    forbidden = {"userId", "appId", "requestId", "callback_url", "retryType", "retryParentTaskId", "tier", "amount"}
    if forbidden.intersection(changes):
        raise ValueError("Identity, billing and callbacks are server-owned")
    for key, value in changes.items():
        if kind not in IMAGE_KINDS and key in {"scene", "version"}:
            body[key] = value
        else:
            params[key] = value
    def reject_identity(value):
        if isinstance(value, dict):
            if forbidden.intersection(value):
                raise ValueError("Identity, billing and callbacks are server-owned")
            for item in value.values():
                reject_identity(item)
        elif isinstance(value, list):
            for item in value:
                reject_identity(item)
    reject_identity(body)
    # Reject old names rather than letting the backend silently ignore them.
    obsolete = {"model_type", "height_relief", "degree_rmbg", "shape_base", "thickness_base", "response_format", "part", "joint", "number_color", "level"}
    if obsolete.intersection(params):
        raise ValueError("Use native hi3d-codex parameter names; see parameters.md")
    if isinstance(params.get("format"), str) and not params["format"].isdigit():
        # Numeric values are generator scene-specific; only model's legacy GLB mapping is retained.
        if kind == "model" and params["format"].lower() == "glb":
            params["format"] = 2
        else:
            raise ValueError("Use the native numeric format value for this scene")
    if kind not in IMAGE_KINDS and (not body.get("scene") or not body.get("version")):
        raise ValueError("scene and version are required")
    if kind in IMAGE_KINDS:
        expected = {"TEXT_TO_IMAGE", "TEXT_TO_IMAGE_MULTI_VIEW"} if kind == "text-to-image" else {"EDIT", "MULTI_VIEW", "MULTI_VIEW_3VIEWS", "MULTI_VIEW_EDIT"}
        if body.get("editTaskType") not in expected:
            raise ValueError("editTaskType does not match task kind")
        # Validate the final DTO after --request/--set, not only convenience args.
        if "prompt" in body:
            budget = image_prompt_budget(body["prompt"])
            if not budget["valid"]:
                raise ValueError(f"Image prompt is {budget['characters']} characters; maximum is {IMAGE_PROMPT_MAX_LENGTH}. Rewrite it; do not truncate.")
    if image_url:
        secure_url(image_url)
    if mesh_url:
        secure_url(mesh_url)
    images = list(images)
    if len(images) > 4 or (images and image_url) or (mesh and mesh_url):
        raise ValueError("Use at most 4 images and choose file OR URL for each input")
    if kind in IMAGE_KINDS and (mesh or mesh_url):
        raise ValueError("2D tasks do not accept a mesh")
    labels = [v.strip().lower() for v in views.split(",")] if views else []
    if labels and (len(labels) != len(images) or len(set(labels)) != len(labels) or not set(labels) <= set(VIEW_NAMES)):
        raise ValueError("--views must match the files with unique front/back/left/right labels")
    slots = None
    if image_slots is not None:
        slots = [int(v.strip()) for v in image_slots.split(",")]
        if kind in IMAGE_KINDS or labels or len(slots) != len(images) or not slots or len(set(slots)) != len(slots) or any(v not in range(4) for v in slots):
            raise ValueError("--image-slots requires one unique 0-3 slot per 3D image; cannot combine with --views")
    files, parts = [], {"request": body}
    if kind in IMAGE_KINDS:
        multi = body["editTaskType"] == "MULTI_VIEW_EDIT"
        if multi and images:
            if not labels:
                raise ValueError("MULTI_VIEW_EDIT files require --views")
            parts["viewKeys"] = [VIEW_KEYS[VIEW_NAMES.index(v)] for v in labels]
        elif labels:
            raise ValueError("--views for 2D requires MULTI_VIEW_EDIT")
        for i, path in enumerate(images):
            field = "viewImages" if multi else ("baseImage" if kind == "image-edit" and i == 0 else "referenceImages")
            files.append(file_info(field, path, IMAGES, 40 * 1024**2))
        if image_url:
            params["baseImageUrl" if kind == "image-edit" else "referenceImageUrls"] = image_url if kind == "image-edit" else [image_url]
    else:
        if len(images) > 1 and not labels and slots is None:
            raise ValueError("Multiple images require explicit --views")
        for path in images:
            files.append(file_info("images", path, IMAGES, 40 * 1024**2))
        if images:
            parts["imageSlots"] = slots if slots is not None else ([VIEW_NAMES.index(v) for v in labels] if labels else [0])
        if image_url:
            params["multiViewSourceImageList"] = [{"sourceOriginImageUrl": image_url}, {}, {}, {}]
        if mesh:
            files.append(file_info("mesh", mesh, MESHES, 200 * 1024**2))
        if mesh_url:
            params["meshUrl"] = mesh_url
    if kind not in IMAGE_KINDS:
        has_images = bool(images or image_url or params.get("multiViewSourceImageList") or params.get("multiViewInfo"))
        has_mesh = bool(mesh or mesh_url or params.get("meshUrl") or params.get("mesh_url"))
        derived = bool(params.get("parentGenerateId"))
        if body["scene"] in {"general", "portrait", "head", "relief", "texture"} and not has_images and not derived:
            raise ValueError("This scene requires reference images")
        if body["scene"] in {"texture", "split-to-print", "multi-color-print", "mcolor_full_pipeline", "segment"} and not has_mesh and not derived:
            raise ValueError("This scene requires a model")
    result = {"backend": BACKEND, "kind": kind, "parameters": parts, "files": files}
    result["fingerprint"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return result


@contextmanager
def multipart(parameters, files):
    """Assemble multipart while verifying the exact bytes still match the plan."""
    boundary = "hi3d-" + uuid.uuid4().hex
    with tempfile.TemporaryFile("w+b") as stream:
        for key, value in parameters.items():
            stream.write(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\nContent-Type: application/json\r\n\r\n{json.dumps(value, ensure_ascii=False, allow_nan=False)}\r\n'
                ).encode()
            )
        for index, item in enumerate(files):
            path = workspace_path(item["path"], must_exist=True)
            name = "input-" + str(index) + path.suffix.lower()
            # Do not rely on the host MIME registry for supported image formats.
            # In particular, some packaged Windows runtimes do not register WebP.
            mime = IMAGE_MIME_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(name)[0] or "application/octet-stream"
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
                    if size > item["bytes"]:
                        raise ValueError("Input grew after planning; no task was submitted")
                    stream.write(block)
            if fingerprint.hexdigest() != item["sha256"] or size != item["bytes"]:
                raise ValueError("Input changed after planning; no task was submitted")
            stream.write(b"\r\n")
        stream.write(("--" + boundary + "--\r\n").encode())
        length = stream.tell()
        if length > 512 * 1024**2:
            raise ValueError("Multipart request exceeds 512 MiB")
        stream.seek(0)
        yield stream, "multipart/form-data; boundary=" + boundary, length
