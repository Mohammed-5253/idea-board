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

  # Control plane → nodes for webhooks served by pods. The default rules cover 443/4443/
  # 6443/8443/9443/10250 only; the Dapr sidecar injector listens on 4000 (and the operator's
  # conversion webhook on 19443). Without this the injector webhook (failurePolicy Ignore)
  # silently creates pods WITHOUT the Dapr sidecar.
  node_security_group_additional_rules = {
    dapr_webhooks = {
      description                   = "Control plane to Dapr webhooks"
      type                          = "ingress"
      protocol                      = "tcp"
      from_port                     = 4000
      to_port                       = 4000
      source_cluster_security_group = true
    }
    dapr_conversion = {
      description                   = "Control plane to Dapr operator conversion webhook"
      type                          = "ingress"
      protocol                      = "tcp"
      from_port                     = 19443
      to_port                       = 19443
      source_cluster_security_group = true
    }
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

# =============================================================================
# EBS CSI DRIVER – lets PersistentVolumeClaims create EBS disks (Postgres needs one).
# It calls the EC2 API (create/attach volumes) → its own IAM role via IRSA, trusted ONLY
# for its ServiceAccount kube-system/ebs-csi-controller-sa. Policy = AWS managed
# AmazonEBSCSIDriverPolicy. Installed as an EKS add-on (AWS keeps it compatible with the
# cluster version).
# =============================================================================
resource "aws_iam_role" "ebs_csi" {
  name = "${var.name}-ebs-csi"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = module.eks.oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${module.eks.oidc_provider}:sub" = "system:serviceaccount:kube-system:ebs-csi-controller-sa"
          "${module.eks.oidc_provider}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name             = module.eks.cluster_name
  addon_name               = "aws-ebs-csi-driver"
  service_account_role_arn = aws_iam_role.ebs_csi.arn

  # The controller pods need a running node group.
  depends_on = [module.eks, aws_iam_role_policy_attachment.ebs_csi]
}
