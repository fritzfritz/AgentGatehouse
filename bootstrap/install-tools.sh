#!/usr/bin/env bash
# Run after worker.py. Supply exact reviewed Node and agent versions.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root' >&2; exit 1; }
node_version=${1:?Supply exact Node version, at least 22.21.0}
node_sha256=${2:?Supply trusted SHA256 for the linux-x64 Node archive}
codex_version=${3:?Supply exact @openai/codex version}
claude_version=${4:?Supply exact @anthropic-ai/claude-code version}
for version in "$node_version" "$codex_version" "$claude_version"; do
  [[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Versions must be exact x.y.z values' >&2; exit 1; }
done
[[ $node_sha256 =~ ^[a-f0-9]{64}$ ]] || exit 1
source /etc/profile.d/agentgatehouse.sh
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y git curl jq python3 python3-venv build-essential docker.io ca-certificates xz-utils
archive=$(mktemp /tmp/gatehouse-node.XXXXXX)
trap 'rm -f "$archive"' EXIT
curl --fail --silent --show-error --location "https://nodejs.org/dist/v${node_version}/node-v${node_version}-linux-x64.tar.xz" --output "$archive"
printf '%s  %s\n' "$node_sha256" "$archive" | sha256sum --check --status
tar -xJf "$archive" -C /usr/local --strip-components=1
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(a<22 || (a===22 && b<21)) process.exit(1)'
npm install --global "@openai/codex@$codex_version" "@anthropic-ai/claude-code@$claude_version"
systemctl daemon-reload
systemctl enable --now docker
systemctl restart docker
echo 'Tools installed. Use sudo docker or explicitly grant the project user Docker access (equivalent to worker root).'
