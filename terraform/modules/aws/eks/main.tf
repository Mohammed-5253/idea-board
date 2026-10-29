# =============================================================================
# MODULE aws/eks – EKS cluster + one managed node group
#   * Access via EKS access entries (API mode). Whoever runs `terraform apply` is admin.
#   * IRSA on: pods get AWS permissions through their ServiceAccount (used by the ALB
#     controller module), never through the node role.
#   * vpc-cni enableNetworkPolicy: otherwise NetworkPolicies are silently ignored.
# =============================================================================
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.29.0"

  name               = var.name
  kubernetes_version = var.kubernetes_version

  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids

  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.public_access_cidrs
  endpoint_private_access      = true

  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = true
  enable_irsa                              = true

  addons = {
    vpc-cni = {
      before_compute       = true
      configuration_values = jsonencode({ enableNetworkPolicy = "true" })
    }
    kube-proxy = {}
    coredns    = {}
  }

  eks_managed_node_groups = {
    default = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.node_instance_types
      capacity_type  = var.node_capacity_type
      min_size       = var.node_count
      max_size       = var.node_count + 1
      desired_size   = var.node_count
    }
  }
}

# The control plane must reach the Dapr sidecar-injector webhook on the nodes (port 4000).
resource "aws_security_group_rule" "dapr_webhook" {
  description              = "EKS control plane -> Dapr sidecar injector webhook"
  type                     = "ingress"
  protocol                 = "tcp"
  from_port                = 4000
  to_port                  = 4000
  security_group_id        = module.eks.node_security_group_id
  source_security_group_id = module.eks.cluster_security_group_id
}
