output "repository_id" {
  value = google_artifact_registry_repository.this.id
}

output "repository_name" {
  value = google_artifact_registry_repository.this.name
}

output "registry_url" {
  description = "Image prefix, e.g. <region>-docker.pkg.dev/<project>/<name>; images go below it."
  value       = "${var.region}-docker.pkg.dev/${google_artifact_registry_repository.this.project}/${google_artifact_registry_repository.this.repository_id}"
}
