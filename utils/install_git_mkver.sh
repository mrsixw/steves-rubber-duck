#!/usr/bin/env bash
# Install the latest git-mkver release into /usr/local/bin.
set -euo pipefail

asset_url=$(python3 - <<'PY'
import json
import os
from urllib.request import Request, urlopen

api_url = "https://api.github.com/repos/idc101/git-mkver/releases/latest"

headers = {}
token = os.environ.get("GITHUB_TOKEN")
if token:
    headers["Authorization"] = f"Bearer {token}"

with urlopen(Request(api_url, headers=headers)) as response:
    data = json.load(response)

for asset in data.get("assets", []):
    name = asset.get("name", "")
    url = asset.get("browser_download_url", "")
    if name.endswith(".tar.gz") and "linux-x86_64" in name and url:
        print(url)
        break
else:
    raise SystemExit("No suitable git-mkver asset found")
PY
)

curl -fsSL -o /tmp/git-mkver.tar.gz "$asset_url"
tar -xzf /tmp/git-mkver.tar.gz -C /tmp
install -m 0755 /tmp/git-mkver /usr/local/bin/git-mkver
