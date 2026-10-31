output "cluster_name" {
  value = module.eks.cluster_name
}

output "kubeconfig_command" {
  description = "Run this to use kubectl against the new cluster."
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region} --profile ${var.aws_profile} --alias ${module.eks.cluster_name}"
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "argocd_ui" {
  value = "kubectl -n argocd port-forward svc/argocd-server 8080:80  →  http://localhost:8080 (user admin)"
}

output "ecr_repository_urls" {
  description = "Push images here (CI) – used in kustomize-apps/overlays/aws images:."
  value       = module.ecr.repository_urls
}

output "github_ci_role_arn" {
  description = "Set as GitHub repository variable AWS_CI_ROLE_ARN."
  value       = module.github_oidc.role_arn
}

output "app_url" {
  description = "Public HTTPS URL of the app (CloudFront)."
  value       = var.enable_cloudfront ? module.cloudfront[0].url : null
}

output "db_endpoint" {
  value = module.rds.endpoint
}
