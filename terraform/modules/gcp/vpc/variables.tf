variable "name" {
  type = string
}

variable "region" {
  type = string
}

variable "subnet_cidr" {
  description = "Node IPs."
  type        = string
}

variable "pods_cidr" {
  description = "Pod IPs (secondary range, VPC-native)."
  type        = string
}

variable "services_cidr" {
  description = "Service ClusterIPs (secondary range)."
  type        = string
}

variable "master_cidr" {
  description = "The GKE control plane's /28 (allowed to call the Dapr webhook)."
  type        = string
}
