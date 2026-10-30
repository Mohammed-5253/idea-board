variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "github_owner_id" {
  description = "Numeric GitHub owner ID (immutable)."
  type        = string
}

variable "github_repository_id" {
  description = "Numeric GitHub repository ID (immutable)."
  type        = string
}

variable "repository_name" {
  description = "Artifact Registry repository the CI may push to."
  type        = string
}
