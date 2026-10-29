output "url" {
  value = "https://${aws_cloudfront_distribution.app.domain_name}"
}
