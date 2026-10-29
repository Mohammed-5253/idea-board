variable "project_id" {
  description = "GCP project ID (set via TF_VAR_project_id or terraform.tfvars)."
  type        = string
}

variable "region" {
  type    = string
  default = "asia-south1"
}

variable "zone" {
  description = "Zonal cluster (one zone) = cheapest; the free GKE management credit covers one zonal cluster."
  type        = string
  default     = "asia-south1-a"
}

variable "name" {
  description = "Name used for the VPC, the GKE cluster and labels."
  type        = string
  default     = "idea-board"
}

# --- network ---------------------------------------------------------------
variable "subnet_cidr" {
  description = "Node IPs."
  type        = string
  default     = "10.20.0.0/20"
}

variable "pods_cidr" {
  description = "Pod IPs (secondary range, VPC-native)."
  type        = string
  default     = "10.24.0.0/14"
}

variable "services_cidr" {
  description = "Service ClusterIPs (secondary range)."
  type        = string
  default     = "10.20.128.0/20"
}

variable "master_cidr" {
  description = "/28 for the private GKE control plane (must not overlap the ranges above)."
  type        = string
  default     = "172.16.0.0/28"
}

# --- cluster ---------------------------------------------------------------
variable "kubernetes_version" {
  type    = string
  default = "1.36"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "spot" {
  description = "Spot VMs (cheap, demo)."
  type        = bool
  default     = true
}

variable "node_count" {
  type    = number
  default = 2
}

variable "cluster_public_access_cidrs" {
  description = "Who may reach the public Kubernetes API (auth is still IAM). Empty = anyone."
  type        = list(string)
  default     = []
}

# --- Argo CD ---------------------------------------------------------------
variable "git_repo_url" {
  description = "Git repo Argo CD watches, e.g. https://github.com/<you>/idea-board.git"
  type        = string
}

variable "git_revision" {
  type    = string
  default = "main"
}

variable "git_username" {
  description = "Only for a PRIVATE repo: GitHub username."
  type        = string
  default     = ""
}

variable "git_token" {
  description = "Only for a PRIVATE repo: read-only GitHub token (set via TF_VAR_git_token, never in a file)."
  type        = string
  default     = ""
  sensitive   = true
}
