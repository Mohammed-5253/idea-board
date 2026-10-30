terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 8.7.0, < 9.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.7.0, < 4.0.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 3.3.0, < 4.0.0"
    }
  }

  # Local state for now. Later: backend "gcs" { bucket = "...", prefix = "..." }
}
