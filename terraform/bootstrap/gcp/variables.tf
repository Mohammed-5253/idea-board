variable "project_id" {
  description = "GCP project ID (set via TF_VAR_project_id or terraform.tfvars)."
  type        = string
}

variable "region" {
  type    = string
  default = "asia-south1"
}

variable "github_owner_id" {
  type    = string
  default = "106949872"
}

variable "github_repository_id" {
  type    = string
  default = "1438023010"
}
