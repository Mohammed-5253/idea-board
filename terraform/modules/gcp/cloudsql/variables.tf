variable "project_id" {
  type = string
}

variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "zone" {
  description = "Same zone as the GKE cluster."
  type        = string
}

variable "network_id" {
  type = string
}

variable "tier" {
  type    = string
  default = "db-f1-micro" # cheapest: shared vCPU, 0.6 GiB
}

variable "k8s_namespace" {
  type    = string
  default = "idea-board"
}

variable "k8s_service_account" {
  description = "Backend Kubernetes ServiceAccount allowed to read the DB secrets (Workload Identity)."
  type        = string
  default     = "backend"
}
