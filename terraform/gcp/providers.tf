provider "google" {
  project = var.project_id
  region  = var.region
}

# Helm and kubernetes talk to the NEW GKE cluster with your gcloud login's access token.
# Modules inherit this provider.
data "google_client_config" "current" {}

provider "helm" {
  kubernetes = {
    host                   = module.gke.cluster_endpoint
    token                  = data.google_client_config.current.access_token
    cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
  }
}

provider "kubernetes" {
  host                   = module.gke.cluster_endpoint
  token                  = data.google_client_config.current.access_token
  cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
}
