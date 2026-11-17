"""Shared constants, data classes and the router's error type."""

from __future__ import annotations

from dataclasses import dataclass


TOOLS = ("claude", "codex", "copilot", "agy")


# Tools that serve models from several families, so the active family cannot be
# inferred from the CLI name alone.
BROKER_TOOLS = ("copilot",)


FAMILIES = ("anthropic", "openai", "google", "unknown")


DIRECT_TOOL_FAMILY = {
    "claude": "anthropic",
    "codex": "openai",
    "agy": "google",
}


CALLER_DEFAULT_FAMILY = {
    "claude": "anthropic",
    "codex": "openai",
    "agy": "google",
    "copilot": "unknown",
}


COMPLEMENTARY_FAMILIES = {
    "anthropic": ("openai", "google"),
    "openai": ("anthropic", "google"),
    "google": ("anthropic", "openai"),
    "unknown": ("anthropic", "openai", "google"),
}


DIRECT_TOOL_BY_FAMILY = {
    "anthropic": "claude",
    "openai": "codex",
    "google": "agy",
}


MAX_INPUT_BYTES = 500_000


DEFAULT_TIMEOUT_SECONDS = 180


class RubberDuckError(RuntimeError):
    """Raised when a review request cannot be prepared or executed.

    Attributes:
        model: The model identifier being attempted when the error occurred,
            or ``None`` when the failure happened before any model was chosen
            (the tool was missing, unauthenticated, or had no configured
            model). Carrying this on the exception means the caller reports
            the model that actually failed instead of guessing from the
            candidate's model list, which is wrong whenever the route is
            abandoned before exhausting every model.
    """

    def __init__(self, message: str, *, model: str | None = None) -> None:
        super().__init__(message)
        self.model = model


@dataclass(frozen=True)
class ModelChoice:
    """Pair a model identifier with the reasoning effort it supports.

    A ``model`` of ``None`` means "omit the model flag and let the CLI pick its
    own default", which keeps self-refreshing CLIs such as Codex current without
    any catalog maintenance. An ``effort`` of ``None`` means the model exposes no
    effort control, so no effort argument is passed at all.
    """

    model: str | None
    effort: str | None = None


@dataclass(frozen=True)
class Candidate:
    """Describe one concrete reviewer route and its ordered model fallbacks."""

    tool: str
    family: str
    model: str | None
    tier: str
    independence: str
    models: tuple[ModelChoice, ...] = ()
    effort: str | None = None


@dataclass(frozen=True)
class Attempt:
    """Record one failed reviewer attempt without sensitive process details."""

    reviewer: str
    model: str | None
    error: str
    reason: str = "error"
    stepped_down: bool = False


@dataclass(frozen=True)
class ReviewResult:
    """Represent a successful independent critique."""

    reviewer: str
    family: str
    model: str | None
    tier: str
    independence: str
    review: str
    effort: str | None = None


@dataclass(frozen=True)
class ReviewRequest:
    """Capture normalized inputs for one routed review."""

    caller: str
    caller_family: str
    kind: str
    tier: str
    reviewer: str
    timeout_seconds: int
