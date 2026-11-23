"""Read embedded base-color labels without rendering lights or the background."""
import io
import numpy as np
from PIL import Image
from partition import access, read, validate


def sample(path, threshold=None, *, with_luminance=False):
    doc, binary = read(path)
    vertices, faces = validate(doc, binary)
    prim = doc["meshes"][0]["primitives"][0]
    material = doc["materials"][prim["material"]]
    if material.get("alphaMode", "OPAQUE") != "OPAQUE":
        raise ValueError("Transparent label materials are unsupported")
    pbr = material["pbrMetallicRoughness"]
    texture_info = pbr["baseColorTexture"]
    if texture_info.get("extensions"):
        raise ValueError("Texture transforms are unsupported")
    texture = doc["textures"][texture_info["index"]]
    uv = access(doc, binary, prim["attributes"]["TEXCOORD_" + str(texture_info.get("texCoord", 0))])
    if len(uv) != len(vertices) or not np.isfinite(uv).all():
        raise ValueError("Invalid UV coordinates")
    image = doc["images"][texture["source"]]
    view = doc["bufferViews"][image["bufferView"]]
    offset = view.get("byteOffset", 0)
    if view.get("buffer", 0) != 0 or offset < 0 or offset + view["byteLength"] > len(binary):
        raise ValueError("Invalid embedded image range")
    with Image.open(io.BytesIO(binary[offset:offset + view["byteLength"]])) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float64) / 255
    factor = np.asarray(pbr.get("baseColorFactor", [1, 1, 1, 1]))
    if factor.shape != (4,) or not np.isfinite(factor).all() or np.any(factor < 0) or np.any(factor > 1):
        raise ValueError("Invalid base color factor")
    gray = (rgb * factor[:3]) @ np.array([.299, .587, .114])
    height, width = gray.shape
    sampler = doc.get("samplers", [])[texture["sampler"]] if "sampler" in texture else {}
    def wrap(values, mode):
        if mode == 10497:
            return values % 1
        if mode == 33071:
            return np.clip(values, 0, 1)
        if mode == 33648:
            return 1 - np.abs(values % 2 - 1)
        raise ValueError("Unsupported texture wrapping")
    # Historical seven interior barycentric samples; no shaded-render threshold.
    bary = np.array([[1/3]*3, [.6,.2,.2], [.2,.6,.2], [.2,.2,.6],
                     [.45,.45,.1], [.45,.1,.45], [.1,.45,.45]])
    lum = np.zeros(len(faces))
    for start in range(0, len(faces), 100000):
        uvtri = uv[faces[start:start+100000]]
        for weights in bary:
            points = np.einsum("k,fkd->fd", weights, uvtri)
            x = np.clip(wrap(points[:,0], sampler.get("wrapS",10497)) * width - .5, 0, width - 1)
            y = np.clip(wrap(points[:,1], sampler.get("wrapT",10497)) * height - .5, 0, height - 1)
            x0, y0 = x.astype(int), y.astype(int)
            x1, y1 = np.minimum(x0+1,width-1), np.minimum(y0+1,height-1)
            fx, fy = x-x0, y-y0
            lum[start:start+len(uvtri)] += (gray[y0,x0]*(1-fx)*(1-fy) +
                gray[y0,x1]*fx*(1-fy) + gray[y1,x0]*(1-fx)*fy + gray[y1,x1]*fx*fy) / len(bary)
    tri = vertices[faces].astype(np.float64)
    area = np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]), axis=1)
    if not np.isfinite(area).all() or np.any(area <= 0):
        raise ValueError("Degenerate triangles are unsupported")
    if threshold is None:
        hist = np.histogram(lum, bins=256, range=(0,1), weights=area)[0]
        hist /= hist.sum()
        centers = (np.arange(256)+.5)/256
        weight, moment = np.cumsum(hist), np.cumsum(hist*centers)
        variance = (moment[-1]*weight-moment)**2 / np.maximum(weight*(1-weight),1e-12)
        threshold = float(centers[np.argmax(variance)] + .5/256)
    if not np.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("Threshold must be in (0, 1)")
    labels = (lum > threshold).astype(np.int8)
    if set(np.unique(labels)) != {0,1}:
        raise ValueError("Label texture must contain both hair and head")
    result = vertices, faces, labels, {"threshold": threshold, "luminance_range": [float(lum.min()),float(lum.max())]}
    return (*result, lum) if with_luminance else result
