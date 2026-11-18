#!/usr/bin/env bash
# ci/state_list.sh aws|gcp – print the resource addresses of that cloud's Terraform state.
# The state is streamed from its bucket straight into ci/state_addresses.py: it is never
# written to disk or printed, and only addresses (no attribute values) come out.
# Needs the read-only state identity (AWS_STATE_READER_ROLE_ARN / GCP_STATE_* in CI).
# A state that does not exist yet (root never applied) prints nothing; any other error
# (denied, expired credentials) fails, so a refused read never looks like an empty state.
set -euo pipefail
here="$(dirname "$0")"
case "${1:?usage: state_list.sh aws|gcp}" in
  aws)
    bucket="idea-board-tfstate-326435482847" key="terraform/aws/terraform.tfstate"
    if ! err="$(aws s3api head-object --bucket "$bucket" --key "$key" 2>&1 >/dev/null)"; then
      case "$err" in *"(404)"*|*NoSuchKey*) exit 0 ;; esac
      echo "$err" >&2; exit 1
    fi
    aws s3 cp --only-show-errors "s3://$bucket/$key" - | python3 "$here/state_addresses.py"
    ;;
  gcp)
    # The gcs backend stores the default workspace as <prefix>/default.tfstate.
    uri="gs://idea-board-tfstate-7e93dfd0/terraform/gcp/default.tfstate"
    if ! err="$(gcloud storage ls "$uri" 2>&1 >/dev/null)"; then
      case "$err" in *"matched no objects"*|*"404"*) exit 0 ;; esac
      echo "$err" >&2; exit 1
    fi
    gcloud storage cat "$uri" | python3 "$here/state_addresses.py"
    ;;
  *) echo "unknown cloud '$1' (use aws or gcp)" >&2; exit 1 ;;
esac
