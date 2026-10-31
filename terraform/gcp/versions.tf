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

  # State lives OUTSIDE the repo: <repo parent>/terraform-state-idea-board/<root>/ with terraform.tfvars (path is
  # relative to this folder; terraform -chdir / tf.sh keep it correct).
  backend "local" {
    path = "../../../terraform-state-idea-board/gcp/terraform.tfstate"
  }
}
