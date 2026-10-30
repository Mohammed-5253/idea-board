# =============================================================================
# ROOT terraform/gcp – wires the modules together, in order:
#   1. vpc  →  2. gke  →  artifact-registry + github-wif (CI) + static IP + cloudsql  →  3. dapr + argocd
# install_addons = false: everything except Dapr and Argo CD (step 1, like AWS).
# (Ingress needs no extra controller on GKE: the built-in one creates a Google LB.)
# Each module lives in ../modules. Change behaviour with variables (terraform.tfvars).
# =============================================================================

# APIs this stack needs (enabling an already-enabled API is a no-op).
resource "google_project_service" "apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com", # project IAM
    "compute.googleapis.com",
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",    # CI: SA impersonation
    "sts.googleapis.com",               # CI: GitHub token → GCP token
    "sqladmin.googleapis.com",          # Cloud SQL
    "servicenetworking.googleapis.com", # Cloud SQL private IP (Private Service Access)
    "secretmanager.googleapis.com",     # DB credentials (read by the Dapr sidecar)
  ])
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

module "artifact_registry" {
  source     = "../modules/gcp/artifact-registry"
  name       = var.name
  region     = var.region
  depends_on = [google_project_service.apis]
}

module "github_wif" {
  source               = "../modules/gcp/github-wif"
  project_id           = var.project_id
  name                 = var.name
  region               = var.region
  github_owner_id      = var.github_owner_id
  github_repository_id = var.github_repository_id
  repository_name      = module.artifact_registry.repository_name
  depends_on           = [google_project_service.apis]
}

# Fixed public IP for the app's Google LB (GCP's answer to CloudFront's free HTTPS URL):
# the Ingress uses it by name, and <ip>.sslip.io resolves to it → Google-managed certificate.
# Created by Terraform (not the Ingress) so the IP survives app redeploys.
resource "google_compute_global_address" "app" {
  name       = "${var.name}-ip"
  depends_on = [google_project_service.apis]
}

# Managed PostgreSQL + Secret Manager credentials (read via Dapr, Workload Identity).
module "cloudsql" {
  source     = "../modules/gcp/cloudsql"
  project_id = var.project_id
  name       = var.name
  region     = var.region
  zone       = var.zone
  network_id = module.vpc.network_id
  depends_on = [google_project_service.apis]
}

# Private nodes: GKE's control plane may only reach nodes on 443/10250 by default. The Dapr
# sidecar injector webhook listens on 4000 (and the operator's conversion webhook on 19443).
resource "google_compute_firewall" "dapr_webhooks" {
  name          = "${var.name}-dapr-webhooks"
  network       = module.vpc.network_id
  source_ranges = [var.master_cidr]
  allow {
    protocol = "tcp"
    ports    = ["4000", "19443"]
  }
}

module "dapr" {
  source     = "../modules/common/dapr"
  count      = var.install_addons ? 1 : 0
  depends_on = [module.gke, google_compute_firewall.dapr_webhooks]
}

module "argocd" {
  source          = "../modules/common/argocd"
  count           = var.install_addons ? 1 : 0
  git_repo_url    = var.git_repo_url
  git_revision    = var.git_revision
  git_username    = var.git_username
  git_token       = var.git_token
  app_path        = "kustomize-apps/overlays/gcp"
  ci_rbac_subject = { kind = "User", name = module.github_wif.service_account_email }
  # Dapr first: the app's secret store Component (a Dapr CRD) is synced by Argo CD.
  depends_on = [module.gke, module.dapr]
}
