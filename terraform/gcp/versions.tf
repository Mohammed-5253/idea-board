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
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.36.0, < 4.0.0"
    }
  }

  # Remote state in the bucket from terraform/bootstrap/gcp (backend blocks can't use
  # variables). GCS locks the state itself.
  backend "gcs" {
    bucket = "idea-board-tfstate-7e93dfd0"
    prefix = "terraform/gcp"
  }
}
