"""Unauthenticated HTTPS downloads, safe extraction, and immutable artifact manifests."""

import os
import hashlib
import json
import shutil
import stat
import struct
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from hi3d_jobs import query_job
from hi3d_parameters import secure_url
from hi3d_storage import digest, load, now, save, workspace_path


class HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        secure_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_glb(path):
    path = Path(path)
    with path.open("rb") as stream:
        header = stream.read(12)
    if len(header) != 12:
        raise ValueError("Truncated GLB header")
    magic, version, length = struct.unpack("<4sII", header)
    if magic != b"glTF" or version != 2 or length != path.stat().st_size or length < 20:
        raise ValueError("Invalid GLB signature, version or length")


def fetch(url, target, opener=None):
    """Never send API authorization to artifact storage or overwrite a destination."""
    secure_url(url)
    target = workspace_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError("Artifact destination already exists")
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}), HttpsRedirect
    )
    fd, name = tempfile.mkstemp(prefix=".download-", dir=target.parent)
    temporary = Path(name)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Hi3D-skill/1.0"})
        with (
            os.fdopen(fd, "wb") as output,
            opener.open(request, timeout=180) as response,
        ):
            maximum = 1024**3
            if int(response.headers.get("Content-Length", 0)) > maximum:
                raise ValueError("Download exceeds 1 GiB")
            total = 0
            for block in iter(lambda: response.read(1024 * 1024), b""):
                total += len(block)
                if total > maximum:
                    raise ValueError("Download exceeds 1 GiB")
                output.write(block)
        if not temporary.stat().st_size:
            raise ValueError("Empty download")
        if target.suffix.lower() == ".glb" and not zipfile.is_zipfile(temporary):
            validate_glb(temporary)
        os.link(temporary, target)  # Exclusive creation, including concurrent writers.
    finally:
        temporary.unlink(missing_ok=True)
    return target


def unpack(path, destination):
    path, destination = workspace_path(path, must_exist=True), workspace_path(destination)
    if path.suffix.lower() != ".zip":
        return [path]
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 10000:
            raise ValueError("Archive has too many entries")
        names = set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in entry.filename
                or ":" in entry.filename
                or stat.S_ISLNK(entry.external_attr >> 16)
                or str(name) in names
            ):
                raise ValueError("Unsafe or duplicate archive member")
            names.add(str(name))
        if sum(entry.file_size for entry in entries) > 8 * 1024**3:
            raise ValueError("Archive exceeds the 8 GiB extraction limit")
        destination.mkdir(parents=True, exist_ok=False)
        for entry in entries:
            target = workspace_path(destination / entry.filename)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
    files = sorted(item for item in destination.rglob("*") if item.is_file())
    if not files:
        raise ValueError("Archive contains no files")
    for item in files:
        if item.suffix.lower() == ".glb":
            validate_glb(item)
    return files


def file_record(path):
    path = Path(path).resolve()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}


def verify_artifact(artifact, output):
    records = [artifact, *artifact["files"]]
    if artifact.get("cover"):
        records.append(artifact["cover"])
    root = Path(output).resolve()
    for item in records:
        path = Path(item["path"]).resolve()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.stat().st_size != item["bytes"]
            or digest(path) != item["sha256"]
        ):
            raise ValueError(
                "Cached artifact is missing, changed, or belongs to a different output directory"
            )


def result_urls(data):
    """Collect output URLs, including JSON attachment payloads, without input-image URLs."""
    urls = []
    def add(value):
        if isinstance(value, str) and value.startswith("https://") and value not in urls:
            urls.append(value)
    def attachment(value):
        if isinstance(value, str):
            if value.startswith("https://"):
                add(value)
            elif value.lstrip().startswith(("{", "[")):
                try:
                    attachment(json.loads(value))
                except ValueError:
                    pass
        elif isinstance(value, list):
            for item in value:
                attachment(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if not any(x in key.lower() for x in ("source", "input", "reference", "prompt")):
                    attachment(item)
    for key in ("resultImageUrls", "blockImageUrls"):
        for url in data.get(key) or []:
            add(url)
    for model in data.get("model3ds") or []:
        if not isinstance(model, dict):
            continue
        for key, value in model.items():
            if key.startswith("model3D") and key.endswith("Url"):
                add(value)
            elif key.startswith("attachData"):
                attachment(value)
        add(model.get("url"))
    return urls


def download_job(client, path, output, fetcher=fetch):
    job = load(path)
    output = workspace_path(output)
    if job.get("artifact"):
        client.check_job(job)
        verify_artifact(job["artifact"], output)
        return {"cached": True, "artifact": job["artifact"]}
    job, data = query_job(client, path)
    urls = result_urls(data)
    if job.get("last_query_error") or job["state"] != "success" or not urls:
        raise ValueError("A fresh successful result with HTTPS output URLs is required")
    if job.get("download_output") and job["download_output"] != str(output):
        raise ValueError("Resume downloads in the original output directory")
    output.mkdir(parents=True, exist_ok=True)
    job["download_output"] = str(output)
    save(path, job)
    records = []
    for index, url in enumerate(urls):
        parsed = urllib.parse.urlsplit(secure_url(url))
        identity = hashlib.sha256((parsed.scheme + '://' + parsed.netloc + parsed.path).encode()).hexdigest()
        final = workspace_path(output / ("hi3d-result-" + str(index)))
        if final.exists():
            checkpoint = load(final / ".download.json")
            if checkpoint.get("identity") != identity:
                raise ValueError("Result order or identity changed; preserve existing downloads")
            previous = checkpoint["files"]
            if checkpoint.get("complete"):
                verify_artifact({**previous[0], "files": previous}, output)
                records.extend(previous)
                continue
        staging = Path(tempfile.mkdtemp(prefix=".download-stage-", dir=output))
        local_files = []
        try:
            suffix = Path(urllib.parse.urlsplit(secure_url(url)).path).suffix.lower()
            if suffix not in {".glb", ".gltf", ".obj", ".stl", ".zip", ".fbx", ".usdz", ".3mf", ".exr", ".png", ".bmp", ".webp", ".jpg", ".jpeg"}:
                suffix = ".bin"
            target = staging / ("hi3d-api-result-" + str(index) + suffix)
            fetcher(url, target)
            if suffix == ".bin":
                with target.open("rb") as source:
                    header = source.read(16)
                detected = (".png" if header.startswith(b"\x89PNG\r\n\x1a\n") else
                            ".jpg" if header.startswith(b"\xff\xd8\xff") else
                            ".webp" if header[:4] == b"RIFF" and header[8:12] == b"WEBP" else
                            ".glb" if header[:4] == b"glTF" else None)
                if detected:
                    if detected == ".glb":
                        validate_glb(target)
                    renamed = target.with_suffix(detected)
                    os.link(target, renamed)
                    target.unlink()
                    target, suffix = renamed, detected
            if zipfile.is_zipfile(target) and suffix not in {".zip", ".3mf", ".usdz"}:
                renamed = target.with_suffix(".zip")
                os.link(target, renamed)
                target.unlink()
                target = renamed
            local_files.append(target)
            for item in unpack(target, staging / ("hi3d-extracted-" + str(index))):
                if item != target:
                    local_files.append(item)
            completed = [{**file_record(item), "path": str(final / item.relative_to(staging))} for item in local_files]
            if not final.exists():
                final.mkdir()
                save(final / ".download.json", {"identity": identity, "files": completed, "complete": False}, exclusive=True)
            else:
                prior = load(final / ".download.json")
                if prior["identity"] != identity or prior["files"] != completed:
                    raise ValueError("Downloaded content changed while recovering publication")
            for item, metadata in zip(local_files, completed):
                destination = workspace_path(metadata["path"])
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if digest(destination) != metadata["sha256"]:
                        raise ValueError("Existing download changed; never overwrite it")
                else:
                    os.link(item, destination)
            save(final / ".download.json", {"identity": identity, "files": completed, "complete": True})
            job.setdefault("downloaded_results", {})[str(index)] = completed
            save(path, job)
            records.extend(completed)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    artifact = {**records[0], "files": records, "downloaded_at": now()}
    job["artifact"] = artifact
    save(path, job)
    return {"cached": False, "artifact": artifact}


def export_image(source, output):
    """Decode to PNG and exclusively publish; repeated exports only reuse identical bytes."""
    from PIL import Image
    source, output = workspace_path(source, True), workspace_path(output)
    if output.suffix.lower() != ".png":
        raise ValueError("Image output must use .png")
    if not output.name.startswith("hi3d-"):
        raise ValueError("Generated file name must use the hi3d- prefix")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".image-", dir=output.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with Image.open(source) as image:
            image.load()
            image.convert("RGBA" if "A" in image.getbands() else "RGB").save(temporary, format="PNG")
            width, height = image.size
        if output.exists():
            if digest(output) != digest(temporary):
                raise FileExistsError("Image output already exists with different content")
        else:
            os.link(temporary, output)
        return {"path": str(output), "width": width, "height": height, "bytes": output.stat().st_size}
    finally:
        temporary.unlink(missing_ok=True)
