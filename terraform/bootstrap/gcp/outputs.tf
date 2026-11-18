output "state_bucket" {
  value = google_storage_bucket.state.name
}

output "state_reader_wif_provider" {
  description = "Repository variable GCP_STATE_WIF_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "state_reader_service_account" {
  description = "Repository variable GCP_STATE_SERVICE_ACCOUNT."
  value       = google_service_account.state_reader.email
}
