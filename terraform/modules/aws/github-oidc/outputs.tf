output "role_arn" {
  description = "Put this in the GitHub repo variable AWS_CI_ROLE_ARN."
  value       = aws_iam_role.ci.arn
}
