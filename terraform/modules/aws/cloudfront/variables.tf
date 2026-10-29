variable "name" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "ingress" {
  description = "<namespace>/<name> of the Ingress whose ALB is the origin."
  type        = string
}
