# =============================================================================
# ROOT terraform/gcp – wires the modules together, in order:
#   1. vpc  →  2. gke  →  3. argocd
# (Ingress needs no extra controller on GKE: the built-in one creates a Google LB.)
# Each module lives in ../modules. Change behaviour with variables (terraform.tfvars).
# =============================================================================

# APIs this stack needs (enabling an already-enabled API is a no-op).
resource "google_project_service" "apis" {
  for_each           = toset(["compute.googleapis.com", "container.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}

module "vpc" {
  source        = "../modules/gcp/vpc"
  name          = var.name
  region        = var.region
  subnet_cidr   = var.subnet_cidr
  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr
  depends_on    = [google_project_service.apis]
}

module "gke" {
  source              = "../modules/gcp/gke"
  project_id          = var.project_id
  name                = var.name
  zone                = var.zone
  kubernetes_version  = var.kubernetes_version
  network_id          = module.vpc.network_id
  subnet_id           = module.vpc.subnet_id
  pods_range_name     = module.vpc.pods_range_name
  services_range_name = module.vpc.services_range_name
  master_cidr         = var.master_cidr
  public_access_cidrs = var.cluster_public_access_cidrs
  machine_type        = var.machine_type
  spot                = var.spot
  node_count          = var.node_count
}

module "argocd" {
  source       = "../modules/common/argocd"
  git_repo_url = var.git_repo_url
  git_revision = var.git_revision
  git_username = var.git_username
  git_token    = var.git_token
  app_path     = "kustomize-apps/overlays/gcp"
  depends_on   = [module.gke]
}
