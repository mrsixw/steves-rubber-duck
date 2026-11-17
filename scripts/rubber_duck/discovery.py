"""Runtime model discovery for CLIs that can list their models, with a 24-hour cache."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from rubber_duck import process
from rubber_duck.catalog import load_catalog
from rubber_duck.common import ModelChoice


DISCOVERY_TTL_SECONDS = 24 * 60 * 60


MODEL_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]+")


def discovery_cache_path() -> Path:
    """Return the on-disk discovery cache location."""

    root = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(root) / "steves-rubber-duck" / "discovery.json"


def read_discovery_cache(tool: str) -> list[str] | None:
    """Return cached discovered models for a tool while the entry is fresh."""

    try:
        cache = json.loads(discovery_cache_path().read_text(encoding="utf-8"))
        entry = cache[tool]
        if time.time() - entry["fetched_at"] > DISCOVERY_TTL_SECONDS:
            return None
        return [str(model) for model in entry["models"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


_DISCOVERY_CACHE_LOCK = threading.Lock()


def write_discovery_cache(tool: str, models: list[str]) -> None:
    """Persist discovered models atomically, ignoring any cache write failure.

    The read-modify-write is serialized because panel reviewers discover in
    parallel, and two unsynchronized writers would drop each other's entries.
    """

    with _DISCOVERY_CACHE_LOCK:
        _write_discovery_cache_locked(tool, models)


def _write_discovery_cache_locked(tool: str, models: list[str]) -> None:
    """Merge one tool's discovered models into the cache file."""

    path = discovery_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except (OSError, json.JSONDecodeError):
            cache = {}
        cache[tool] = {"fetched_at": time.time(), "models": models}
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            json.dump(cache, handle)
            temporary = Path(handle.name)
        temporary.chmod(0o600)
        os.replace(temporary, path)
    except OSError:
        pass


def discover_models(tool: str, executable: str, timeout_seconds: int) -> list[str]:
    """List the models a CLI reports as available.

    Parsing is deliberately loose: every whitespace-separated token on every
    output line is a candidate, because the exact listing format is not a
    documented contract. Callers intersect the result with the catalog, so
    unrelated tokens such as banner text cannot introduce a bogus model.

    Args:
        tool: Reviewer CLI name.
        executable: Resolved executable path.
        timeout_seconds: Overall timeout used to bound the probe.

    Returns:
        Discovered model tokens, empty when the tool cannot or will not report.
    """

    command = load_catalog()["tools"].get(tool, {}).get("discovery")
    if not command or os.environ.get("RUBBER_DUCK_NO_DISCOVERY") == "1":
        return []
    cached = read_discovery_cache(tool)
    if cached is not None:
        return cached
    try:
        result = process.run_process(
            [executable, *command],
            cwd=Path(tempfile.gettempdir()),
            timeout_seconds=min(timeout_seconds, 15),
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if result.returncode != 0:
        return []
    models = MODEL_TOKEN_RE.findall(result.stdout)
    write_discovery_cache(tool, models)
    return models


def available_models(
    tool: str,
    choices: tuple[ModelChoice, ...],
    executable: str,
    timeout_seconds: int,
) -> tuple[ModelChoice, ...]:
    """Filter catalog choices down to what the CLI reports it can actually run.

    Args:
        tool: Reviewer CLI name.
        choices: Catalog-ordered model choices.
        executable: Resolved executable path.
        timeout_seconds: Overall timeout used to bound the probe.

    Returns:
        Choices in catalog order. The input is returned unchanged when the tool
        supports no discovery, discovery fails, or discovery matches nothing --
        an unhelpful probe must never leave a route with no models to try.
    """

    discovered = set(discover_models(tool, executable, timeout_seconds))
    if not discovered:
        return choices
    filtered = tuple(
        choice for choice in choices if choice.model is None or choice.model in discovered
    )
    return filtered or choices
