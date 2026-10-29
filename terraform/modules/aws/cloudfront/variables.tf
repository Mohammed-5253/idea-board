variable "name" {
  type = string
}

variable "alb_name" {
  description = "Name of the ALB created by the Ingress (load-balancer-name annotation)."
  type        = string
}
