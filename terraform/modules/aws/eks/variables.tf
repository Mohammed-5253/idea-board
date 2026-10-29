variable "name" {
  type = string
}

variable "kubernetes_version" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "PRIVATE subnets for the nodes."
  type        = list(string)
}

variable "public_access_cidrs" {
  description = "Who may reach the public Kubernetes API (auth is still IAM)."
  type        = list(string)
}

variable "node_instance_types" {
  type = list(string)
}

variable "node_capacity_type" {
  description = "SPOT or ON_DEMAND."
  type        = string
}

variable "node_count" {
  type = number
}
