#!/usr/bin/env python3
"""Route plan and code critiques to an independent AI reviewer.

Usage:
    printf '%s' "$REVIEW_PACKET" | python3 scripts/steves_rubber_duck.py         --caller codex --caller-family openai --kind plan --tier auto
    printf '%s' "$REVIEW_PACKET" | python3 scripts/steves_rubber_duck.py         --caller claude --caller-family anthropic --kind code --reviewers all
    python3 scripts/steves_rubber_duck.py --check --format json

The router lives in the ``rubber_duck`` package next to this file, split by
concern, with one module per reviewer CLI under ``rubber_duck/harnesses``. This
script stays the entry point so that installs, the skill instructions and CI
keep working, and it re-exports the names the single-file router used to
define. To patch behaviour in tests, patch the module that owns the name, for
example ``rubber_duck.process.run_process``: a patch on this module does not
reach the callers.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from rubber_duck.common import (  # noqa: F401
    Attempt,
    BROKER_TOOLS,
    CALLER_DEFAULT_FAMILY,
    Candidate,
    COMPLEMENTARY_FAMILIES,
    DEFAULT_TIMEOUT_SECONDS,
    DIRECT_TOOL_BY_FAMILY,
    DIRECT_TOOL_FAMILY,
    FAMILIES,
    MAX_INPUT_BYTES,
    ModelChoice,
    ReviewRequest,
    ReviewResult,
    RubberDuckError,
    TOOLS,
)
from rubber_duck.catalog import (  # noqa: F401
    _BUILTIN_CATALOG,
    catalog_age_days,
    CATALOG_PATH,
    CATALOG_STALE_DAYS,
    configured_models,
    effort_args,
    load_catalog,
    MAX_MODELS_PER_ROUTE,
    REPO_ROOT,
    resolve_effort,
    skill_version,
    SUPPORTED_SCHEMA_VERSION,
    VERSION_PATH,
)
from rubber_duck.discovery import (  # noqa: F401
    _DISCOVERY_CACHE_LOCK,
    _write_discovery_cache_locked,
    available_models,
    discover_models,
    discovery_cache_path,
    DISCOVERY_TTL_SECONDS,
    MODEL_TOKEN_RE,
    read_discovery_cache,
    write_discovery_cache,
)
from rubber_duck.process import (  # noqa: F401
    descendant_pids,
    run_process,
    terminate_process_group,
)
from rubber_duck.prompt import (  # noqa: F401
    build_review_prompt,
)
from rubber_duck.harnesses.codex import (  # noqa: F401
    codex_disable_args,
    CODEX_TOOL_FEATURES,
)
from rubber_duck.harnesses.agy import (  # noqa: F401
    advertises_subcommand,
    build_agy_command,
)
from rubber_duck.harnesses import (  # noqa: F401
    harness_for,
    HARNESSES,
    preflight,
)
from rubber_duck.routing import (  # noqa: F401
    build_route,
    candidate_routes,
    classify_error,
    execute_candidate,
    HIGH_RISK_RE,
    MODEL_ERROR_RE,
    perform_review,
    PLAN_LIMIT_RE,
    resolve_tier,
    run_candidate_model,
    run_routes,
    sanitize_error,
    STEP_DOWN_REASONS,
    THROTTLE_RE,
)
from rubber_duck.panel import (  # noqa: F401
    panel_slots,
    PanelResult,
    perform_panel,
    resolve_panel_size,
    SlotOutcome,
)
from rubber_duck.report import (  # noqa: F401
    catalog_report,
    describe_choice,
    describe_slot_failure,
    probe_tools,
    render_catalog,
    render_failure,
    render_panel,
    render_success,
)
from rubber_duck.cli import (  # noqa: F401
    main,
    parse_args,
    parse_panel_tools,
    parse_reviewer_count,
)


if __name__ == "__main__":
    raise SystemExit(main())
