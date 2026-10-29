variable "region" {
  description = "AWS region."
  type        = string
  default     = "ap-south-1"
}

variable "name" {
  description = "Name used for the VPC, the EKS cluster and tags."
  type        = string
  default     = "idea-board"
}

# --- network ---------------------------------------------------------------
variable "vpc_cidr" {
  description = "VPC CIDR (/16)."
  type        = string
  default     = "10.10.0.0/16"
}

variable "az_count" {
  description = "Availability zones to use (EKS needs at least 2)."
  type        = number
  default     = 2
}

# --- cluster ---------------------------------------------------------------
variable "kubernetes_version" {
  type    = string
  default = "1.36"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium", "t3a.medium"]
}

variable "node_capacity_type" {
  description = "SPOT (cheap, demo) or ON_DEMAND."
  type        = string
  default     = "SPOT"
}

variable "node_count" {
  type    = number
  default = 2
}

variable "cluster_public_access_cidrs" {
  description = "Who may reach the public Kubernetes API (auth is still IAM). Tighten to your IP, e.g. [\"203.0.113.7/32\"]."
  type        = list(string)
  default     = ["0.0.0.0/0"]
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
