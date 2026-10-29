provider "aws" {
  region  = var.region
  profile = var.aws_profile
  default_tags {
    tags = {
      project    = var.name
      managed-by = "terraform"
    }
  }
}

# Helm talks to the NEW EKS cluster with a short-lived token from `aws eks get-token`
# (needs AWS CLI v2 on the machine running terraform). Modules inherit this provider.
provider "helm" {
  kubernetes = {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_ca_certificate)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.region, "--profile", var.aws_profile]
    }
  }
}
