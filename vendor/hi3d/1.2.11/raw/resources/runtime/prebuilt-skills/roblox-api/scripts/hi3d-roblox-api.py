"""Roblox place inspection and a single Open Cloud version upload.

Standard library only. Pure contract functions do not authenticate. A durable
intent precedes the one POST; an ambiguous submission is never retried here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import xml.etree.ElementTree as ET

MAX_PLACE_BYTES = 100 * 1024 * 1024  # Conservative local upload ceiling.
UNSUPPORTED_CLOUD_CLASSES = frozenset({
    "EditableImage", "EditableMesh", "PartOperation", "UnionOperation",
    "NegateOperation", "SurfaceAppearance", "BaseWrap", "WrapLayer", "WrapTarget",
})
PART_CLASSES = frozenset({"Part", "MeshPart", "SpawnLocation", "WedgePart",
                          "CornerWedgePart", "TrussPart", "UnionOperation"})


def positive_id(value):
    """Canonical decimal Roblox ID; booleans, signs and URL fragments fail."""
    if (isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,18}", str(value))
            or int(value) > 9223372036854775807):
        raise ValueError("Expected a positive decimal Roblox ID")
    return str(value)


def parse_place(data):
    """Parse an XML place without executing scripts or resolving entities."""
    if not data or len(data) > MAX_PLACE_BYTES:
        raise ValueError("Empty or over-budget place")
    # Generated XML places use UTF-8. Other encodings require Studio conversion.
    text = data.decode("utf-8-sig")
    if "\x00" in text or re.search(r"<!\s*(DOCTYPE|ENTITY)\b", text, re.I):
        raise ValueError("DTD/entities and non-UTF-8 place XML are unsupported")
    root = ET.fromstring(text)
    if root.tag != "roblox" or root.get("version") != "4":
        raise ValueError("Expected Roblox XML version 4")
    return root


def inspect_place(data):
    """Return static facts only; no runtime, asset permission or FPS claims."""
    root = parse_place(data)
    counts, scripts, resources, invalid_local = {}, [], [], []
    referents, duplicates = set(), []
    def visit(item, parents):
        cls = item.get("class", "")
        counts[cls] = counts.get(cls, 0) + 1
        props = item.find("Properties")
        props = [] if props is None else list(props)
        name = next((p.text for p in props if p.get("name") == "Name"), cls)
        path = parents + [name or cls]
        ref = item.get("referent")
        if ref:
            if ref in referents:
                duplicates.append(ref)
            referents.add(ref)
        if cls in {"Script", "LocalScript", "ModuleScript"}:
            source = next((p.text or "" for p in props if p.get("name") == "Source"), "")
            scripts.append({"path": "/".join(path), "class": cls,
                            "source_bytes": len(source.encode("utf-8"))})
        for prop in props:
            if prop.tag == "Content":
                for node in prop.iter("url"):
                    url = (node.text or "").strip()
                    if not url:
                        continue
                    # Never echo URLs: they may contain credentials or signatures.
                    scheme = url.split(":", 1)[0].lower() if ":" in url else "relative"
                    resources.append({"path": "/".join(path),
                                      "property": prop.get("name"), "scheme": scheme})
                    if scheme not in {"rbxassetid", "rbxasset", "http", "https", "rbxgameasset", "rbxthumb"}:
                        invalid_local.append("/".join(path) + ":" + str(prop.get("name")))
        for child in item.findall("Item"):
            visit(child, path)
    for item in root.findall("Item"):
        visit(item, [])
    return {"schema": "roblox.place-inspection.v1", "classes": dict(sorted(counts.items())),
            "part_count": sum(counts.get(k, 0) for k in PART_CLASSES),
            "scripts": scripts, "content_references": resources,
            "invalid_local_content": invalid_local, "duplicate_referents": duplicates,
            "cloud_unsupported_classes": sorted(set(counts) & UNSUPPORTED_CLOUD_CLASSES),
            "runtime_tested": False, "asset_permissions_tested": False,
            "native_part_triangles": None}


def publish_plan(data, suffix, universe_id, place_id):
    """Build a credential-free plan for an EXISTING place, not a new game."""
    uid, pid = positive_id(universe_id), positive_id(place_id)
    if not data or len(data) > MAX_PLACE_BYTES:
        raise ValueError("Empty or over-budget place")
    if suffix.lower() == ".rbxlx":
        facts = inspect_place(data)
        if facts["invalid_local_content"] or facts["duplicate_referents"]:
            raise ValueError("Repair local content references or duplicate referents in Studio")
        if facts["cloud_unsupported_classes"]:
            raise ValueError("This place contains classes requiring Studio publishing")
        content_type, inspection = "application/xml", "xml_static"
    elif suffix.lower() == ".rbxl" and data.startswith(b"<roblox!\x89\xff\r\n\x1a\n"):
        content_type, inspection = "application/octet-stream", "studio_required"
    else:
        raise ValueError("Expected a .rbxlx or binary .rbxl place")
    return {"schema": "roblox.publish-plan.v1", "universe_id": uid, "place_id": pid,
            "method": "POST", "url": f"https://apis.roblox.com/universes/v1/{uid}/places/{pid}/versions?versionType=Published",
            "content_type": content_type, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "inspection": inspection,
            "visibility": "unchanged_unknown", "creates_experience": False}


def save_new_json(path, value):
    """Exclusive record creation: do not overwrite an old intent or symlink."""
    path = Path(path)
    if path.parent.resolve() != path.parent.absolute():
        raise ValueError("Record parent must be a resolved, non-symlink path")
    with path.open("x", encoding="utf-8") as out:
        os.chmod(path, 0o600)
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())


def replace_record(path, value):
    """Update only this call's regular intent, retaining it on write failure."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Record must be a private regular file")
    fd, temp = tempfile.mkstemp(prefix=".roblox-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def upload_once(plan, data, job_path, transport, *, authorized=False, studio_reviewed=False):
    """Persist intent, invoke injected transport once, save a bounded receipt.

    transport(plan, bytes) -> (HTTP status, response bytes). It must not follow
    redirects or retry. No credentials or free-text responses enter the record.
    """
    suffix = ".rbxlx" if plan.get("content_type") == "application/xml" else ".rbxl"
    canonical = publish_plan(data, suffix, plan.get("universe_id"), plan.get("place_id"))
    if plan != canonical:
        raise ValueError("Plan or upload bytes changed; prepare a new reviewed plan")
    job_path = Path(job_path)
    if job_path.is_symlink():
        raise ValueError("Symlink job refused")
    if job_path.exists():
        old = json.loads(job_path.read_text(encoding="utf-8"))
        if old.get("plan") != plan:
            raise ValueError("Existing intent belongs to a different publish plan")
        if old.get("schema") != "roblox.publish-receipt.v1" or old.get("state") not in {
            "submitting", "submission_uncertain", "rejected", "uploaded"}:
            raise ValueError("Invalid publish record; inspect without submitting")
        return old  # Includes submitting/unknown: never repeats a POST.
    if not authorized or not studio_reviewed:
        raise ValueError("Publishing authorization and actual Studio review are required")
    record = {"schema": "roblox.publish-receipt.v1", "plan": plan,
              "state": "submitting", "public_verified": False,
              "multiplayer_verified": False}
    save_new_json(job_path, record)
    try:
        status, body = transport(plan, data)
        if type(status) is not int or not 100 <= status <= 599:
            raise ValueError("Invalid transport status")
        record["http_status"] = status
        if 400 <= status < 500 and status != 408:
            record["state"] = "rejected"
        elif 200 <= status < 300:
            if not isinstance(body, bytes) or len(body) > 65536:
                raise ValueError("Invalid response")
            result = json.loads(body)
            version = result.get("versionNumber") if isinstance(result, dict) else None
            if type(version) is not int or version <= 0:
                raise ValueError("Missing publish version")
            record.update(state="uploaded", version_number=version)
        else:
            record["state"] = "submission_uncertain"
    except Exception:
        record["state"] = "submission_uncertain"
    replace_record(job_path, record)
    return record


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_key_transport(key, *, timeout=30):
    """Authorized caller injects a key in memory. No discovery, log or retry."""
    if not isinstance(key, str) or not key or "\r" in key or "\n" in key:
        raise ValueError("Configure the Roblox credential outside the conversation")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    def send(plan, data):
        suffix = ".rbxlx" if plan.get("content_type") == "application/xml" else ".rbxl"
        if plan != publish_plan(data, suffix, plan.get("universe_id"), plan.get("place_id")):
            raise ValueError("Only a canonical Roblox upload plan is allowed")
        req = Request(plan["url"], data=data, method="POST", headers={
            "x-api-key": key, "Content-Type": plan["content_type"]})
        try:
            with opener.open(req, timeout=timeout) as response:
                return response.status, response.read(65537)
        except HTTPError as exc:
            with exc:
                return exc.code, b""  # Never expose remote error bodies.
    return send


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect-place")
    inspect.add_argument("--place", type=Path, required=True)
    inspect.add_argument("--output", type=Path)
    publish = commands.add_parser("publish-place")
    publish.add_argument("--place", type=Path, required=True)
    publish.add_argument("--universe-id", required=True)
    publish.add_argument("--place-id", required=True)
    publish.add_argument("--job", type=Path)
    publish.add_argument("--execute", action="store_true", help="Default is offline dry-run")
    publish.add_argument("--authorized", action="store_true", help="Records existing user authorization")
    publish.add_argument("--studio-reviewed", action="store_true", help="Only after actual Studio acceptance")
    args = parser.parse_args(argv)
    try:
        # Bound input before reading; never read configuration or credential files.
        if not args.place.is_file() or args.place.stat().st_size > MAX_PLACE_BYTES:
            raise ValueError("Missing or over-budget place")
        data = args.place.read_bytes()
        if args.command == "inspect-place":
            result = inspect_place(data)
            if args.output:
                save_new_json(args.output, result)
            code = 1 if result["invalid_local_content"] or result["duplicate_referents"] else 0
        else:
            plan = publish_plan(data, args.place.suffix, args.universe_id, args.place_id)
            if not args.execute:
                result, code = plan, 0
            else:
                if not args.job or not args.authorized or not args.studio_reviewed:
                    raise ValueError("Need --job, --authorized and --studio-reviewed")
                def send(planned, body):
                    # Executed only after a new intent has been written.
                    return api_key_transport(os.environ.get("ROBLOX_API_KEY"))(planned, body)
                result = upload_once(plan, data, args.job, send,
                                     authorized=True, studio_reviewed=True)
                code = 0 if result["state"] == "uploaded" else 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (ValueError, OSError, UnicodeError, ET.ParseError, TypeError):
        print(json.dumps({"error": "Input, path or record invalid; inspect the local files and contract. No automatic retry."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
