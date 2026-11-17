"""Status probes and the text and JSON renderings of results."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict

from rubber_duck import discovery
from rubber_duck.catalog import (
    CATALOG_STALE_DAYS,
    catalog_age_days,
    configured_models,
    load_catalog,
    skill_version,
)
from rubber_duck.common import (
    Attempt,
    Candidate,
    DIRECT_TOOL_FAMILY,
    ModelChoice,
    ReviewResult,
    RubberDuckError,
    TOOLS,
)
from rubber_duck.discovery import available_models
from rubber_duck.harnesses import preflight
from rubber_duck.panel import PanelResult, SlotOutcome


def probe_tools(timeout_seconds: int) -> list[dict[str, object]]:
    """Inspect installed tools, auth signals, and resolved models without model calls."""

    probes: list[dict[str, object]] = []
    for tool in TOOLS:
        executable = shutil.which(tool)
        if not executable:
            probes.append({"tool": tool, "installed": False, "status": "not installed", "models": []})
            continue
        family = DIRECT_TOOL_FAMILY.get(tool, "unknown")
        choices = configured_models(tool, family, "medium")
        candidate = Candidate(
            tool,
            family,
            choices[0].model if choices else None,
            "medium",
            "diagnostic",
            choices,
            choices[0].effort if choices else None,
        )
        try:
            preflight(candidate, executable, timeout_seconds)
            status = "authenticated" if tool in {"claude", "codex"} else "installed; auth verified on live call"
        except RubberDuckError as exc:
            status = str(exc)
        discovered = discovery.discover_models(tool, executable, timeout_seconds)
        probes.append(
            {
                "tool": tool,
                "installed": True,
                "status": status,
                "models": [describe_choice(choice) for choice in choices],
                "discovery": "unsupported" if not discovered else f"{len(discovered)} models reported",
            },
        )
    return probes


def describe_choice(choice: ModelChoice) -> dict[str, str | None]:
    """Render one model choice for diagnostic output."""

    return {"model": choice.model or "CLI default", "effort": choice.effort}


def catalog_report() -> dict[str, object]:
    """Resolve every catalog route for diagnostics, applying discovery where possible."""

    catalog = load_catalog()
    age = catalog_age_days(catalog)
    tools: dict[str, object] = {}
    for tool in TOOLS:
        executable = shutil.which(tool)
        families: dict[str, object] = {}
        for family, tiers in catalog["tools"].get(tool, {}).get("families", {}).items():
            resolved = {}
            for tier in tiers:
                choices = configured_models(tool, family, tier)
                if executable:
                    choices = available_models(tool, choices, executable, 15)
                resolved[tier] = [describe_choice(choice) for choice in choices]
            families[family] = resolved
        tools[tool] = {"installed": bool(executable), "families": families}
    return {
        "version": skill_version(),
        "updated": catalog.get("updated"),
        "age_days": age,
        "stale": age is not None and age > CATALOG_STALE_DAYS,
        "tools": tools,
    }


def render_catalog(report: dict[str, object]) -> str:
    """Render the resolved catalog for humans."""

    lines = [
        f"🦆📇 Steve's Rubber Duck {report['version']} — "
        f"catalog updated {report['updated']} ({report['age_days']} days ago)",
    ]
    if report["stale"]:
        lines.append(f"⚠️🦆 Catalog is older than {CATALOG_STALE_DAYS} days; check for newer models.")
    for tool, detail in report["tools"].items():
        icon = "✅🦆" if detail["installed"] else "💤🦆"
        lines.append(f"{icon} {tool}")
        for family, tiers in detail["families"].items():
            for tier, choices in tiers.items():
                rendered = ", ".join(
                    f"{choice['model']}" + (f" (effort {choice['effort']})" if choice["effort"] else "")
                    for choice in choices
                ) or "none configured"
                lines.append(f"   {family}/{tier}: {rendered}")
    return "\n".join(lines)


def render_success(result: ReviewResult, attempts: list[Attempt], output_format: str) -> str:
    """Render a successful review for humans or automation."""

    if output_format == "json":
        return json.dumps(
            {
                "status": "ok",
                "version": skill_version(),
                **asdict(result),
                "attempts": [asdict(item) for item in attempts],
            },
            ensure_ascii=False,
            indent=2,
        )
    model = result.model or "configured capable default"
    heading = "🦆📋" if "plan" in result.review.lower() else "🦆🔍"
    return (
        f"{heading} Steve's Rubber Duck — Your Cardboard Engineer 📦👷🦆\n"
        f"Reviewer: {result.reviewer} | Model: {model} | Tier: {result.tier} | "
        f"Effort: {result.effort or 'n/a'} | "
        f"Independence: {result.independence}\n\n{result.review}"
    )


def render_failure(attempts: list[Attempt], output_format: str) -> str:
    """Render complete route exhaustion without hiding degraded status."""

    if output_format == "json":
        return json.dumps(
            {"status": "unavailable", "attempts": [asdict(item) for item in attempts]},
            ensure_ascii=False,
            indent=2,
        )
    lines = [
        "🫠🦆 Steve's Rubber Duck — Your Cardboard Engineer 📦👷🦆",
        "Reviewer: in-session self-critique | Model: caller | Independence: degraded",
        "",
        "🫠🦆 No reviewer route succeeded. Perform an in-session self-critique.",
    ]
    lines.extend(f"- {item.reviewer}: {item.error}" for item in attempts)
    return "\n".join(lines)


def describe_slot_failure(outcome: SlotOutcome) -> str:
    """Summarize why a panel slot went unfilled, one clause per tool tried."""

    clauses = [
        f"{item.reviewer} {item.reason}" if item.reason != "error" else f"{item.reviewer}: {item.error[:80]}"
        for item in outcome.attempts
    ]
    return f"{outcome.family} slot: " + "; ".join(clauses)


def render_panel(panel: PanelResult, output_format: str) -> str:
    """Render a panel review for humans or automation.

    Args:
        panel: Completed panel outcome.
        output_format: ``text`` or ``json``.

    Returns:
        Rendered output. Falls back to ``render_failure`` when nothing ran.
    """

    reviews = panel.reviews
    attempts = panel.attempts
    gaps = [describe_slot_failure(outcome) for outcome in panel.outcomes if outcome.result is None]
    if not reviews and not panel.fallback:
        if output_format == "json":
            return json.dumps(
                {
                    "status": "unavailable",
                    "version": skill_version(),
                    "requested": panel.requested,
                    "target": panel.target,
                    "achieved": 0,
                    "attempts": [asdict(item) for item in attempts],
                },
                ensure_ascii=False,
                indent=2,
            )
        summary = [f"🫠🦆 Panel: 0/{panel.target} — no reviewer or fallback succeeded"]
        summary.extend(f"   - {gap}" for gap in gaps)
        return "\n".join([*summary, "", render_failure(attempts, output_format)])

    if output_format == "json":
        return json.dumps(
            {
                "status": "ok",
                "version": skill_version(),
                "requested": panel.requested,
                "target": panel.target,
                "achieved": len(reviews),
                "reviews": [asdict(result) for result in reviews],
                "fallback": asdict(panel.fallback) if panel.fallback else None,
                "attempts": [asdict(item) for item in attempts],
            },
            ensure_ascii=False,
            indent=2,
        )

    capped = (
        f" (requested {panel.requested}; {panel.target} "
        f"{'family' if panel.target == 1 else 'families'} available)"
        if panel.requested != "all" and panel.requested > panel.target
        else ""
    )
    lines: list[str] = []
    if panel.fallback:
        lines.append(f"🦆⚠️ Panel: 0/{panel.target}{capped} — fell back to fresh-session review")
        lines.extend(f"   - {gap}" for gap in gaps)
        lines.append("")
        lines.append(render_success(panel.fallback, [], "text"))
    else:
        members = ", ".join(f"{result.reviewer} {result.family}" for result in reviews)
        line = f"🦆🦆 Panel: {len(reviews)}/{panel.target}{capped} ({members})"
        if gaps:
            line += " — " + " | ".join(gaps)
        lines.append(line)
        for result in reviews:
            lines.append("")
            lines.append(render_success(result, [], "text"))
    step_downs = [item for item in attempts if item.stepped_down]
    if step_downs:
        lines.append("")
        lines.extend(
            f"↘️🦆 {item.reviewer}: {item.model or 'CLI default'} {item.reason}, stepped down"
            for item in step_downs
        )
    return "\n".join(lines)
