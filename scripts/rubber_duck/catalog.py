"""Model catalogue loading, per-route model choice and effort flags."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from rubber_duck.common import ModelChoice


MAX_MODELS_PER_ROUTE = 6


CATALOG_STALE_DAYS = 90


SUPPORTED_SCHEMA_VERSION = 1


REPO_ROOT = Path(__file__).resolve().parents[2]


CATALOG_PATH = REPO_ROOT / "data" / "models.json"


VERSION_PATH = REPO_ROOT / "VERSION"


# Fallback catalog used only when data/models.json is missing or unreadable, so a
# damaged checkout still routes instead of failing outright. Deliberately minimal:
# it prefers each CLI's own self-refreshing default or alias.
_BUILTIN_CATALOG = {
    "schema_version": SUPPORTED_SCHEMA_VERSION,
    "updated": "2026-08-20",
    "effort_preference": {"medium": ["medium", "low"], "high": ["xhigh", "high", "medium"]},
    "tools": {
        "claude": {
            "discovery": None,
            "effort": {"style": "flag", "flag": "--effort"},
            "families": {
                "anthropic": {
                    "high": [{"id": "opus", "efforts": ["low", "medium", "high", "xhigh", "max"]}],
                    "medium": [{"id": "sonnet", "efforts": ["low", "medium", "high", "xhigh", "max"]}],
                },
            },
        },
        "codex": {
            "discovery": None,
            "effort": {"style": "config", "key": "model_reasoning_effort"},
            "families": {"openai": {"high": [{"id": None}], "medium": [{"id": None}]}},
        },
        "agy": {
            "discovery": ["models"],
            "effort": None,
            "families": {
                "google": {
                    "high": [{"id": "gemini-3.1-pro-high"}],
                    "medium": [{"id": "gemini-3.5-flash-medium"}],
                },
            },
        },
        "copilot": {"discovery": None, "effort": None, "families": {}},
    },
}


def skill_version() -> str:
    """Return the installed skill version.

    Returns:
        Version string from the VERSION file, or ``"unknown"`` when the file is
        absent or unreadable, as it is in a partial or vendored checkout.
    """

    try:
        return VERSION_PATH.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def load_catalog() -> dict:
    """Load the model catalog, falling back to the builtin when it is unusable.

    Returns:
        Catalog mapping. Never raises: a missing, unreadable, malformed, or
        future-versioned file degrades to ``_BUILTIN_CATALOG`` so the router
        still routes.
    """

    path = Path(os.environ.get("RUBBER_DUCK_MODELS_FILE", CATALOG_PATH))
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _BUILTIN_CATALOG
    if not isinstance(catalog, dict) or not isinstance(catalog.get("tools"), dict):
        return _BUILTIN_CATALOG
    if catalog.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        return _BUILTIN_CATALOG
    return catalog


def catalog_age_days(catalog: dict) -> int | None:
    """Return the catalog's age in days, or ``None`` when it has no valid date."""

    try:
        return (date.today() - date.fromisoformat(catalog["updated"])).days
    except (KeyError, TypeError, ValueError):
        return None


def resolve_effort(entry: dict, tier: str, catalog: dict) -> str | None:
    """Pick the best reasoning effort a model actually supports for a tier.

    Args:
        entry: Catalog model entry.
        tier: Resolved capability tier.
        catalog: Loaded catalog, for its effort preference order.

    Returns:
        Effort level, or ``None`` when the model declares no effort control.
    """

    supported = entry.get("efforts") or ()
    if not supported:
        return None
    preference = catalog.get("effort_preference", {}).get(tier) or ()
    for level in preference:
        if level in supported:
            return level
    return None


def configured_models(tool: str, family: str, tier: str) -> tuple[ModelChoice, ...]:
    """Return ordered model choices for a reviewer route, newest first.

    Environment overrides win outright and collapse the route to one choice, so
    an operator can always pin an exact model without editing the catalog.

    Args:
        tool: Reviewer CLI name.
        family: Underlying model family.
        tier: Resolved capability tier.

    Returns:
        Model choices in preference order, capped at ``MAX_MODELS_PER_ROUTE``.
        An entry whose ``model`` is ``None`` means "use the CLI's own default".
    """

    prefix = f"RUBBER_DUCK_{tool.upper()}_{family.upper()}_{tier.upper()}"
    override = os.environ.get(f"{prefix}_MODEL")
    if override is None and tool == "codex":
        override = os.environ.get("RUBBER_DUCK_CODEX_MODEL")
    if override is not None:
        return (ModelChoice(override or None, os.environ.get(f"{prefix}_EFFORT")),)

    catalog = load_catalog()
    entries = (
        catalog["tools"]
        .get(tool, {})
        .get("families", {})
        .get(family, {})
        .get(tier, [])
    )
    effort_override = os.environ.get(f"{prefix}_EFFORT")
    choices = []
    for entry in entries[:MAX_MODELS_PER_ROUTE]:
        if not isinstance(entry, dict):
            continue
        effort = effort_override or resolve_effort(entry, tier, catalog)
        choices.append(ModelChoice(entry.get("id"), effort))
    return tuple(choices)


def effort_args(tool: str, effort: str | None, help_text: str = "") -> list[str]:
    """Render a reasoning effort into CLI arguments for one tool.

    Args:
        tool: Reviewer CLI name.
        effort: Resolved effort level, or ``None``.
        help_text: Probed help output, used when the tool needs flag discovery.

    Returns:
        Arguments to append, empty when the tool or model has no effort control.
    """

    if not effort:
        return []
    config = load_catalog()["tools"].get(tool, {}).get("effort")
    if not config:
        return []
    style = config.get("style")
    if style == "config":
        return ["-c", f'{config["key"]}="{effort}"']
    if style == "flag":
        flag = config["flag"]
        if config.get("probe_help") and flag not in help_text:
            return []
        return [flag, effort]
    return []
