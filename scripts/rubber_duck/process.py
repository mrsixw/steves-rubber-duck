"""Bounded child processes and process-group cleanup on timeout."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from collections import deque
from pathlib import Path


def run_process(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one bounded child process with the recursion marker set.

    Args:
        command: Executable and arguments.
        cwd: Isolated working directory.
        timeout_seconds: Process timeout.
        input_text: Optional standard input.

    Returns:
        Completed process result.
    """

    environment = os.environ.copy()
    environment["RUBBER_DUCK_CHILD"] = "1"
    with (
        tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stdout_file,
        tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr_file,
    ):
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=os.name != "nt",
        )
        try:
            process.communicate(input=input_text, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            terminate_process_group(process)
            raise
        stdout_file.seek(0)
        stderr_file.seek(0)
        return subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout_file.read(),
            stderr_file.read(),
        )


def terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate a timed-out reviewer and any children holding output pipes.

    Args:
        process: Reviewer process started in its own POSIX session when
            supported.
    """

    descendants = descendant_pids(process.pid) if os.name != "nt" else []
    if os.name == "nt":
        process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for pid in reversed(descendants):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    if os.name != "nt":
        for pid in reversed(descendants):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    if process.poll() is None:
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def descendant_pids(parent_pid: int) -> list[int]:
    """Return POSIX descendant process IDs for best-effort timeout cleanup.

    Args:
        parent_pid: Root reviewer process ID.

    Returns:
        Descendant process IDs ordered from parent generation to leaves.
    """

    try:
        result = subprocess.run(
            ["/bin/ps", "-Ao", "pid=,ppid="],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []

    children: dict[int, list[int]] = {}
    for line in result.stdout.splitlines():
        try:
            pid_text, ppid_text = line.split()
            pid, ppid = int(pid_text), int(ppid_text)
        except (ValueError, TypeError):
            continue
        children.setdefault(ppid, []).append(pid)

    descendants: list[int] = []
    pending = deque(children.get(parent_pid, []))
    while pending:
        pid = pending.popleft()
        descendants.append(pid)
        pending.extend(children.get(pid, []))
    return descendants
