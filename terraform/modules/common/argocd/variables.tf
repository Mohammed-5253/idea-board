variable "git_repo_url" {
  type = string
}

variable "git_revision" {
  type = string
}

variable "app_path" {
  description = "Folder in the repo Argo CD syncs, e.g. kustomize-apps/overlays/aws."
  type        = string
}

variable "git_username" {
  type    = string
  default = ""
}

variable "git_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "ci_rbac_subject" {
  description = "Kubernetes identity of the CI role (read-only RBAC), e.g. { kind = \"Group\", name = \"idea-board-ci\" }."
  type        = object({ kind = string, name = string })
}
