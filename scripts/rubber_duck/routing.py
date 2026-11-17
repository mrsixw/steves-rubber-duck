"""Route selection, model step-down and single-reviewer execution."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from rubber_duck import process
from rubber_duck.catalog import configured_models
from rubber_duck.common import (
    Attempt,
    BROKER_TOOLS,
    CALLER_DEFAULT_FAMILY,
    COMPLEMENTARY_FAMILIES,
    Candidate,
    DIRECT_TOOL_BY_FAMILY,
    DIRECT_TOOL_FAMILY,
    ModelChoice,
    ReviewRequest,
    ReviewResult,
    RubberDuckError,
)
from rubber_duck.discovery import available_models
from rubber_duck.harnesses import harness_for, preflight
from rubber_duck.prompt import build_review_prompt


HIGH_RISK_RE = re.compile(
    r"\b(security|authentication|authorization|credential|production|prod|"
    r"infrastructure|terraform|migration|destructive|delete|data[ -]loss|"
    r"concurren|race[ -]condition|public[ -](api|interface)|schema|"
    r"multi[ -]service|architect|incident|permission|privilege)\b",
    re.IGNORECASE,
)


def resolve_tier(requested: str, kind: str, artifact: str) -> str:
    """Resolve ``auto`` to medium or high based on review risk.

    Args:
        requested: Requested tier.
        kind: Review kind, either plan or code.
        artifact: Review packet supplied by the primary agent.

    Returns:
        ``medium`` or ``high``.
    """

    if requested != "auto":
        return requested
    changed_files = artifact.count("diff --git ") if kind == "code" else 0
    if HIGH_RISK_RE.search(artifact) or changed_files >= 5:
        return "high"
    return "medium"


def build_route(tool: str, family: str, tier: str, independence: str) -> Candidate:
    """Build one candidate with its ordered model fallbacks resolved.

    Args:
        tool: Reviewer CLI name.
        family: Model family the route should serve.
        tier: Resolved capability tier.
        independence: Independence level claimed for a successful review.

    Returns:
        Candidate whose ``models`` is never empty.
    """

    models = configured_models(tool, family, tier)
    first = models[0] if models else ModelChoice(None, None)
    return Candidate(
        tool=tool,
        family=family,
        model=first.model,
        tier=tier,
        independence=independence,
        models=models or (first,),
        effort=first.effort,
    )


def candidate_routes(request: ReviewRequest, artifact: str) -> list[Candidate]:
    """Build ordered, de-duplicated reviewer routes for a request.

    Args:
        request: Normalized review request.
        artifact: Review packet used to resolve adaptive tiering.

    Returns:
        Reviewer candidates in failover order.
    """

    tier = resolve_tier(request.tier, request.kind, artifact)
    caller_family = request.caller_family
    complementary = COMPLEMENTARY_FAMILIES[caller_family]

    def route(tool: str, family: str, independence: str) -> Candidate:
        return build_route(tool, family, tier, independence)

    if request.reviewer != "auto":
        if request.reviewer == "copilot":
            family = complementary[0] if complementary else "unknown"
        else:
            family = DIRECT_TOOL_FAMILY.get(request.reviewer, caller_family)
        independence = "cross-family" if family != caller_family and caller_family != "unknown" else "fresh-session"
        return [route(request.reviewer, family, independence)]

    candidates: list[Candidate] = []
    for family in complementary:
        tool = DIRECT_TOOL_BY_FAMILY[family]
        if tool == request.caller and family == caller_family:
            continue
        candidates.append(route(tool, family, "cross-family"))

    broker_family = complementary[0]
    candidates.append(
        route(
            "copilot",
            broker_family,
            "cross-family" if caller_family != "unknown" else "fresh-session",
        ),
    )

    self_family = caller_family
    if self_family == "unknown":
        self_family = CALLER_DEFAULT_FAMILY[request.caller]
    candidates.append(route(request.caller, self_family, "fresh-session"))

    unique: list[Candidate] = []
    seen: set[tuple[str, tuple[ModelChoice, ...]]] = set()
    for candidate in candidates:
        key = (candidate.tool, candidate.models)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def execute_candidate(
    candidate: Candidate,
    *,
    kind: str,
    artifact: str,
    timeout_seconds: int,
    attempts: list[Attempt] | None = None,
) -> ReviewResult:
    """Execute one reviewer route, walking its model fallbacks in order.

    The tool is resolved and authenticated once, then each model is tried until
    one produces a critique. A model rejection or a plan entitlement limit
    advances to the next model; throttling, authentication, timeout, or
    transport failure abandons the tool immediately so the router moves on
    rather than repeating a failure that a different model cannot fix.

    Args:
        candidate: Candidate reviewer route.
        kind: Review kind.
        artifact: Review packet.
        timeout_seconds: Model-call timeout.
        attempts: Optional sink recording each rejected model.

    Returns:
        Successful review result.

    Raises:
        RubberDuckError: If the tool is unavailable, unauthenticated, or every
            model is rejected.
    """

    executable = shutil.which(candidate.tool)
    if not executable:
        raise RubberDuckError(f"{candidate.tool} is not installed")
    preflight(candidate, executable, timeout_seconds)
    prompt = build_review_prompt(kind, artifact)
    models = available_models(
        candidate.tool, candidate.models or (ModelChoice(candidate.model),), executable, timeout_seconds
    )

    if not models:
        raise RubberDuckError(f"{candidate.tool} has no configured model")
    for index, model in enumerate(models):
        try:
            return run_candidate_model(
                candidate,
                model,
                executable=executable,
                prompt=prompt,
                timeout_seconds=timeout_seconds,
            )
        except (RubberDuckError, subprocess.SubprocessError, OSError) as exc:
            # A failure anywhere inside run_candidate_model reaches here,
            # including file I/O or an AGY help probe that runs before its own
            # try block, so this is the one place that reliably knows which
            # model was being attempted. Wrapping a non-RubberDuckError here
            # keeps that model on the exception all the way to run_routes,
            # rather than letting it escape unattributed.
            duck_exc = exc if isinstance(exc, RubberDuckError) else RubberDuckError(
                f"{candidate.tool} failed to run: {sanitize_error(str(exc))}", model=model.model
            )
            reason = classify_error(str(duck_exc))
            # The final rejection is raised rather than recorded, so the caller
            # logs it once instead of the route appearing twice in the attempts.
            if index == len(models) - 1 or reason not in STEP_DOWN_REASONS:
                raise duck_exc from exc
            if attempts is not None:
                attempts.append(
                    Attempt(candidate.tool, model.model, sanitize_error(str(duck_exc)), reason, stepped_down=True)
                )
    raise RubberDuckError(f"{candidate.tool} exhausted every configured model")


STEP_DOWN_REASONS = ("model", "plan-limit")


MODEL_ERROR_RE = re.compile(
    r"unknown model|invalid model|unsupported model|unrecognized model|"
    r"model .{0,40}?not (?:found|available|supported)|no longer available|"
    r"is deprecated|has been retired",
    re.IGNORECASE,
)


# Entitlement failures: the account's plan cannot run this model, but a cheaper
# model on the same tool may still work, so the router steps down.
PLAN_LIMIT_RE = re.compile(
    r"premium requests?|usage limit|insufficient_quota|"
    r"(?:monthly|model|plan|subscription|account) quota|"
    r"upgrade your (?:plan|subscription)|"
    r"not (?:included|available) (?:in|on) your (?:plan|subscription)|"
    r"exceeded your (?:monthly |current )?(?:quota|usage|plan|allowance)|requires a paid",
    re.IGNORECASE,
)


# Transient tool-wide throttling: another model on the same tool is throttled
# too, so the router skips the tool instead of stepping down.
THROTTLE_RE = re.compile(r"rate[ -]limit|too many requests|\b429\b", re.IGNORECASE)


def classify_error(message: str) -> str:
    """Classify a reviewer failure to decide whether another model can help.

    Entitlement is checked first, so "429: you have exhausted your premium
    requests" still steps down to a model the plan covers. Its patterns name
    the account or model explicitly, which keeps generic throttling such as
    "rate limit exceeded for your quota" and local errors such as "Disk quota
    exceeded" out of it.

    Args:
        message: Failure text from the reviewer.

    Returns:
        ``throttled``, ``plan-limit``, ``model``, or ``error``.
    """

    if PLAN_LIMIT_RE.search(message):
        return "plan-limit"
    if THROTTLE_RE.search(message):
        return "throttled"
    if MODEL_ERROR_RE.search(message):
        return "model"
    return "error"


def run_candidate_model(
    candidate: Candidate,
    model: ModelChoice,
    *,
    executable: str,
    prompt: str,
    timeout_seconds: int,
) -> ReviewResult:
    """Run one reviewer with one model in an isolated temporary directory.

    Args:
        candidate: Candidate reviewer route.
        model: Model choice to attempt.
        executable: Resolved executable path.
        prompt: Complete reviewer prompt.
        timeout_seconds: Model-call timeout.

    Returns:
        Successful review result.

    Raises:
        RubberDuckError: If the reviewer is unsupported, times out, or fails.
    """

    with tempfile.TemporaryDirectory(prefix="steves-rubber-duck-") as directory:
        workdir = Path(directory)
        command, input_text, effort = harness_for(candidate.tool, model.model).build_command(
            executable, candidate, model, prompt, workdir, timeout_seconds
        )

        try:
            result = process.run_process(
                command,
                cwd=workdir,
                timeout_seconds=timeout_seconds,
                input_text=input_text,
            )
        except subprocess.TimeoutExpired as exc:
            raise RubberDuckError(f"{candidate.tool} timed out after {timeout_seconds}s", model=model.model) from exc
        except (subprocess.SubprocessError, OSError) as exc:
            # Caught here, not left to propagate, so the model being attempted
            # is still known: an OSError or another SubprocessError escaping
            # uncaught would reach run_routes with no .model to report, and it
            # would fall back to guessing the route's last configured model.
            raise RubberDuckError(
                f"{candidate.tool} failed to run: {sanitize_error(str(exc))}", model=model.model
            ) from exc

        output = result.stdout.strip()
        if result.returncode != 0:
            detail = sanitize_error(result.stderr or result.stdout)
            raise RubberDuckError(f"{candidate.tool} exited {result.returncode}: {detail}", model=model.model)
        if not output:
            raise RubberDuckError(f"{candidate.tool} returned an empty critique", model=model.model)
        family, independence = candidate.family, candidate.independence
        if candidate.tool in BROKER_TOOLS and model.model is None:
            # A broker left to pick its own model may serve any family, so the
            # cross-family claim in the header cannot be substantiated.
            family, independence = "unknown", "fresh-session"
        return ReviewResult(
            reviewer=candidate.tool,
            family=family,
            model=model.model,
            tier=candidate.tier,
            independence=independence,
            review=output,
            effort=effort,
        )


def sanitize_error(value: str) -> str:
    """Return a short single-line error safe for status output."""

    collapsed = " ".join(value.split())
    return collapsed[:300] or "no diagnostic output"


def run_routes(
    routes: list[Candidate], request: ReviewRequest, artifact: str
) -> tuple[ReviewResult | None, list[Attempt]]:
    """Try routes in order until one succeeds.

    Args:
        routes: Candidates in failover order.
        request: Normalized request.
        artifact: Review packet.

    Returns:
        Successful result, if any, and failed attempt metadata.
    """

    attempts: list[Attempt] = []
    for candidate in routes:
        try:
            return (
                execute_candidate(
                    candidate,
                    kind=request.kind,
                    artifact=artifact,
                    timeout_seconds=request.timeout_seconds,
                    attempts=attempts,
                ),
                attempts,
            )
        except (RubberDuckError, subprocess.SubprocessError, OSError) as exc:
            # RubberDuckError carries the model it was actually attempting.
            # Other exceptions (a transport failure before any model ran)
            # have none, so fall back to the route's last configured model
            # rather than claim a specific one that was never tried.
            failed = getattr(exc, "model", None)
            if failed is None and not isinstance(exc, RubberDuckError):
                failed = candidate.models[-1].model if candidate.models else candidate.model
            message = sanitize_error(str(exc))
            attempts.append(Attempt(candidate.tool, failed, message, classify_error(message)))
    return None, attempts


def perform_review(request: ReviewRequest, artifact: str) -> tuple[ReviewResult | None, list[Attempt]]:
    """Try reviewer routes until one succeeds.

    Args:
        request: Normalized request.
        artifact: Review packet.

    Returns:
        Successful result, if any, and failed attempt metadata.
    """

    return run_routes(candidate_routes(request, artifact), request, artifact)
