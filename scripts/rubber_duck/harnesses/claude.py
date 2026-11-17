"""Claude Code as a reviewer: tool-less, plan-mode headless runs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from rubber_duck import process
from rubber_duck.catalog import effort_args
from rubber_duck.common import Candidate, ModelChoice, RubberDuckError


def preflight(executable: str, timeout: int) -> None:
    """Fail unless ``claude auth status`` reports a signed-in user.

    Raises:
        RubberDuckError: If Claude is installed but not authenticated.
    """

    result = process.run_process(
        [executable, "auth", "status", "--json"],
        cwd=Path(tempfile.gettempdir()),
        timeout_seconds=timeout,
    )
    try:
        logged_in = json.loads(result.stdout).get("loggedIn") is True
    except json.JSONDecodeError:
        logged_in = False
    if result.returncode != 0 or not logged_in:
        raise RubberDuckError("Claude is installed but not authenticated")


def build_command(
    executable: str,
    candidate: Candidate,
    model: ModelChoice,
    prompt: str,
    workdir: Path,
    timeout_seconds: int,
) -> tuple[list[str], str | None, str | None]:
    """Build a tool-less Claude review command.

    Returns:
        The command, the text to send on standard input, and the effort used.
    """

    command = [
        executable,
        "-p",
        "--permission-mode",
        "plan",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--tools",
        "",
        "--output-format",
        "text",
    ]
    if model.model:
        command.extend(["--model", model.model])
    command.extend(effort_args("claude", model.effort))
    return command, prompt, model.effort
