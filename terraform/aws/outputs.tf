output "cluster_name" {
  value = module.eks.cluster_name
}

output "kubeconfig_command" {
  description = "Run this to use kubectl against the new cluster."
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "argocd_ui" {
  value = "kubectl -n argocd port-forward svc/argocd-server 8080:80  →  http://localhost:8080 (user admin)"
}
