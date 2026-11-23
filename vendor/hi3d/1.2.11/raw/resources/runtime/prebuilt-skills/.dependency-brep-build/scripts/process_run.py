"""Run one explicit local child with bounded cleanup on interruption."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess
import signal
import time


STALL_MIN_CYCLES = 2
STALL_ELAPSED_RATIO = 0.4
EXHAUSTING_RATIO = 0.8
EXHAUSTING_PHASES = frozenset({'start', 'wait'})
HEARTBEAT_SCHEMA = 'run-tools.budget.v1'


class BudgetTimeout(RuntimeError):
    """The wall-clock budget elapsed; the child was terminated. Do not retry or extend here."""

    def __init__(self, elapsed_s, budget_s):
        super().__init__(f'budget exceeded: {elapsed_s:.1f}s / {budget_s}s')
        self.elapsed_s = elapsed_s
        self.budget_s = budget_s


def utc_stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_heartbeat(path):
    """Read a heartbeat JSON object or return None if missing/invalid JSON."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _phase_cycles(previous, phase, status):
    if (
        isinstance(previous, dict)
        and previous.get('status') == 'running'
        and status == 'running'
        and previous.get('phase') == phase
    ):
        try:
            return int(previous.get('phase_unchanged_cycles') or 1) + 1
        except (TypeError, ValueError):
            return 2
    return 1


def write_heartbeat(path, **fields):
    """Replace heartbeat JSON. Callers create the parent directory. No retry.

    If phase_unchanged_cycles is omitted, it is derived from the previous file.
    """
    path = Path(path)
    payload = {'schema': HEARTBEAT_SCHEMA}
    payload.update(fields)
    if 'phase_unchanged_cycles' not in payload and 'phase' in payload and 'status' in payload:
        payload['phase_unchanged_cycles'] = _phase_cycles(load_heartbeat(path), payload['phase'], payload['status'])
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
    return payload


def popup_reason(record, *, asked=()):
    """Return a heartbeat popup reason or None. Does not start, kill, or extend.

    Reasons: timeout, stall, exhausting. `asked` suppresses repeats at the caller checkpoint.
    """
    if not isinstance(record, dict) or record.get('schema') != HEARTBEAT_SCHEMA:
        raise ValueError('heartbeat schema must be ' + HEARTBEAT_SCHEMA)
    asked = set(asked)
    status = record.get('status')
    reason = None
    if status == 'timeout':
        reason = 'timeout'
    elif status == 'running':
        try:
            elapsed = float(record['elapsed_s'])
            budget = float(record['budget_s'])
            cycles = int(record.get('phase_unchanged_cycles') or 1)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('heartbeat elapsed_s, budget_s and cycles must be numeric') from exc
        if budget <= 0:
            raise ValueError('budget_s must be positive')
        phase = record.get('phase')
        if elapsed >= EXHAUSTING_RATIO * budget and phase in EXHAUSTING_PHASES:
            reason = 'exhausting'
        elif cycles >= STALL_MIN_CYCLES and elapsed >= STALL_ELAPSED_RATIO * budget:
            reason = 'stall'
    if reason in asked:
        return None
    return reason


def run_process(command, log, *, env=None, terminate_timeout=10, error_prefix="Stage exited"):
    """Capture combined output; terminate then kill/wait on any parent exception.

    Does not retry. Callers create log directories and choose environment policy.
    A child failure raises RuntimeError; interruption preserves the original error.
    """
    with Path(log).open("w") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, env=env)
        code = _wait(process, terminate_timeout)
    if code:
        raise RuntimeError(f"{error_prefix} {code}; see {log}")


def _stop(process, terminate_timeout, kill_tree=False):
    if kill_tree:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return process.wait()
        try:
            code = process.wait(timeout=terminate_timeout)
        except subprocess.TimeoutExpired:
            code = None
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.wait() if code is None else code
    if process.poll() is not None:
        return process.returncode
    process.terminate()
    try:
        return process.wait(timeout=terminate_timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait()


def _wait(process, terminate_timeout):
    try:
        return process.wait()
    except BaseException:
        _stop(process, terminate_timeout)
        raise


def run_budgeted(
    command,
    log,
    *,
    env=None,
    max_wall_seconds,
    heartbeat_path=None,
    heartbeat_seconds=5,
    terminate_timeout=10,
    error_prefix="Stage exited",
    clock=time.monotonic,
    kill_tree=False,
):
    """Run a child with a wall-clock budget and optional heartbeat JSON.

    On timeout the child is terminated then killed; raises BudgetTimeout.
    Does not extend the budget, retry, or start a second child.
    Heartbeat status is running / completed / failed / timeout.
    """
    if not isinstance(max_wall_seconds, (int, float)) or isinstance(max_wall_seconds, bool) or max_wall_seconds <= 0:
        raise ValueError('max_wall_seconds must be a positive number')
    if not isinstance(heartbeat_seconds, (int, float)) or isinstance(heartbeat_seconds, bool) or heartbeat_seconds <= 0:
        raise ValueError('heartbeat_seconds must be a positive number')
    if kill_tree and os.name != 'posix':
        raise ValueError('kill_tree requires a POSIX process group')
    started = clock()
    deadline = started + float(max_wall_seconds)
    log = Path(log)
    heartbeat = Path(heartbeat_path) if heartbeat_path is not None else None

    def beat(status, phase):
        if heartbeat is None:
            return
        write_heartbeat(
            heartbeat,
            status=status,
            phase=phase,
            elapsed_s=round(clock() - started, 3),
            budget_s=float(max_wall_seconds),
            heartbeat_s=float(heartbeat_seconds),
            last_heartbeat=utc_stamp(),
        )

    with log.open("w") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, env=env, start_new_session=kill_tree)
        beat('running', 'start')
        try:
            while True:
                remaining = deadline - clock()
                if remaining <= 0:
                    _stop(process, terminate_timeout, kill_tree)
                    beat('timeout', 'killed')
                    raise BudgetTimeout(clock() - started, float(max_wall_seconds))
                wait_for = min(float(heartbeat_seconds), remaining)
                try:
                    code = process.wait(timeout=wait_for)
                except subprocess.TimeoutExpired:
                    beat('running', 'wait')
                    continue
                if code:
                    beat('failed', 'exit')
                    raise RuntimeError(f"{error_prefix} {code}; see {log}")
                beat('completed', 'exit')
                return None
        except BudgetTimeout:
            raise
        except BaseException:
            _stop(process, terminate_timeout, kill_tree)
            raise


def run_checked(command, *, env=None, terminate_timeout=10):
    """Inherit stdio, run once and preserve CalledProcessError on child failure."""
    code = _wait(subprocess.Popen(command, env=env), terminate_timeout)
    if code:raise subprocess.CalledProcessError(code, command)


def child_environment(*, inherit=(), overrides=None):
    """Copy only explicitly named environment keys, then apply caller values."""
    result = {key: os.environ[key] for key in inherit if key in os.environ}
    result.update(overrides or {})
    return result
