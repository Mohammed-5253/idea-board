# =============================================================================
# MODULE aws/rds – managed PostgreSQL 17 for the app + its credentials
#   - smallest instance (db.t4g.micro, 20 GiB gp3, single-AZ, no backups): cost first
#   - private subnets only, port 5432 open to the VPC (EKS pods use VPC IPs)
#   - two Secrets Manager secrets (same least-privilege model as the in-cluster DB):
#       <name>-db-owner  master user: db-bootstrap + migrations
#       <name>-db-app    app user (created by db-bootstrap): the running API
#     Each is one JSON document {host, port, dbname, username, password, sslmode}, read
#     by the backend through the Dapr secret store (secretstores.aws.secretmanager).
#   - IAM role for the backend ServiceAccount (IRSA): read those two secrets only
# Passwords come from random_password and are kept in the (local, git-ignored) state.
# =============================================================================
locals {
  db_name = "ideas"
  secrets = {
    owner = { username = aws_db_instance.this.username, password = random_password.owner.result }
    app   = { username = "ideas_app", password = random_password.app.result }
  }
}

resource "random_password" "owner" {
  length  = 32
  special = false # RDS rejects / @ " and space; alphanumeric avoids escaping anywhere
}

resource "random_password" "app" {
  length  = 32
  special = false
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "db" {
  name        = "${var.name}-db"
  description = "PostgreSQL from inside the VPC"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
}

resource "aws_db_instance" "this" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.instance_class

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = local.db_name
  username = "ideas_owner"
  password = random_password.owner.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false

  # Demo / cost: no automated backups, no final snapshot, destroy allowed.
  backup_retention_period = 0
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true
}

resource "aws_secretsmanager_secret" "db" {
  for_each = local.secrets
  name     = "${var.name}-db-${each.key}"
  # Delete immediately on destroy, so a re-apply can reuse the same name.
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db" {
  for_each  = local.secrets
  secret_id = aws_secretsmanager_secret.db[each.key].id
  secret_string = jsonencode({
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = local.db_name
    username = each.value.username
    password = each.value.password
    sslmode  = "require" # RDS PostgreSQL 17 enforces TLS (rds.force_ssl = 1)
  })
}

resource "aws_iam_role" "backend" {
  name = "${var.name}-backend"
  # Only the backend ServiceAccount (the pod's Dapr sidecar) may assume this role.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${var.oidc_provider}:sub" = "system:serviceaccount:${var.service_account}"
          "${var.oidc_provider}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "backend" {
  name = "read-db-secrets"
  role = aws_iam_role.backend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [for s in aws_secretsmanager_secret.db : s.arn]
    }]
  })
}
