# =============================================================================
# MODULE gcp/github-wif – lets GitHub Actions log in to GCP WITHOUT stored keys
# (GCP's version of aws/github-oidc)
# 1. Workload Identity Pool + OIDC provider: GCP trusts tokens issued by GitHub.
#    attribute_condition: ONLY workflows of our repo (immutable owner/repo IDs, so a
#    renamed or re-created repo with the same name can't get in) running on `main`.
# 2. Service account the workflow impersonates; it gets short-lived tokens (~1 h).
# 3. Permission: push/pull to OUR Artifact Registry repository only (least privilege).
# Note: a deleted pool is kept 30 days and its ID can't be reused meanwhile
#   (re-apply after destroy → undelete it: gcloud iam workload-identity-pools undelete).
# =============================================================================
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${var.name}-github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub OIDC"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.repository"    = "assertion.repository"
    "attribute.ref"           = "assertion.ref"
  }

  attribute_condition = <<-EOT
    assertion.repository_owner_id == "${var.github_owner_id}" &&
    assertion.repository_id == "${var.github_repository_id}" &&
    assertion.ref == "refs/heads/main"
  EOT
}

resource "google_service_account" "ci" {
  account_id   = "${var.name}-github-ci"
  display_name = "GitHub Actions CI (${var.name})"
}

# Only tokens from our repo (already filtered by attribute_condition) may act as the SA.
resource "google_service_account_iam_member" "wif" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

resource "google_artifact_registry_repository_iam_member" "push" {
  location   = var.region
  repository = var.repository_name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.ci.email}"
}
