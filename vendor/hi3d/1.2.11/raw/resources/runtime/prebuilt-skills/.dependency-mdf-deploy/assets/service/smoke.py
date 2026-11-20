"""Deployment-only SDK round trip. No private wire protocol or generic gateway client."""
import argparse
import json
from pathlib import Path
import uuid

from mdf3 import BinaryFile, ServiceInvokeSession
from config_check import check_config


def save_record(path, record):
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
    temporary.replace(path)


def require_result(result):
    if not isinstance(result, dict) or result.get("success") is not True or result.get("status") != "success":
        raise RuntimeError("MDF3 returned a business failure; inspect the service log using the saved trace")
    file = result.get("output_file")
    if not isinstance(file, BinaryFile) or file.field_name != "output_file" or not file.content:
        raise ValueError("Missing output_file BinaryFile")
    name = file.file_name
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name or Path(name).name != name:
        raise ValueError("Unsafe output filename")
    return file


def invoke_checks(client, service_name, source, options, run_dir, timeout, repeat=2):
    """Save each ID before submission; never retry ambiguous tasks or overwrite a run."""
    if repeat < 2 or not 0 < timeout < float("inf"):
        raise ValueError("Need repeat >= 2 and a finite positive timeout")
    source, run_dir = Path(source).resolve(), Path(run_dir)
    content = source.read_bytes()
    if not content or not isinstance(options, dict):
        raise ValueError("Need a nonempty input file and a dict of options")
    request = dict(input_file=BinaryFile(field_name="input_file", file_name=source.name, content=content), options=options)
    run_dir.mkdir(parents=True, exist_ok=False)
    identities = []
    for index in range(repeat + 1):
        # Put the negative case between valid calls to prove the worker recovers.
        invalid = index == 1
        trace_id = "mdf-deploy-" + uuid.uuid4().hex
        record_path = run_dir / f"call-{index + 1}.json"
        record = dict(trace_id=trace_id, state="SUBMITTING", kind="invalid" if invalid else "valid")
        save_record(record_path, record)
        try:
            result = client.invoke(service_name, {} if invalid else request, trace_id=trace_id, timeout=timeout)
        except Exception:
            record["state"] = "AMBIGUOUS"
            save_record(record_path, record)
            raise RuntimeError("Call interrupted; keep this run and investigate its saved trace without resubmitting") from None
        # Persist arrival before validating: a malformed result is not an unknown submission.
        record["state"] = "RECEIVED"
        save_record(record_path, record)
        if invalid:
            if not isinstance(result, dict) or result.get("success") is not False or result.get("status") != "failed" or "output_file" in result:
                raise ValueError("Invalid-input contract failed")
            if not isinstance(result.get("error_type"), str) or not isinstance(result.get("error_message"), str):
                raise ValueError("Failure is missing structured error fields")
            record["state"] = "EXPECTED_FAILURE"
        else:
            file = require_result(result)
            metadata = result.get("metadata", {})
            identity = (metadata.get("worker_pid"), metadata.get("session_id"))
            if not all(identity) or (identities and identity != identities[0]):
                raise ValueError("Worker/session changed between requests; investigate model reloads")
            identities.append(identity)
            target = run_dir / (f"output-{index + 1}" + Path(file.file_name).suffix)
            target.write_bytes(file.content)
            record.update(state="TRANSPORT_VALIDATED", output=target.name,
                          worker_pid=identity[0], session_id=identity[1],
                          algorithm_profile=metadata.get("algorithm_profile"),
                          elapsed_seconds=metadata.get("elapsed_seconds"))
        save_record(record_path, record)
    return run_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--options", default="{}")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--repeat", type=int, default=2)
    args = parser.parse_args()
    check_config(args.config)
    with ServiceInvokeSession(environment=args.env, config_path=args.config,
                              caller_service_name="mdf-deploy-check") as client:
        output = invoke_checks(client, args.service_name, args.input, json.loads(args.options),
                               args.run_dir, args.timeout, args.repeat)
    print(f"Queue/TCP and failure contract verified in {output}; independently decode outputs before accepting the algorithm")


if __name__ == "__main__":
    main()
