"""AGY as a reviewer: whichever headless interface the installed CLI offers."""

from __future__ import annotations

import re
from pathlib import Path

from rubber_duck import process
from rubber_duck.catalog import effort_args
from rubber_duck.common import Candidate, ModelChoice, RubberDuckError


def build_agy_command(
    executable: str,
    candidate: Candidate,
    model: ModelChoice,
    review_file: Path,
    timeout_seconds: int,
) -> list[str]:
    """Build a command for an installed AGY headless interface.

    AGY encodes reasoning effort in the model identifier itself, for example
    ``gemini-3.1-pro-high``, so no separate effort argument is added here.

    Args:
        executable: Resolved AGY path.
        candidate: AGY reviewer candidate.
        model: Model choice being attempted.
        review_file: File containing the complete review prompt.
        timeout_seconds: Bound for help probes.

    Returns:
        Supported AGY headless command.

    Raises:
        RubberDuckError: If the installed AGY lacks a supported headless mode.
    """

    timeout = min(timeout_seconds, 15)
    top = process.run_process(
        [executable, "--help"],
        cwd=review_file.parent,
        timeout_seconds=timeout,
    )
    top_help = f"{top.stdout}\n{top.stderr}"
    prompt = "Read review-input.md and return only the requested critique. Do not modify files or invoke other agents."

    if advertises_subcommand(top_help, "run"):
        run_help_result = process.run_process(
            [executable, "run", "--help"],
            cwd=review_file.parent,
            timeout_seconds=timeout,
        )
        run_help = f"{run_help_result.stdout}\n{run_help_result.stderr}"
        if "--prompt" not in run_help:
            raise RubberDuckError("AGY run does not advertise --prompt", model=model.model)
        command = [executable, "run"]
        if model.model and "--model" in run_help:
            command.extend(["--model", model.model])
        command.extend(effort_args("agy", model.effort, run_help))
        if "--sandbox" in run_help:
            command.append("--sandbox=true")
        command.extend(["--prompt", prompt])
        return command

    if "--print" in top_help and ("--prompt" in top_help or "-p" in top_help):
        # --print <value> consumes the immediately following argument as the prompt.
        # --model must come BEFORE --print to avoid being swallowed as the prompt.
        # Embed review content directly rather than referencing a file, since
        # agy --print has no file-reading tools.
        review_content = review_file.read_text(encoding="utf-8")
        command = [executable]
        if model.model and "--model" in top_help:
            command.extend(["--model", model.model])
        command.extend(effort_args("agy", model.effort, top_help))
        if "--sandbox" in top_help:
            command.append("--sandbox")
        command.extend(["--print", review_content])
        return command

    raise RubberDuckError("AGY has no supported non-interactive interface", model=model.model)


def advertises_subcommand(help_text: str, name: str) -> bool:
    """Report whether help output lists a subcommand, not merely the word.

    Only the trailing subcommand listing is searched. Scanning the whole help
    text matches prose such as "Run a single prompt", which would send the
    router down a command path the CLI does not actually support.

    Args:
        help_text: Combined stdout and stderr from a help probe.
        name: Subcommand to look for.

    Returns:
        ``True`` when the subcommand appears in a subcommand listing.
    """

    match = re.search(r"^.*subcommands?:\s*$", help_text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return False
    section = help_text[match.end():]
    return re.search(rf"^\s+{re.escape(name)}\s+\S", section, re.MULTILINE) is not None


def build_command(
    executable: str,
    candidate: Candidate,
    model: ModelChoice,
    prompt: str,
    workdir: Path,
    timeout_seconds: int,
) -> tuple[list[str], str | None, str | None]:
    """Write the prompt to a private file and build AGY's headless command.

    Returns:
        The command, no standard input, and the effort used.
    """

    review_file = workdir / "review-input.md"
    review_file.write_text(prompt, encoding="utf-8")
    review_file.chmod(0o600)
    return build_agy_command(executable, candidate, model, review_file, timeout_seconds), None, model.effort
