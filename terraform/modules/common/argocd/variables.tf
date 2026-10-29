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
