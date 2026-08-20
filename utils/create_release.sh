#!/usr/bin/env bash
# Create the GitHub release for a version.
#
# The skill is installed by cloning the repository, so the release carries no
# built artifacts: the tag and its generated notes are the deliverable.
set -euo pipefail

version="$1"
tag="v${version}"

gh release create "${tag}" \
  --title "${tag}" \
  --generate-notes \
  --target "$(git rev-parse HEAD)"
