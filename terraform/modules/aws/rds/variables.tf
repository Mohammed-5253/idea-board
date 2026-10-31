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
