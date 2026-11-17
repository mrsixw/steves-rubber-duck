"""GitHub Copilot CLI as a reviewer, and as a broker for other families' models."""

from __future__ import annotations

from pathlib import Path

from rubber_duck.catalog import effort_args
from rubber_duck.common import Candidate, ModelChoice


def build_command(
    executable: str,
    candidate: Candidate,
    model: ModelChoice,
    prompt: str,
    workdir: Path,
    timeout_seconds: int,
) -> tuple[list[str], str | None, str | None]:
    """Build a Copilot review command with an empty tool set.

    Returns:
        The command, no standard input (the prompt is an argument), and the
        effort used.
    """

    # Only send an effort the catalog vouches for. Copilot rejects the
    # flag outright on models that do not support it, including the
    # "auto" selection some plans are limited to, so a tier fallback
    # here fails the whole route.
    effort = model.effort
    # No --agent: Copilot CLI 1.0.112 fails every prompt run under the
    # built-in rubber-duck agent with "Selected custom agent system
    # prompt callback is unavailable". The prompt carries the persona.
    command = [
        executable,
        "-p",
        prompt,
        "--silent",
        "--no-custom-instructions",
        "--disable-builtin-mcps",
        "--available-tools=",
        # Non-interactive Copilot requires permission for its available
        # tools; the empty available set leaves nothing to authorize.
        "--allow-all-tools",
        "--no-ask-user",
        # --no-remote was removed in Copilot CLI 1.0.112, which now
        # rejects the whole call when it is passed.
        "--no-auto-update",
        "--stream",
        "off",
        "--output-format",
        "text",
    ]
    command.extend(effort_args("copilot", effort))
    if model.model:
        command.extend(["--model", model.model])
    return command, None, effort
