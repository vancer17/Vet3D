"""Text-to-image planning and compatible shared workflow export."""
from pathlib import Path

from hi3d_parameters import build_plan
from hi3d_storage import load
from hi3d_generation_workflow import generate_task as generate_image


# Desktop compatibility aliases; explicit native model names remain unchanged.
IMAGE_MODEL_NAMES = {
    "nano-banana-2": "Nano-Banana 2",
    "nano-banana-pro": "Nano-Banana-Pro",
    "seedream-v4.5": "Seedream v4.5",
    "gpt-image-2": "GPT Image 2",
}


def image_plan(prompt, model, aspect_ratio, count, *, kind="text-to-image", request=None, **plan_options):
    if not prompt.strip() or not model.strip() or count not in range(1, 5):
        raise ValueError("Image prompt/model must be nonempty; count must be 1..4")
    if kind not in {"text-to-image", "image-edit"}:
        raise ValueError("Expected an image task kind")
    body = {
        "editTaskType": "TEXT_TO_IMAGE" if kind == "text-to-image" else "EDIT",
        "modelName": IMAGE_MODEL_NAMES.get(model.strip(), model.strip()),
        "prompt": prompt, "imageCount": count, "aspectRatio": aspect_ratio,
    }
    if request is not None:
        native = load(request) if isinstance(request, (str, Path)) else request
        if not isinstance(native, dict):
            raise ValueError("Request must be a JSON object")
        body.update(native)
    return build_plan(kind, request=body, **plan_options)
