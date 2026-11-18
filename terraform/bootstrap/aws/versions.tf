terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.70.0, < 7.0.0"
    }
  }

  # The bucket that holds every other root's state can't hold its own: this root keeps
  # local state OUTSIDE the repo, like the roots did before remote state.
  backend "local" {
    path = "../../../../terraform-state-idea-board/bootstrap-aws/terraform.tfstate"
  }
}
