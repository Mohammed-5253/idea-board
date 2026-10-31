terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.36.0, < 4.0.0"
    }
  }
}
