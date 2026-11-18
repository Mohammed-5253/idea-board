output "state_bucket" {
  value = aws_s3_bucket.state.bucket
}

output "state_reader_role_arn" {
  description = "Repository variable AWS_STATE_READER_ROLE_ARN."
  value       = aws_iam_role.state_reader.arn
}

output "pulumi_kms_key_arn" {
  value = aws_kms_key.pulumi.arn
}

output "github_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}
