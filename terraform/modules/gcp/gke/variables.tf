variable "project_id" {
  type = string
}

variable "name" {
  type = string
}

variable "zone" {
  type = string
}

variable "kubernetes_version" {
  description = "Minimum control-plane version; null = release channel default."
  type        = string
  default     = null
}

variable "network_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "pods_range_name" {
  type = string
}

variable "services_range_name" {
  type = string
}

variable "master_cidr" {
  type = string
}

variable "public_access_cidrs" {
  description = "Who may reach the public Kubernetes API. Empty = anyone (auth is still IAM)."
  type        = list(string)
}

variable "machine_type" {
  type = string
}

variable "spot" {
  type = bool
}

variable "node_count" {
  type = number
}
