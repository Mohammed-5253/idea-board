terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 8.7.0, < 9.0.0"
    }
  }

  # The bucket that holds every other root's state can't hold its own: this root keeps
  # local state OUTSIDE the repo, like the roots did before remote state.
  backend "local" {
    path = "../../../../terraform-state-idea-board/bootstrap-gcp/terraform.tfstate"
  }
}
