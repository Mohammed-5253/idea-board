output "cluster_name" {
  value = module.gke.cluster_name
}

output "kubeconfig_command" {
  description = "Run this to use kubectl against the new cluster."
  value       = "gcloud container clusters get-credentials ${module.gke.cluster_name} --zone ${var.zone} --project ${var.project_id}"
}

output "vpc_name" {
  value = module.vpc.network_name
}

output "argocd_ui" {
  value = "kubectl -n argocd port-forward svc/argocd-server 8080:80  →  http://localhost:8080 (user admin)"
}

output "registry_url" {
  description = "Push images here (CI) – used in kustomize-apps/overlays/gcp images:."
  value       = module.artifact_registry.registry_url
}

output "github_wif_provider" {
  description = "Set as GitHub repository variable GCP_WIF_PROVIDER."
  value       = module.github_wif.provider_name
}

output "github_ci_service_account" {
  description = "Set as GitHub repository variable GCP_CI_SERVICE_ACCOUNT."
  value       = module.github_wif.service_account_email
}

output "app_ip" {
  description = "Static IP of the app LB → put it into kustomize-apps/overlays/gcp/managed-certificate.yaml."
  value       = google_compute_global_address.app.address
}

output "app_url" {
  description = "Public HTTPS URL (works once the managed certificate is ACTIVE, ~15-60 min after the Ingress)."
  value       = "https://${replace(google_compute_global_address.app.address, ".", "-")}.sslip.io"
}

output "db_private_ip" {
  value = module.cloudsql.private_ip
}
