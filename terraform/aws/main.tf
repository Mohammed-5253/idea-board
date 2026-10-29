# =============================================================================
# ROOT terraform/aws – wires the modules together, in order:
#   1. vpc  →  2. eks  →  3. alb-controller (Ingress → ALB)  →  4. dapr  →  5. argocd
# Each module lives in ../modules. Change behaviour with variables (terraform.tfvars).
# =============================================================================
module "vpc" {
  source   = "../modules/aws/vpc"
  name     = var.name
  cidr     = var.vpc_cidr
  az_count = var.az_count
}

module "eks" {
  source              = "../modules/aws/eks"
  name                = var.name
  kubernetes_version  = var.kubernetes_version
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.private_subnet_ids
  public_access_cidrs = var.cluster_public_access_cidrs
  node_instance_types = var.node_instance_types
  node_capacity_type  = var.node_capacity_type
  node_count          = var.node_count
}

module "alb_controller" {
  source            = "../modules/aws/alb-controller"
  name              = var.name
  region            = var.region
  cluster_name      = module.eks.cluster_name
  vpc_id            = module.vpc.vpc_id
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider     = module.eks.oidc_provider
}

module "dapr" {
  source     = "../modules/common/dapr"
  depends_on = [module.eks]
}

module "argocd" {
  source       = "../modules/common/argocd"
  git_repo_url = var.git_repo_url
  git_revision = var.git_revision
  git_username = var.git_username
  git_token    = var.git_token
  app_path     = "kustomize-apps/overlays/aws"
  # The app needs the Dapr sidecar injector and the ALB controller before its first sync.
  depends_on = [module.dapr, module.alb_controller]
}
