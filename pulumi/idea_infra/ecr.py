"""ECR repositories <name>/<image>: immutable tags, scan on push, keep newest 20 images."""

import json

import pulumi
import pulumi_aws as aws

LIFECYCLE = json.dumps(
    {
        "rules": [
            {
                "rulePriority": 1,
                "description": "Keep the newest 20 images",
                "selection": {
                    "tagStatus": "any",
                    "countType": "imageCountMoreThan",
                    "countNumber": 20,
                },
                "action": {"type": "expire"},
            }
        ]
    }
)


def create_ecr(name: str, opts: pulumi.ResourceOptions, images=("backend", "frontend")) -> dict:
    repos = {}
    for image in sorted(set(images)):  # Terraform toset(): unique, sorted keys
        repo = aws.ecr.Repository(
            f"ecr-{image}",
            name=f"{name}/{image}",
            image_tag_mutability="IMMUTABLE",
            force_delete=True,
            image_scanning_configuration={"scan_on_push": True},
            encryption_configurations=[{"encryption_type": "AES256"}],
            opts=opts,
        )
        aws.ecr.LifecyclePolicy(f"ecr-{image}", repository=repo.name, policy=LIFECYCLE, opts=opts)
        repos[image] = repo
    return {
        "repository_urls": {k: r.repository_url for k, r in repos.items()},
        "repository_arns": [r.arn for r in repos.values()],
    }
