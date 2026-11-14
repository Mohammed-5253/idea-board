"""CloudFront (free *.cloudfront.net HTTPS) in front of the Ingress ALB; /api/* never cached."""

import pulumi
import pulumi_aws as aws

ALL_METHODS = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]


def create_cloudfront(
    name: str, cluster_name: str, ingress: str, opts: pulumi.ResourceOptions,
    min_ttl: int = 0, default_ttl: int = 0, max_ttl: int = 86400,
) -> dict:
    if not (max_ttl >= default_ttl and default_ttl >= min_ttl):
        raise ValueError("TTLs must satisfy min_ttl <= default_ttl <= max_ttl.")
    invoke = pulumi.InvokeOptions(provider=opts.provider)
    alb = aws.lb.get_load_balancer_output(
        tags={"ingress.k8s.aws/stack": ingress, "elbv2.k8s.aws/cluster": cluster_name}, opts=invoke
    )
    disabled = aws.cloudfront.get_cache_policy_output(name="Managed-CachingDisabled", opts=invoke)
    all_viewer = aws.cloudfront.get_origin_request_policy_output(
        name="Managed-AllViewerExceptHostHeader", opts=invoke
    )
    static = aws.cloudfront.CachePolicy(
        "static",
        name=f"{name}-static",
        comment=f"{name}: honour origin Cache-Control",
        min_ttl=min_ttl,
        default_ttl=default_ttl,
        max_ttl=max_ttl,
        parameters_in_cache_key_and_forwarded_to_origin={
            "enable_accept_encoding_gzip": True,
            "enable_accept_encoding_brotli": True,
            "cookies_config": {"cookie_behavior": "none"},
            "headers_config": {"header_behavior": "none"},
            "query_strings_config": {"query_string_behavior": "none"},
        },
        opts=opts,
    )
    behavior = {
        "target_origin_id": "alb",
        "viewer_protocol_policy": "redirect-to-https",
        "allowed_methods": ALL_METHODS,
        "cached_methods": ["GET", "HEAD"],
        "origin_request_policy_id": all_viewer.id,
        "compress": True,
    }
    dist = aws.cloudfront.Distribution(
        "app",
        enabled=True,
        comment=f"{name} – HTTPS in front of the ALB",
        price_class="PriceClass_200",
        origins=[{
            "origin_id": "alb",
            "domain_name": alb.dns_name,
            "custom_origin_config": {
                "http_port": 80,
                "https_port": 443,
                "origin_protocol_policy": "http-only",
                "origin_ssl_protocols": ["TLSv1.2"],
            },
        }],
        default_cache_behavior={**behavior, "cache_policy_id": static.id},
        ordered_cache_behaviors=[
            {**behavior, "path_pattern": "/api/*", "cache_policy_id": disabled.id}
        ],
        restrictions={"geo_restriction": {"restriction_type": "none"}},
        viewer_certificate={"cloudfront_default_certificate": True},
        opts=opts,
    )
    return {"url": dist.domain_name.apply(lambda d: f"https://{d}")}
