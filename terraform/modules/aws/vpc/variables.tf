variable "name" {
  type = string
}

variable "cidr" {
  description = "VPC CIDR (/16)."
  type        = string
}

variable "az_count" {
  description = "Availability zones (EKS needs at least 2)."
  type        = number
}
