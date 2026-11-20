"""Unauthenticated HTTPS downloads, safe extraction, and immutable artifact manifests."""

import os
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
from hi3d_storage import digest, load, now, save


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
    target = Path(target)
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
            shutil.copyfileobj(response, output)
        if not temporary.stat().st_size:
            raise ValueError("Empty download")
        if target.suffix.lower() == ".glb" and not zipfile.is_zipfile(temporary):
            validate_glb(temporary)
        os.link(temporary, target)  # Exclusive creation, including concurrent writers.
    finally:
        temporary.unlink(missing_ok=True)
    return target


def unpack(path, destination):
    path, destination = Path(path), Path(destination)
    if path.suffix.lower() != ".zip":
        return [path]
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
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
            target = destination / entry.filename
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


def download_job(client, path, output, fetcher=fetch):
    job = load(path)
    output = Path(output).resolve()
    if job.get("artifact"):
        verify_artifact(job["artifact"], output)
        return {"cached": True, "artifact": job["artifact"]}
    job, data = query_job(client, path)
    if job.get("last_query_error") or job["state"] != "success" or not data.get("url"):
        raise ValueError("A fresh successful result with a download URL is required")
    suffix = Path(urllib.parse.urlsplit(secure_url(data["url"])).path).suffix.lower()
    if suffix not in {
        ".glb",
        ".gltf",
        ".obj",
        ".stl",
        ".zip",
        ".fbx",
        ".usdz",
        ".3mf",
        ".exr",
        ".png",
        ".bmp",
    }:
        suffix = ".bin"
    target = output / ("api-result" + suffix)
    fetcher(data["url"], target)
    if zipfile.is_zipfile(target) and suffix not in {".zip", ".3mf", ".usdz"}:
        renamed = target.with_suffix(".zip")
        os.link(target, renamed)
        target.unlink()
        target = renamed
    files = unpack(target, output / "extracted")
    artifact = {
        **file_record(target),
        "files": [file_record(item) for item in files],
        "downloaded_at": now(),
    }
    if data.get("cover_url"):
        try:
            suffix = Path(
                urllib.parse.urlsplit(secure_url(data["cover_url"])).path
            ).suffix.lower()
            if suffix not in {".png", ".webp", ".jpg", ".jpeg"}:
                suffix = ".bin"
            cover = fetcher(data["cover_url"], output / ("api-cover" + suffix))
            artifact["cover"] = file_record(cover)
        except Exception as error:  # noqa: BLE001 - suppress response/transport details at the reporting boundary
            artifact["cover_error"] = type(error).__name__
    job["artifact"] = artifact
    save(path, job)
    return {"cached": False, "artifact": artifact}
