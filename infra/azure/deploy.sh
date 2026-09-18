#!/usr/bin/env bash
# Run from a trusted operator workstation. Never run using worker credentials.
set -euo pipefail
action=${1:?Usage: bash infra/azure/deploy.sh validate|what-if|deploy SUBSCRIPTION_ID RESOURCE_GROUP PARAMETER_FILE}
subscription=${2:?Supply explicit subscription ID}
group=${3:?Supply existing resource group}
parameters=${4:?Supply a local .bicepparam file}
case "$action" in validate|what-if|deploy) ;; *) echo 'Invalid action' >&2; exit 2;; esac
[[ $subscription =~ ^[a-fA-F0-9-]{36}$ ]] || { echo 'Use a subscription UUID' >&2; exit 2; }
root=$(cd "$(dirname "$0")/../.." && pwd)
[[ -f $parameters ]] || { echo 'Parameter file not found' >&2; exit 2; }
build_dir=$(mktemp -d)
trap 'rm -f "$build_dir/parameters.json" "$build_dir/template.json"; rmdir "$build_dir"' EXIT
az bicep build --file "$root/infra/azure/main.bicep" --outfile "$build_dir/template.json"
az bicep build-params --file "$parameters" --outfile "$build_dir/parameters.json"
python3 "$root/infra/azure/validate-parameters.py" "$build_dir/parameters.json"
# Explicit subscription on every cloud call; no implicit account switching.
az group show --subscription "$subscription" --name "$group" --query id -o tsv
operation=$action
[[ $action == deploy ]] && operation=create
az deployment group "$operation" \
  --subscription "$subscription" --resource-group "$group" \
  --name agentgatehouse --template-file "$build_dir/template.json" \
  --parameters "@$build_dir/parameters.json"
