"""CI role for GitHub Actions (push to our ECR repos, describe our EKS cluster).

The account's GitHub OIDC provider belongs to terraform/bootstrap/aws (an account can't
hold two), so it is looked up here, like data.aws_iam_openid_connect_provider in terraform/aws.
"""

import json

import pulumi
import pulumi_aws as aws


def create_github_oidc(name: str, github_repo: str, ecr_repository_arns, opts) -> dict:
    provider = aws.iam.get_open_id_connect_provider_output(
        url="https://token.actions.githubusercontent.com",
        opts=pulumi.InvokeOutputOptions(provider=opts.provider),
    )
    role = aws.iam.Role(
        "ci",
        name=f"{name}-github-ci",
        assume_role_policy=provider.arn.apply(
            lambda arn: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Federated": arn},
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {
                                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                                    "token.actions.githubusercontent.com:sub": f"repo:{github_repo}:ref:refs/heads/main",
                                }
                            },
                        }
                    ],
                }
            )
        ),
        opts=opts,
    )
    aws.iam.RolePolicy(
        "ecr-push",
        name="ecr-push",
        role=role.id,
        policy=pulumi.Output.all(*ecr_repository_arns).apply(
            lambda arns: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {"Sid": "EcrLogin", "Effect": "Allow",
                         "Action": "ecr:GetAuthorizationToken", "Resource": "*"},
                        {
                            "Sid": "PushPullOurRepos",
                            "Effect": "Allow",
                            "Action": [
                                "ecr:BatchCheckLayerAvailability",
                                "ecr:InitiateLayerUpload",
                                "ecr:UploadLayerPart",
                                "ecr:CompleteLayerUpload",
                                "ecr:PutImage",
                                "ecr:BatchGetImage",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:DescribeImages",
                            ],
                            "Resource": list(arns),
                        },
                        {"Sid": "EksKubeconfig", "Effect": "Allow", "Action": "eks:DescribeCluster",
                         "Resource": f"arn:aws:eks:*:*:cluster/{name}"},
                    ],
                }
            )
        ),
        opts=opts,
    )
    return {"role_arn": role.arn}
