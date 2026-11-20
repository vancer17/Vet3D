"""MDF3 contract: input_file: BinaryFile, options: dict -> output_file: BinaryFile."""
import argparse
import os
from pathlib import Path
import tempfile
import time
import traceback
import uuid

from mdf3 import AlgoWorker, BinaryFile, KeywordRule, ServiceBase
from algorithm import Session
from API import infer
from config_check import check_config


def validate_request(data, session, max_bytes):
    if not isinstance(data, dict):
        raise ValueError("input_data must be a dict")
    file = data.get("input_file")
    if not isinstance(file, BinaryFile) or file.field_name != "input_file":
        raise ValueError("input_file must be BinaryFile(field_name='input_file')")
    name = file.file_name
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name or Path(name).name != name:
        raise ValueError("input_file.file_name must be a safe basename")
    if Path(name).suffix.lower() not in session.input_suffixes:
        raise ValueError("Unsupported input suffix")
    if not isinstance(file.content, bytes) or not 0 < len(file.content) <= max_bytes:
        raise ValueError("input_file.content is empty or exceeds the byte limit")
    return file, session.validate_options(data.get("options", {}))


class ServiceWorker(AlgoWorker):
    def init(self, worker_id):
        self.worker_id = worker_id
        self.max_bytes = int(os.getenv("MAX_INPUT_BYTES", str(256 * 1024 * 1024)))
        if self.max_bytes <= 0:
            raise ValueError("MAX_INPUT_BYTES must be positive")
        self.session = Session(os.getenv("MODEL_DIR", "/models"), os.getenv("DEVICE", "cpu"))
        self.session_id = uuid.uuid4().hex
        self.requests_completed = 0
        print(f"resident_session_ready worker={worker_id} pid={os.getpid()} profile={self.session.profile}", flush=True)

    def process(self, input_data, trace_id):
        started = time.monotonic()
        try:
            file, options = validate_request(input_data, self.session, self.max_bytes)
            with tempfile.TemporaryDirectory(prefix="mdf-request-") as directory:
                source = Path(directory) / ("input" + Path(file.file_name).suffix.lower())
                output = Path(directory) / ("result" + self.session.output_suffix)
                source.write_bytes(file.content)
                details = infer(self.session, source, output, options)
                binary = BinaryFile(field_name="output_file", file_name=output.name, content=output.read_bytes())
            self.requests_completed += 1
            return dict(success=True, status="success", trace_id=trace_id, output_file=binary,
                        metadata=dict(worker_id=self.worker_id, worker_pid=os.getpid(),
                                      session_id=self.session_id, algorithm_profile=self.session.profile,
                                      requests_completed=self.requests_completed,
                                      elapsed_seconds=time.monotonic() - started, output=details))
        except Exception as exc:
            traceback.print_exc()
            return dict(success=False, status="failed", trace_id=trace_id,
                        error_type=type(exc).__name__, error_message=str(exc))

    def shutdown(self):
        session = getattr(self, "session", None)
        if session is not None:
            self.session = None
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--env", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--tcp-port", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--task-timeout", type=float, default=1800)
    args = parser.parse_args()
    if not 1 <= args.tcp_port <= 65535 or args.workers != 1 or not 0 < args.task_timeout < float("inf"):
        parser.error("Starter requires one worker, a valid TCP port and a finite positive timeout")
    check_config(args.config)
    ServiceBase(
        service_name=args.service_name, algo_cls=ServiceWorker, num_workers=args.workers,
        num_pullers=args.workers, config_path=args.config, environment=args.env, group_name=args.group,
        tcp_port=args.tcp_port, worker_pool_wait_ready=True, worker_pool_ready_timeout_sec=600,
        worker_task_timeout_sec=args.task_timeout, worker_timeout_action="kill",
        failure_dump_enabled=False, failure_feishu_enabled=False, tmp_cleanup_enabled=False,
        keyword_rules=[KeywordRule(pattern=r"CUDA error:.*illegal memory access|device-side assert triggered|uncorrectable ECC",
                                   action="kill", description="Unrecoverable CUDA context; restart container")],
    ).run()


if __name__ == "__main__":
    main()
