"""Idea Board on AWS: Pulumi port of terraform/aws (VPC, ECR, CI role, RDS, DB Secret, CloudFront).

EKS, the ALB controller and Argo CD stay out; the Kubernetes provider uses the `kubeconfig` config.
"""

import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s

from idea_infra.app_db_secret import create_app_db_secret
from idea_infra.cloudfront import create_cloudfront
from idea_infra.ecr import create_ecr
from idea_infra.github_oidc import create_github_oidc
from idea_infra.rds import create_rds
from idea_infra.vpc import create_vpc

cfg = pulumi.Config()
name = cfg.get("name") or "idea-board"
region = cfg.get("region") or "ap-south-1"
aws_profile = cfg.get("aws_profile") or "mkk"
vpc_cidr = cfg.get("vpc_cidr") or "10.10.0.0/16"
az_count = cfg.get_int("az_count") or 2
github_repo = cfg.get("github_repo") or "Mohammed-5253@106949872/idea-board@1438023010"
enable_cloudfront = cfg.get_bool("enable_cloudfront") or False
cf_default_ttl = cfg.get_int("cloudfront_default_ttl")
cf_max_ttl = cfg.get_int("cloudfront_max_ttl")

provider = aws.Provider(
    "aws",
    region=region,
    profile=aws_profile,
    default_tags={"tags": {"project": name, "managed-by": "terraform"}},
)
opts = pulumi.ResourceOptions(provider=provider)
k8s_provider = k8s.Provider("k8s", kubeconfig=cfg.require("kubeconfig"))

vpc = create_vpc(name, vpc_cidr, az_count, opts)
ecr = create_ecr(name, opts)
oidc = create_github_oidc(name, github_repo, ecr["repository_arns"], opts)
rds = create_rds(name, vpc["vpc_id"], vpc_cidr, vpc["private_subnet_ids"], opts)
create_app_db_secret(rds["db"], pulumi.ResourceOptions(provider=k8s_provider))

app_url = None
if enable_cloudfront:
    app_url = create_cloudfront(
        name, name, "idea-board/idea-board", opts,
        default_ttl=0 if cf_default_ttl is None else cf_default_ttl,
        max_ttl=86400 if cf_max_ttl is None else cf_max_ttl,
    )["url"]

pulumi.export("vpc_id", vpc["vpc_id"])
pulumi.export("ecr_repository_urls", ecr["repository_urls"])
pulumi.export("github_ci_role_arn", oidc["role_arn"])
pulumi.export("app_url", app_url)
pulumi.export("db_endpoint", rds["endpoint"])
