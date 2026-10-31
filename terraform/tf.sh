#!/usr/bin/env bash
# =============================================================================
# terraform/tf.sh – run Terraform for one cloud, then refresh <cloud>/inventory.txt
# inventory.txt = `terraform state list` (resource ADDRESSES only, no attributes → no
# secrets). The PR infra-compatibility check (ai-assist.yml) reads it, because the real
# state is local on the operator's machine. Commit inventory.txt after apply/destroy.
# Usage: terraform/tf.sh aws|gcp|budget/aws|budget/gcp <terraform command> [args]
#        e.g. terraform/tf.sh gcp apply
# State and tfvars live OUTSIDE the repo in <repo parent>/terraform-state-idea-board/<root>/
# (budget/aws → budget-aws); this wrapper passes that terraform.tfvars as -var-file.
# =============================================================================
set -euo pipefail
cloud="${1:?usage: tf.sh aws|gcp|budget/aws|budget/gcp <terraform command> [args]}"
shift
dir="$(dirname "$0")/$cloud"
vars="$(cd "$(dirname "$0")/../.." && pwd)/terraform-state-idea-board/${cloud//\//-}/terraform.tfvars"
if [[ -f "$vars" ]]; then
  # TF_CLI_ARGS_<cmd> only applies to commands that accept -var-file.
  for c in plan apply destroy import refresh console; do export "TF_CLI_ARGS_$c=-var-file=$vars"; done
fi
status=0
terraform -chdir="$dir" "$@" || status=$? # refresh the inventory even after a partial apply
terraform -chdir="$dir" state list > "$dir/inventory.txt"
echo "updated $dir/inventory.txt ($(wc -l < "$dir/inventory.txt" | tr -d ' ') resources) – commit it"
exit "$status"
