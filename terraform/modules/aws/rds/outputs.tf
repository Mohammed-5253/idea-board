output "endpoint" {
  value = aws_db_instance.this.address
}

output "backend_role_arn" {
  description = "IRSA role of the backend ServiceAccount (kustomize-apps/overlays/aws)."
  value       = aws_iam_role.backend.arn
}

output "secret_names" {
  value = [for s in aws_secretsmanager_secret.db : s.name]
}
