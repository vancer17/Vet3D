"""Taubin artifact handoff for a host-owned session; no Agent loop or Blender IO."""
from copy import deepcopy
import json
from pathlib import Path

from architecture_ir import compose_board, locate_board
from checkpoints import digest
from path_safety import validate_write_roots
from pcg_yaml import load as load_yaml
from session_schema import apply_tool_result, validate_session
from timing import write_json
from tool_result import tool_result
from view_ir import compose_view


def result_from_report(report_path):
    """Read a completed numerical report and verify its current BLEND hash.

    Reuses existing files for review_only; never smooths, writes, or certifies
    visual quality. A report is trusted local run evidence, not a signed proof.
    """
    path = Path(report_path).resolve()
    report = json.loads(path.read_text(encoding="utf-8"))
    if (report.get("schema") != "taubin-smooth.v1"
            or report.get("saved_mesh_readback") is not True
            or report.get("source_unchanged") is not True
            or not report.get("objects")
            or any(item.get("topology_unchanged") is not True for item in report["objects"])):
        raise ValueError("Expected a successful taubin-smooth numerical report")
    mesh = Path(report["output"]).resolve()
    if mesh != path.parent / "smoothed.blend" or not mesh.is_file():
        raise ValueError("Report must identify the adjacent smoothed.blend")
    if digest(mesh) != report.get("output_sha256"):
        raise ValueError("Saved BLEND is no longer the reported revision")
    return tool_result(
        status="ok", summary="数值与保存重开检查通过；待核对轮廓、边界和细节。",
        artifacts=[
            {"task": "smooth", "output": "mesh", "path": str(mesh),
             "href": str(mesh), "hash": report["output_sha256"], "tool": "taubin-smooth"},
            {"task": "smooth", "output": "report", "path": str(path),
             "href": str(path), "hash": digest(path), "tool": "taubin-smooth"},
        ],
        next_checkpoint="review", irreversible=["blender.write"],
    )


def bind_report(session, report_path, *, task_root):
    """Return a session copy binding this revision once; preserve older traces.

    The host owns route, authorization, status and checkpoint transitions. Same
    path/hash replay is a no-op, including for a completed review session.
    """
    validate_session(session)
    if session["entry"] != "taubin-smooth":
        raise ValueError("Use the existing taubin-smooth task session")
    result = result_from_report(report_path)
    root = Path(task_root).resolve()
    for item in result["artifacts"]:
        if root not in Path(item["path"]).parents:
            raise ValueError("Artifacts must be inside the task root")
    updated = deepcopy(session)
    changed = []
    for item in result["artifacts"]:
        current = next((old for old in updated["artifacts"]
                        if (old.get("task"), old.get("output")) == (item["task"], item["output"])), None)
        if current is None or current.get("purged") or any(
                current.get(key) != item[key] for key in ("path", "href", "hash")):
            changed.append(item)
    apply_tool_result(updated, dict(result, artifacts=changed))
    if changed:
        updated.update(checkpoint="review", status="running")
    return updated


def project_session(session, *, task_root):
    """Rebuild both projections from the persisted session, without append/write."""
    validate_session(session)
    if session["entry"] != "taubin-smooth":
        raise ValueError("Expected a taubin-smooth session")
    pcg = Path(__file__).resolve().parents[1] / "pcg"
    architecture = load_yaml((pcg / "architecture.yaml").read_text(encoding="utf-8"))
    routes = load_yaml((pcg / "routes.yaml").read_text(encoding="utf-8"))
    board = locate_board(compose_board(architecture, session), task_root)
    return board, compose_view(routes, session)


def write_state(session, *, task_root):
    """Persist one host-owned session, then replace disposable JSON projections.

    Single writer only. Call after each loop/option/rollback/compact, including
    loops with no new artifacts. Metadata is not appended as business output.
    """
    root = validate_write_roots(
        {"task": task_root}, package_root=Path(__file__).resolve().parents[1],
    )["task"]
    paths = [root / name for name in ("session.json", "board.json", "view.json")]
    if any(path.is_symlink() for path in paths):
        raise ValueError("Task metadata must not be symlinks")
    if paths[0].exists():
        previous = validate_session(json.loads(paths[0].read_text(encoding="utf-8")))
        if (previous["entry"], previous["task_id"]) != (session["entry"], session["task_id"]):
            raise ValueError("Do not replace a different task session")
    board, view = project_session(session, task_root=root)
    for path, document in zip(paths, (session, board, view)):
        write_json(path, document)
    return board, view
