# =============================================================================
# MODULE aws/vpc – VPC + subnets + NAT
#   public  subnets (/20): internet-facing load balancers (ALB) and the NAT gateway
#   private subnets (/19): EKS nodes and pods (VPC CNI gives every pod a VPC IP → big)
# One NAT gateway (~$33/month) lets private nodes pull images; production: one per AZ.
# =============================================================================
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs             = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  public_subnets  = [for i in range(var.az_count) : cidrsubnet(var.cidr, 4, i)]     # 10.10.0.0/20, 10.10.16.0/20
  private_subnets = [for i in range(var.az_count) : cidrsubnet(var.cidr, 3, i + 2)] # 10.10.64.0/19, 10.10.96.0/19
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.7.3"

  name = var.name
  cidr = var.cidr
  azs  = local.azs

  public_subnets  = local.public_subnets
  private_subnets = local.private_subnets

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Tags the AWS Load Balancer Controller uses to find subnets for ALBs.
  public_subnet_tags  = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = "1" }

  # Lock down the default security group (CIS benchmark).
  manage_default_security_group  = true
  default_security_group_ingress = []
  default_security_group_egress  = []
}
