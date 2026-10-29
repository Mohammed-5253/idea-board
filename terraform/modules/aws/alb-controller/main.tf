# =============================================================================
# MODULE aws/alb-controller – AWS Load Balancer Controller: makes `Ingress` objects work on EKS
# It watches Ingress (class "alb") and creates an Application Load Balancer for it.
# It needs AWS permissions → its own IAM role, assumed via IRSA (ServiceAccount token).
# The IAM policy is the official one from the controller's repo, pinned to the same version.
# =============================================================================
locals {
  alb_controller_version = "v2.13.3" # chart 1.13.3 ships this app version
  alb_sa                 = "aws-load-balancer-controller"
}

data "http" "alb_controller_policy" {
  url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/${local.alb_controller_version}/docs/install/iam_policy.json"
}

resource "aws_iam_policy" "alb_controller" {
  name   = "${var.name}-alb-controller"
  policy = data.http.alb_controller_policy.response_body
}

resource "aws_iam_role" "alb_controller" {
  name = "${var.name}-alb-controller"
  # Only the controller's ServiceAccount in kube-system may assume this role.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${var.oidc_provider}:sub" = "system:serviceaccount:kube-system:${local.alb_sa}"
          "${var.oidc_provider}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "alb_controller" {
  role       = aws_iam_role.alb_controller.name
  policy_arn = aws_iam_policy.alb_controller.arn
}

resource "helm_release" "alb_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = "1.13.3"
  namespace  = "kube-system"
  atomic     = true
  timeout    = 600

  values = [yamlencode({
    clusterName = var.cluster_name
    region      = var.region
    vpcId       = var.vpc_id
    serviceAccount = {
      name        = local.alb_sa
      annotations = { "eks.amazonaws.com/role-arn" = aws_iam_role.alb_controller.arn }
    }
  })]

  depends_on = [aws_iam_role_policy_attachment.alb_controller]
}
