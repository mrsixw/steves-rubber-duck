"""Codex as a reviewer: read-only sandbox with every tool feature disabled."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from rubber_duck import process
from rubber_duck.catalog import effort_args
from rubber_duck.common import Candidate, ModelChoice, RubberDuckError


# Codex has no "no tools" switch, and its read-only sandbox still lets the
# reviewer run commands that read anywhere on disk. Every tool feature the
# installed CLI lists is disabled; unknown names are omitted because Codex
# rejects them, and a CLI whose shell_tool cannot be disabled is skipped.
CODEX_TOOL_FEATURES = (
    "shell_tool", "unified_exec", "browser_use", "browser_use_external",
    "browser_use_full_cdp_access", "computer_use", "apps", "plugins", "remote_plugin",
    "multi_agent", "image_generation", "in_app_browser", "in_app_local_automation",
    "skill_search", "skill_mcp_dependency_install", "view_image", "tool_suggest",
    "workspace_dependencies", "worktrees", "goals", "hooks",
)


def codex_disable_args(executable: str, workdir: Path, timeout_seconds: int) -> list[str]:
    """Return ``--disable`` flags for every Codex tool feature this CLI knows.

    Args:
        executable: Resolved Codex path.
        workdir: Isolated working directory.
        timeout_seconds: Bound for the feature listing.

    Returns:
        Arguments disabling each known tool feature.

    Raises:
        RubberDuckError: If the features cannot be listed or ``shell_tool`` is
            not among them, so the reviewer's tools cannot be switched off.
    """

    try:
        listing = process.run_process(
            [executable, "features", "list"], cwd=workdir, timeout_seconds=min(timeout_seconds, 15)
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RubberDuckError(f"codex features could not be listed: {exc}") from exc
    known = {line.split()[0] for line in listing.stdout.splitlines() if line.strip()}
    if listing.returncode != 0 or "shell_tool" not in known:
        raise RubberDuckError("codex tools cannot be disabled on this CLI version")
    args: list[str] = []
    for feature in CODEX_TOOL_FEATURES:
        if feature in known:
            args.extend(["--disable", feature])
    return args


def preflight(executable: str, timeout: int) -> None:
    """Fail unless ``codex login status`` succeeds.

    Raises:
        RubberDuckError: If Codex is installed but not authenticated.
    """

    result = process.run_process(
        [executable, "login", "status"],
        cwd=Path(tempfile.gettempdir()),
        timeout_seconds=timeout,
    )
    if result.returncode != 0:
        raise RubberDuckError("Codex is installed but not authenticated")


def build_command(
    executable: str,
    candidate: Candidate,
    model: ModelChoice,
    prompt: str,
    workdir: Path,
    timeout_seconds: int,
) -> tuple[list[str], str | None, str | None]:
    """Build a read-only Codex review command with its tools disabled.

    Returns:
        The command, the text to send on standard input, and the effort used.

    Raises:
        RubberDuckError: If this Codex cannot disable its tools.
    """

    effort = model.effort or candidate.tier
    command = [
        executable,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(workdir),
    ]
    command.extend(codex_disable_args(executable, workdir, timeout_seconds))
    command.extend(effort_args("codex", effort))
    if model.model:
        command.extend(["-m", model.model])
    command.append("-")
    return command, prompt, effort
