# =============================================================================
# MODULE gcp/artifact-registry – private Docker registry (GCP's ECR)
#   One repository per project+region holds every image:
#   <region>-docker.pkg.dev/<project>/<name>/{backend,frontend}
# * IMMUTABLE tags: a tag (CI: <version>-<sha>-<run>) can never be overwritten.
# * Cleanup: keep the newest 20 versions per image, delete the rest (storage cost stays tiny).
# * No vulnerability scanning: on GCP it is paid per image (ECR basic scan is free).
# GKE nodes can pull without extra setup: their service account has artifactregistry.reader.
# =============================================================================
resource "google_artifact_registry_repository" "this" {
  repository_id = var.name
  location      = var.region
  format        = "DOCKER"
  description   = "${var.name} container images"

  docker_config {
    immutable_tags = true
  }

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-newest-20"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }
  cleanup_policies {
    id     = "delete-older"
    action = "DELETE" # KEEP wins over DELETE → only versions beyond the newest 20 go
    condition {
      tag_state = "ANY"
    }
  }
}
