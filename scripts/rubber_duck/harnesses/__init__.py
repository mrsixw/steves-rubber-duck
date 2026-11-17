"""Reviewer CLIs: one module per harness, plus the authentication preflight.

Each harness module provides ``build_command``, which turns one model choice
into the CLI's tool-less headless command, and may provide ``preflight``, which
checks authentication cheaply before a model call.
"""

from __future__ import annotations

from types import ModuleType

from rubber_duck.common import Candidate, RubberDuckError
from rubber_duck.harnesses import agy, claude, codex, copilot

HARNESSES: dict[str, ModuleType] = {"claude": claude, "codex": codex, "copilot": copilot, "agy": agy}


def harness_for(tool: str, model: str | None = None) -> ModuleType:
    """Return the harness module for a reviewer CLI.

    Args:
        tool: Reviewer CLI name.
        model: Model being attempted, carried on the error for attribution.

    Raises:
        RubberDuckError: If the tool has no harness.
    """

    harness = HARNESSES.get(tool)
    if harness is None:
        raise RubberDuckError(f"Unsupported reviewer: {tool}", model=model)
    return harness


def preflight(candidate: Candidate, executable: str, timeout_seconds: int) -> None:
    """Verify stable authentication signals before a model call.

    Args:
        candidate: Candidate reviewer.
        executable: Resolved executable path.
        timeout_seconds: Overall timeout used to bound preflight checks.

    Raises:
        RubberDuckError: If a supported authentication check fails.
    """

    check = getattr(HARNESSES.get(candidate.tool), "preflight", None)
    if check is not None:
        check(executable, min(timeout_seconds, 15))
