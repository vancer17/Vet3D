"""Validate assembly view directions and delegate submission to an explicit Hi3D tool."""

import argparse
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from view_contract import audit_multipart, load_views


def load_tool(directory):
    """Load the separately supplied tool; never guess a sibling installation."""
    directory = Path(directory).resolve()
    scripts = directory / 'scripts'
    names = ('hi3d_parameters', 'hi3d_jobs', 'hi3d_client', 'hi3d_storage')
    if not (directory / 'SKILL.md').is_file() or any(not (scripts / (n+'.py')).is_file() for n in names):
        raise ValueError('Provide the complete independent hi3d-api tool directory')
    sys.path.insert(0, str(scripts))
    modules = {}
    for name in names:
        module = importlib.import_module(name)
        if Path(module.__file__).resolve().parent != scripts:
            raise ValueError('Conflicting Hi3D module; run this entry in a fresh process')
        modules[name.removeprefix('hi3d_')] = module
    return SimpleNamespace(**modules)


def reviewed_plan(tool, manifest, parameters):
    """Validate directions and the public tool's encoded request before authentication."""
    paths, bits, audit = load_views(Path(manifest))
    params = json.loads(Path(parameters).read_text())
    if params.pop('multi_images_bit', bits) != bits:
        raise ValueError('Parameter bitmap disagrees with reviewed views')
    slots = ','.join(v['api_slot'] for v in audit['views'])
    plan = tool.parameters.build_plan('model', images=[str(p) for p in paths], views=slots,
                                     overrides=[f'{k}={v}' for k,v in params.items()])
    with tool.parameters.multipart(plan['parameters'], plan['files']) as (stream, content_type, length):
        encoded = audit_multipart(stream.read(), content_type, plan['parameters'], audit)
    return plan, audit, encoded


class ReviewedClient:
    """Audit the exact outgoing image stream while reusing the tool's transport."""

    def __init__(self, client, tool, plan, audit, audit_path):
        self.client, self.tool, self.plan, self.audit = client, tool, plan, audit
        self.audit_path = audit_path

    def auth(self):
        """Delegate authentication without inspecting any credential or token."""
        return self.client.auth()

    def request(self, path, method, data, content_type, length):
        """Fail closed before forwarding a changed or reordered POST body."""
        if method != 'POST' or path != self.tool.client.CREATE['model']:
            raise ValueError('Only reviewed model submission is supported')
        position = data.tell()
        data.seek(0)
        encoded = audit_multipart(data.read(), content_type, self.plan['parameters'], self.audit)
        data.seek(position)
        self.tool.storage.save(self.audit_path, {'views': self.audit, 'multipart': encoded}, exclusive=True)
        return self.client.request(path, method, data, content_type, length)


def execute(tool, manifest, parameters, job, dry_run, client_factory=None):
    """Preserve public job recovery and block invalid views before creating a client."""
    plan, audit, encoded = reviewed_plan(tool, manifest, parameters)
    if dry_run:
        return {'dry_run': True, 'plan': plan, 'views': audit, 'multipart_preview': encoded}, 0
    client = (client_factory or tool.client.Client)()
    wrapper = ReviewedClient(client, tool, plan, audit, str(job)+'.views.json')
    result = tool.jobs.submit_job(wrapper, job, plan)
    return result, tool.jobs.job_outcome(result['job'])[1]


def reviewed_handoff(manifest, parameters, job, output_dir):
    """Return a local-only Runtime tool handoff after validating every view."""
    paths, bits, audit = load_views(Path(manifest))
    settings = json.loads(Path(parameters).read_text(encoding="utf-8"))
    if settings.pop("multi_images_bit", bits) != bits:
        raise ValueError("Parameter bitmap disagrees with reviewed views")
    arguments = {
        "action": "generate_3d",
        "kind": "model",
        "images": [str(path) for path in paths],
        "views": [entry["api_slot"] for entry in audit["views"]],
        "settings": settings,
        "jobPath": str(Path(job)),
        "outputDir": str(Path(output_dir)),
    }
    return {
        "runtimeTool": "hi3d_api",
        "dryRunFirst": True,
        "arguments": arguments,
        "views": audit,
        "note": (
            "Call Runtime hi3d_api with these arguments and dryRun=true. Pass "
            "consent.user_interaction to the host preference panel, merge answers into "
            "settings, then call again without dryRun. Do not invent another popup kind."
        ),
    }


def main():
    """Parse only business handoff arguments and report safe errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hi3d-tool-dir')
    parser.add_argument('--output-dir')
    parser.add_argument('--backend', choices=['public', 'runtime'], default='runtime' if (Path(__file__).resolve().parents[1]/'.runtime-profile.json').is_file() else 'public')
    parser.add_argument('--views-manifest', required=True)
    parser.add_argument('--params', default=str(Path(__file__).resolve().parents[1]/'assets/hi3d-quality-fourview.json'))
    parser.add_argument('--job', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        if args.backend == 'runtime':
            if not args.output_dir:
                raise ValueError('Runtime handoff requires --output-dir')
            print(json.dumps(reviewed_handoff(args.views_manifest, args.params, args.job, args.output_dir), ensure_ascii=False, indent=2))
            return 0
        if not args.hi3d_tool_dir:
            raise ValueError('Public mode requires --hi3d-tool-dir')
        tool = load_tool(args.hi3d_tool_dir)
        result, code = execute(tool, args.views_manifest, args.params, args.job, args.dry_run)
        print(json.dumps(tool.storage.public_record(result), ensure_ascii=False, indent=2))
    except Exception as error:
        print(json.dumps({'error_type':type(error).__name__, 'message':'Check reviewed inputs and the existing job; never retry an uncertain submission.'}))
        code = 2
    return code


if __name__ == '__main__':
    sys.exit(main())
