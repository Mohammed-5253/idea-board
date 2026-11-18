# =============================================================================
# ROOT terraform/bootstrap/aws – applied ONCE from the operator's laptop, before any other AWS root
#   1. S3 bucket for Terraform state (terraform/aws, terraform/budget/aws) and Pulumi state
#   2. KMS key that encrypts Pulumi stack secrets (awskms://alias/idea-board-pulumi)
#   3. The account's ONLY GitHub OIDC provider (terraform/aws and pulumi/ look it up)
#   4. idea-board-state-reader: read-only role CI uses to list resources in the state
# =============================================================================
locals {
  state_bucket = "idea-board-tfstate-326435482847" # fixed: backend blocks can't use variables
}

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket

  lifecycle {
    prevent_destroy = true
  }
}

# Every apply writes a new version → a broken state can be rolled back.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

# AWS-managed aws/s3 key: anyone allowed to read the object can decrypt it, so the
# state reader needs no extra KMS permission.
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.state]
}

resource "aws_kms_key" "pulumi" {
  description         = "Pulumi secrets for ${var.name}"
  enable_key_rotation = true
}

resource "aws_kms_alias" "pulumi" {
  name          = "alias/${var.name}-pulumi"
  target_key_id = aws_kms_key.pulumi.key_id
}

# One per account and URL: terraform/aws and pulumi/ find it with a data source.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

resource "aws_iam_role" "state_reader" {
  name = "idea-board-state-reader"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        # Any branch (release check) and pull requests (PR review) of our repo only.
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:${var.github_repo}:ref:refs/heads/*",
            "repo:${var.github_repo}:pull_request",
          ]
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "state_read" {
  name = "terraform-state-read"
  role = aws_iam_role.state_reader.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "ListTerraformState"
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.state.arn
        Condition = { StringLike = { "s3:prefix" = ["terraform/*"] } }
      },
      {
        Sid      = "ReadTerraformState"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.state.arn}/terraform/*"
      },
    ]
  })
}
