# =============================================================================
# ROOT terraform/bootstrap/gcp – applied ONCE from the operator's laptop, before any other GCP root
#   1. GCS bucket for Terraform state (terraform/gcp, terraform/budget/gcp)
#   2. idea-board-state-reader: service account CI impersonates (Workload Identity
#      Federation, no keys) to list resources in the state – read-only
# Note: a deleted pool is kept 30 days and its ID can't be reused meanwhile.
# =============================================================================
resource "google_storage_bucket" "state" {
  name                        = "idea-board-tfstate-7e93dfd0" # fixed: backend blocks can't use variables
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_iam_workload_identity_pool" "state" {
  workload_identity_pool_id = "idea-board-state"
  display_name              = "GitHub Actions state reader"
}

# Any branch and pull requests of our repo (immutable owner/repo IDs); terraform/gcp's
# CI pool stays limited to main.
resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.state.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.repository"    = "assertion.repository"
  }

  attribute_condition = <<-EOT
    assertion.repository_owner_id == "${var.github_owner_id}" &&
    assertion.repository_id == "${var.github_repository_id}"
  EOT
}

resource "google_service_account" "state_reader" {
  account_id   = "idea-board-state-reader"
  display_name = "GitHub Actions Terraform state reader"
}

resource "google_service_account_iam_member" "wif" {
  service_account_id = google_service_account.state_reader.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.state.name}/attribute.repository_id/${var.github_repository_id}"
}

# Read objects in the state bucket only (no write, no other bucket).
resource "google_storage_bucket_iam_member" "state_read" {
  bucket = google_storage_bucket.state.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.state_reader.email}"
}
