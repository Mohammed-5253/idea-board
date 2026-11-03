# =============================================================================
# MODULE aws/cloudfront – free HTTPS URL (https://dxxxx.cloudfront.net) without a domain
# CloudFront terminates HTTPS with its own free *.cloudfront.net certificate and forwards
# every request to the ALB over HTTP (the ALB has no certificate: that needs a domain).
# Caching: /api/* is never cached (dynamic). Everything else follows the ORIGIN's
#   Cache-Control (nginx): /assets/* max-age=1y → cached up to max_ttl; index.html no-cache
#   and /config.js no-store → not cached. TTLs come from variables (min/default/max_ttl).
# The ALB is created by Kubernetes (Ingress), not Terraform → looked up by the tag the AWS
# Load Balancer Controller puts on it (ingress.k8s.aws/stack = <namespace>/<ingress name>).
# The controller never renames an existing ALB, so a name lookup is unreliable.
# =============================================================================
data "aws_lb" "app" {
  tags = {
    "ingress.k8s.aws/stack" = var.ingress
    "elbv2.k8s.aws/cluster" = var.cluster_name
  }
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

# Static content: honour the origin's Cache-Control, bounded by our TTLs.
#   min_ttl     floor: keep 0, or CloudFront caches even no-store/no-cache responses
#   default_ttl used only when the origin sends NO Cache-Control (0 = don't cache those)
#   max_ttl     cap on the origin's max-age (also how long a bad asset can live at the edge)
# Cache key = path only (no cookies/headers/query strings) → high hit ratio.
resource "aws_cloudfront_cache_policy" "static" {
  name        = "${var.name}-static"
  comment     = "${var.name}: honour origin Cache-Control"
  min_ttl     = var.min_ttl
  default_ttl = var.default_ttl
  max_ttl     = var.max_ttl

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_gzip   = true # needed for `compress = true` with a cache policy
    enable_accept_encoding_brotli = true
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
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
    cache_policy_id          = aws_cloudfront_cache_policy.static.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
    compress                 = true
  }

  # API: never cached – ideas change on every POST. Matched before the default behavior.
  ordered_cache_behavior {
    path_pattern             = "/api/*"
    target_origin_id         = "alb"
    viewer_protocol_policy   = "redirect-to-https"
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
