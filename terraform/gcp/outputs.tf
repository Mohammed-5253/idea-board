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
