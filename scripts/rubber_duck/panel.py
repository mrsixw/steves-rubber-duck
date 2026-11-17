"""Multi-reviewer panels, one reviewer per model family, run in parallel."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from rubber_duck.common import (
    Attempt,
    CALLER_DEFAULT_FAMILY,
    COMPLEMENTARY_FAMILIES,
    Candidate,
    DIRECT_TOOL_BY_FAMILY,
    ReviewRequest,
    ReviewResult,
)
from rubber_duck.routing import build_route, resolve_tier, run_routes


def panel_slots(
    request: ReviewRequest,
    artifact: str,
    allowed_tools: tuple[str, ...] | None = None,
) -> list[tuple[str, list[Candidate]]]:
    """Build one reviewer slot per complementary model family.

    Each slot holds the routes able to serve its family, in failover order: the
    family's direct CLI, then Copilot brokering that family. Copilot's ``null``
    CLI-default entry is dropped because a broker left to choose its own model
    cannot prove which family answered, so it could never fill a slot that must
    be a distinct family.

    Args:
        request: Normalized review request.
        artifact: Review packet used to resolve adaptive tiering.
        allowed_tools: Optional allow-list of reviewer CLIs. Routes through any
            other tool are removed, keeping the remaining order.

    Returns:
        ``(family, routes)`` pairs in ``COMPLEMENTARY_FAMILIES`` order. A family
        with no usable route is omitted, so the slot count is what the panel can
        actually attempt.
    """

    tier = resolve_tier(request.tier, request.kind, artifact)
    slots: list[tuple[str, list[Candidate]]] = []
    for family in COMPLEMENTARY_FAMILIES[request.caller_family]:
        routes: list[Candidate] = []
        tool = DIRECT_TOOL_BY_FAMILY[family]
        if not (tool == request.caller and family == request.caller_family):
            routes.append(build_route(tool, family, tier, "cross-family"))
        broker = build_route("copilot", family, tier, "cross-family")
        named = tuple(choice for choice in broker.models if choice.model is not None)
        if named:
            routes.append(
                Candidate(
                    tool=broker.tool,
                    family=family,
                    model=named[0].model,
                    tier=tier,
                    independence=broker.independence,
                    models=named,
                    effort=named[0].effort,
                ),
            )
        if allowed_tools is not None:
            routes = [route for route in routes if route.tool in allowed_tools]
        if routes:
            slots.append((family, routes))
    return slots


@dataclass(frozen=True)
class SlotOutcome:
    """Record how one family's panel slot was, or was not, filled."""

    family: str
    result: ReviewResult | None
    attempts: tuple[Attempt, ...]


@dataclass(frozen=True)
class PanelResult:
    """Represent a multi-reviewer panel and any fresh-session fallback."""

    requested: int | str
    target: int
    outcomes: tuple[SlotOutcome, ...]
    fallback: ReviewResult | None
    fallback_attempts: tuple[Attempt, ...]

    @property
    def reviews(self) -> list[ReviewResult]:
        """Return the cross-family reviews that filled a slot, in slot order."""

        return [outcome.result for outcome in self.outcomes if outcome.result]

    @property
    def attempts(self) -> list[Attempt]:
        """Return every failed attempt across slots and the fallback."""

        flattened = [item for outcome in self.outcomes for item in outcome.attempts]
        return flattened + list(self.fallback_attempts)


def resolve_panel_size(requested: int | str, slot_count: int) -> int:
    """Return the effective panel size, capped at the available families."""

    if requested == "all":
        return slot_count
    return min(int(requested), slot_count)


def perform_panel(
    request: ReviewRequest,
    artifact: str,
    requested: int | str,
    allowed_tools: tuple[str, ...] | None = None,
) -> PanelResult:
    """Run several independent reviewers, one per distinct model family.

    The first ``target`` slots run in parallel. A slot whose routes all fail is
    replaced by the next unused slot, when one exists, in a second parallel
    wave. If no slot succeeds, a fresh session of the caller's own tool runs as
    a disclosed fallback that is never counted as a panel member.

    Args:
        request: Normalized request.
        artifact: Review packet.
        requested: Requested panel size, an integer or ``"all"``.
        allowed_tools: Optional allow-list of reviewer CLIs for panel slots. The
            fresh-session fallback is not a panel member and ignores it.

    Returns:
        Panel outcome with every slot that ran, in slot order.
    """

    slots = panel_slots(request, artifact, allowed_tools)
    target = resolve_panel_size(requested, len(slots))

    def run_slot(slot: tuple[str, list[Candidate]]) -> SlotOutcome:
        family, routes = slot
        result, attempts = run_routes(routes, request, artifact)
        if result and result.independence != "cross-family":
            attempts.append(Attempt(result.reviewer, result.model, "family could not be verified", "error"))
            result = None
        return SlotOutcome(family, result, tuple(attempts))

    outcomes: list[SlotOutcome] = []
    pending = slots[:target]
    spare = slots[target:]
    while pending:
        with ThreadPoolExecutor(max_workers=len(pending)) as pool:
            wave = list(pool.map(run_slot, pending))
        outcomes.extend(wave)
        missing = sum(1 for outcome in wave if outcome.result is None)
        pending, spare = spare[:missing], spare[missing:]

    fallback: ReviewResult | None = None
    fallback_attempts: list[Attempt] = []
    if not any(outcome.result for outcome in outcomes):
        self_family = request.caller_family
        if self_family == "unknown":
            self_family = CALLER_DEFAULT_FAMILY[request.caller]
        tier = resolve_tier(request.tier, request.kind, artifact)
        fallback, fallback_attempts = run_routes(
            [build_route(request.caller, self_family, tier, "fresh-session")], request, artifact
        )
    return PanelResult(requested, target, tuple(outcomes), fallback, tuple(fallback_attempts))
