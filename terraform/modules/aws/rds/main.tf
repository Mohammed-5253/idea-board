# =============================================================================
# MODULE aws/rds – managed PostgreSQL 17 for the app + its credentials
#   - smallest instance (db.t4g.micro, 20 GiB gp3, single-AZ, no backups): cost first
#   - private subnets only, port 5432 open to the VPC (EKS pods use VPC IPs)
#   - two users, output `db` → K8s Secrets (terraform/modules/common/app-db-secret):
#       ideas_owner  master user: db-migrate Job only (bootstrap + migrations)
#       ideas_app    created by db-bootstrap: the running API (SELECT/INSERT only)
# Passwords come from random_password and are kept in the (local, git-ignored) state.
# =============================================================================
locals {
  db_name = "ideas"
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
