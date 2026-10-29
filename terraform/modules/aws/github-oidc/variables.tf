variable "name" {
  type = string
}

variable "github_repo" {
  description = "owner/repo allowed to assume the CI role, e.g. Mohammed-5253/idea-board."
  type        = string
}

variable "ecr_repository_arns" {
  description = "ECR repositories CI may push to."
  type        = list(string)
}
