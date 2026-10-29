# =============================================================================
# MODULE aws/cloudfront – free HTTPS URL (https://dxxxx.cloudfront.net) without a domain
# CloudFront terminates HTTPS with its own free *.cloudfront.net certificate and forwards
# every request to the ALB over HTTP (the ALB has no certificate: that needs a domain).
# No caching: the API is dynamic; every request goes to the app.
# The ALB is created by Kubernetes (Ingress), not Terraform → looked up by its fixed name
# (annotation alb.ingress.kubernetes.io/load-balancer-name in kustomize-apps/overlays/aws).
# =============================================================================
data "aws_lb" "app" {
  name = var.alb_name
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

# Forward headers, cookies and query strings; NOT Host (the ALB answers on its own name).
data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewerExceptHostHeader"
}

resource "aws_cloudfront_distribution" "app" {
  enabled     = true
  comment     = "${var.name} – HTTPS in front of the ALB"
  price_class = "PriceClass_200" # includes India edge locations

  origin {
    origin_id   = "alb"
    domain_name = data.aws_lb.app.dns_name
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id         = "alb"
    viewer_protocol_policy   = "redirect-to-https" # http:// → https://
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
    compress                 = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
