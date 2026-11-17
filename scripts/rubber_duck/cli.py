"""Command-line parsing and the main entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys

# Imported under an alias because main() has a local named ``report``.
from rubber_duck import report as report_module
from rubber_duck.catalog import (
    CATALOG_STALE_DAYS,
    catalog_age_days,
    load_catalog,
    skill_version,
)
from rubber_duck.common import (
    CALLER_DEFAULT_FAMILY,
    DEFAULT_TIMEOUT_SECONDS,
    FAMILIES,
    MAX_INPUT_BYTES,
    ReviewRequest,
    TOOLS,
)
from rubber_duck.panel import panel_slots, perform_panel
from rubber_duck.report import (
    catalog_report,
    render_catalog,
    render_failure,
    render_panel,
    render_success,
)
from rubber_duck.routing import perform_review


def parse_reviewer_count(value: str) -> int | str:
    """Parse a panel size of a positive integer or ``all``.

    Raises:
        ValueError: If the value is neither.
    """

    text = value.strip().lower()
    if text == "all":
        return "all"
    count = int(text)
    if count < 1:
        raise ValueError(value)
    return count


def parse_panel_tools(value: str) -> tuple[str, ...]:
    """Parse a comma-separated allow-list of reviewer CLIs.

    Raises:
        ValueError: If the list is empty or names an unknown tool.
    """

    tools = tuple(dict.fromkeys(part.strip().lower() for part in value.split(",") if part.strip()))
    if not tools or any(tool not in TOOLS for tool in tools):
        raise ValueError(value)
    return tools


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Ask Steve's Rubber Duck for a cross-model critique. 🦆")
    parser.add_argument("--caller", choices=TOOLS)
    parser.add_argument("--caller-family", choices=FAMILIES)
    parser.add_argument("--kind", choices=("plan", "code"))
    parser.add_argument("--tier", choices=("auto", "medium", "high"), default="auto")
    parser.add_argument("--reviewer", choices=("auto", *TOOLS), default="auto")
    parser.add_argument(
        "--reviewers",
        default=None,
        help="Panel size: a positive integer or 'all' (default: RUBBER_DUCK_REVIEWERS, else 1)",
    )
    parser.add_argument(
        "--panel-tools",
        dest="panel_tools",
        default=None,
        help=f"Comma-separated reviewer CLIs a panel may use, from {','.join(TOOLS)} "
        "(default: RUBBER_DUCK_PANEL_TOOLS, else all)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.environ.get("RUBBER_DUCK_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
    )
    parser.add_argument("--format", dest="output_format", choices=("text", "json"), default="text")
    parser.add_argument("--version", action="version", version=f"steves-rubber-duck {skill_version()} 🦆")
    parser.add_argument("--check", action="store_true", help="Report provider capability without model calls")
    parser.add_argument(
        "--list-models",
        dest="list_models",
        action="store_true",
        help="Report the resolved model catalog without model calls",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    args = parse_args(argv or sys.argv[1:])
    if args.list_models:
        report = catalog_report()
        print(json.dumps(report, indent=2) if args.output_format == "json" else render_catalog(report))
        return 0

    if args.check:
        probes = report_module.probe_tools(args.timeout_seconds)
        if args.output_format == "json":
            catalog = load_catalog()
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "version": skill_version(),
                        "catalog_updated": catalog.get("updated"),
                        "catalog_age_days": catalog_age_days(catalog),
                        "providers": probes,
                    },
                    indent=2,
                ),
            )
        else:
            catalog = load_catalog()
            age = catalog_age_days(catalog)
            if age is not None and age > CATALOG_STALE_DAYS:
                print(f"⚠️🦆 Model catalog is {age} days old; run --list-models and check for newer models.")
            for probe in probes:
                icon = "✅🦆" if probe["installed"] else "💤🦆"
                models = ", ".join(str(choice["model"]) for choice in probe["models"]) or "CLI default"
                print(f"{icon} {probe['tool']}: {probe['status']} | models: {models}")
        return 0

    if os.environ.get("RUBBER_DUCK_CHILD") == "1":
        print("🦆♻️🚫 Nested rubber-duck review refused.", file=sys.stderr)
        return 5
    if not args.caller or not args.kind:
        print("error: --caller and --kind are required unless --check is used", file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0:
        print("error: --timeout-seconds must be positive", file=sys.stderr)
        return 2

    artifact = sys.stdin.read()
    if not artifact.strip():
        print("error: review packet on stdin is empty", file=sys.stderr)
        return 2
    if len(artifact.encode("utf-8")) > MAX_INPUT_BYTES:
        print("error: review packet exceeds 500,000 bytes; split it by subsystem", file=sys.stderr)
        return 2

    explicit_panel = args.reviewers is not None
    if explicit_panel:
        raw_count = args.reviewers
    elif args.reviewer != "auto":
        # A forced reviewer is a diagnostic: the environment panel default does not apply.
        raw_count = "1"
    else:
        raw_count = os.environ.get("RUBBER_DUCK_REVIEWERS", "1")
    try:
        reviewers = parse_reviewer_count(raw_count)
    except ValueError:
        source = "--reviewers" if explicit_panel else "RUBBER_DUCK_REVIEWERS"
        print(f"error: {source} must be a positive integer or 'all'", file=sys.stderr)
        return 2
    if args.reviewer != "auto" and explicit_panel:
        print("error: --reviewer selects one tool and cannot be combined with --reviewers", file=sys.stderr)
        return 2

    explicit_tools = args.panel_tools is not None
    if explicit_tools and reviewers == 1:
        print("error: --panel-tools needs a panel; pass --reviewers 2 or more", file=sys.stderr)
        return 2
    allowed_tools: tuple[str, ...] | None = None
    raw_tools = args.panel_tools if explicit_tools else os.environ.get("RUBBER_DUCK_PANEL_TOOLS")
    if reviewers != 1 and raw_tools is not None:
        try:
            allowed_tools = parse_panel_tools(raw_tools)
        except ValueError:
            source = "--panel-tools" if explicit_tools else "RUBBER_DUCK_PANEL_TOOLS"
            print(f"error: {source} must list tools from {','.join(TOOLS)}", file=sys.stderr)
            return 2

    caller_family = args.caller_family or CALLER_DEFAULT_FAMILY[args.caller]
    request = ReviewRequest(
        caller=args.caller,
        caller_family=caller_family,
        kind=args.kind,
        tier=args.tier,
        reviewer=args.reviewer,
        timeout_seconds=args.timeout_seconds,
    )
    if reviewers != 1:
        if allowed_tools is not None and not panel_slots(request, artifact, allowed_tools):
            print(
                f"error: panel tools {','.join(allowed_tools)} only serve the caller's own "
                f"family ({caller_family}), so no independent reviewer is possible",
                file=sys.stderr,
            )
            return 2
        panel = perform_panel(request, artifact, reviewers, allowed_tools)
        print(render_panel(panel, args.output_format))
        return 0 if panel.reviews or panel.fallback else 4

    result, attempts = perform_review(request, artifact)
    if result:
        print(render_success(result, attempts, args.output_format))
        return 0
    print(render_failure(attempts, args.output_format))
    return 4
