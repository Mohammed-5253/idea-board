variable "aws_profile" {
  description = "AWS CLI profile (~/.aws/credentials) Terraform uses."
  type        = string
  default     = "mkk"
}

variable "region" {
  description = "AWS region of the state bucket (the S3 backends of terraform/aws and terraform/budget/aws use it)."
  type        = string
  default     = "ap-south-1"
}

variable "name" {
  description = "Name used for tags and the Pulumi KMS alias."
  type        = string
  default     = "idea-board"
}

variable "github_repo" {
  # Same immutable owner@id/repo@id as terraform/aws (a renamed or re-created repo can't take over).
  description = "GitHub owner@id/repo@id whose workflows may read Terraform state (OIDC, no keys)."
  type        = string
  default     = "Mohammed-5253@106949872/idea-board@1438023010"
}
