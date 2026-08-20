#!/usr/bin/env bash
# Bump VERSION and push the bump when the current version is already tagged.
#
# Prints the version to release on stdout, which is either the unchanged input
# or the freshly bumped value.
set -euo pipefail

version="$1"

if git rev-parse -q --verify "refs/tags/v${version}" >/dev/null; then
  branch_name="$(git symbolic-ref --quiet --short HEAD || true)"
  branch_name="${branch_name:-${GITHUB_HEAD_REF:-${GITHUB_REF_NAME:-}}}"

  if [[ -z "${branch_name}" ]]; then
    echo "Unable to determine branch name for release version bump" >&2
    exit 1
  fi

  git config user.name "github-actions[bot]"
  git config user.email "github-actions[bot]@users.noreply.github.com"
  git mkver patch >/dev/null
  version=$(python3 utils/read_version.py)
  git add VERSION
  git commit -m "chore: bump version to ${version}" >/dev/null
  if ! git push origin "HEAD:${branch_name}"; then
    echo "git push failed; version bump commit not pushed" >&2
    exit 1
  fi
fi

printf '%s\n' "$version"
