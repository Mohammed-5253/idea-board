variable "aws_profile" {
  description = "AWS CLI profile (~/.aws/credentials) Terraform uses."
  type        = string
  default     = "mkk"
}

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
  default = ["t3.large", "t3a.large"]
}

variable "node_capacity_type" {
  description = "SPOT (cheap, demo) or ON_DEMAND."
  type        = string
  default     = "SPOT"
}

variable "node_count" {
  type    = number
  default = 1
}

variable "cluster_public_access_cidrs" {
  description = "Who may reach the public Kubernetes API (auth is still IAM). Tighten to your IP, e.g. [\"203.0.113.7/32\"]."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# --- add-ons (step 2: ALB controller, Argo CD) ---
variable "install_addons" {
  description = "false = build only VPC + EKS (step 1). Set true for the ALB controller and Argo CD."
  type        = bool
  default     = false
}

# --- Argo CD ---------------------------------------------------------------
variable "git_repo_url" {
  description = "Git repo Argo CD watches (needed only when install_addons = true)."
  type        = string
  default     = "https://github.com/Mohammed-5253/idea-board.git"
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

# --- CI (GitHub Actions) ---------------------------------------------------
variable "github_repo" {
  # GitHub's OIDC `sub` uses owner@<owner-id>/repo@<repo-id> (immutable IDs: a renamed or
  # re-created repo with the same name can't take over this role). IDs from CloudTrail.
  description = "GitHub owner@id/repo@id whose main-branch workflows may push images (OIDC, no keys)."
  type        = string
  default     = "Mohammed-5253@106949872/idea-board@1438023010"
}

variable "enable_cloudfront" {
  description = "HTTPS URL via CloudFront in front of the app's ALB. Turn on only after Argo CD has created the app Ingress (and its ALB)."
  type        = bool
  default     = false
}
