variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  description = "Allowed to reach PostgreSQL (EKS pods get VPC IPs)."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets (at least 2 AZs, required by RDS)."
  type        = list(string)
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro" # cheapest Graviton class (2 vCPU burst, 1 GiB)
}

variable "oidc_provider_arn" {
  type = string
}

variable "oidc_provider" {
  description = "EKS OIDC issuer without https:// (IRSA trust policy)."
  type        = string
}

variable "service_account" {
  description = "<namespace>:<name> of the backend ServiceAccount allowed to read the DB secrets."
  type        = string
  default     = "idea-board:backend"
}
