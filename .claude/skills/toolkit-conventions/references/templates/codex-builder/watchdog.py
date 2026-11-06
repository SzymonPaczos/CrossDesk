#!/usr/bin/env python3
"""Bound a POSIX command and its process group; this is not an OS sandbox."""
import os
import signal
import subprocess
import threading
import time


class Cancelled(BaseException):
    """The supervising process received a termination request."""


def _stop_group(process, grace):
    """Stop children even if their group leader has already exited."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return
    # killpg(..., 0) is not necessary and is denied by some host sandboxes.
    # Give all children the same grace, then kill the group even if its
    # original leader already exited. A zombie does not keep doing work.
    time.sleep(grace)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_process(argv, *, cwd, timeout, stdin=None, stdout=None, stderr=None,
                env=None, grace=1.0):
    """Run argv without a shell and return exit_code/timed_out/cancelled/duration_seconds.

    stdin/stdout/stderr accept subprocess-compatible file objects or descriptors.
    No output is captured in memory. SIGTERM is handled only on the main thread;
    callers using threads must forward cancellation through their own supervisor.
    Children which deliberately escape the process group require an OS sandbox.
    """
    if (not isinstance(argv, (list, tuple)) or not argv
            or any(not isinstance(part, str) or not part for part in argv)):
        raise ValueError("argv must be a nonempty list of strings")
    if not 0 < timeout < float("inf") or not 0 <= grace < float("inf"):
        raise ValueError("timeout must be finite and positive; grace finite and nonnegative")
    started = time.monotonic()
    process = subprocess.Popen(argv, cwd=cwd, stdin=stdin, stdout=stdout,
                               stderr=stderr, env=env, start_new_session=True)
    timed_out = cancelled = False
    code = 125
    cleanup_error = None
    previous = None
    handles_term = threading.current_thread() is threading.main_thread()
    if handles_term:
        previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(Cancelled()))
    try:
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            code = 124
        except (KeyboardInterrupt, Cancelled):
            cancelled = True
            code = 130
    finally:
        previous_int = None
        if handles_term:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            previous_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            try:
                _stop_group(process, grace)
            except OSError as exc:
                cleanup_error = type(exc).__name__
                process.poll()
                if process.returncode is None:
                    try:
                        process.kill()
                        process.wait(timeout=1)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                if code == 0:
                    code = 125
        finally:
            if handles_term:
                signal.signal(signal.SIGTERM, previous)
                signal.signal(signal.SIGINT, previous_int)
    return {"exit_code": code if code >= 0 else 128 - code,
            "timed_out": timed_out, "cancelled": cancelled,
            "cleanup_complete": cleanup_error is None,
            "cleanup_error": cleanup_error,
            "duration_seconds": round(time.monotonic() - started, 3)}
