# =============================================================================
# MODULE common/app-db-secret – app namespace + DB Secrets (same on EKS and GKE)
#   backend-db  app user only (SELECT/INSERT): envFrom of the backend Deployment
#   db-migrate  owner + app user: envFrom of the db-migrate Job (Argo CD PreSync hook),
#               which creates the app role and runs Alembic before the Deployment updates
# Least privilege: neither pod gets a ServiceAccount token, so the backend cannot read
# db-migrate through the Kubernetes API.
# Terraform owns the namespace so the Secrets exist before Argo CD syncs the app; Argo CD
# also applies base/namespace.yaml (same object, adopted), hence ignore_changes.
# =============================================================================
locals {
  conn = {
    DB_HOST     = var.db.host
    DB_PORT     = tostring(var.db.port)
    DB_NAME     = var.db.dbname
    DB_SSLMODE  = "require" # RDS and Cloud SQL both enforce TLS
    DB_USER     = var.db.app_username
    DB_PASSWORD = var.db.app_password
  }
}

resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = var.namespace
    labels = {
      "pod-security.kubernetes.io/enforce"         = "restricted"
      "pod-security.kubernetes.io/enforce-version" = "latest"
      "pod-security.kubernetes.io/warn"            = "restricted"
    }
  }

  lifecycle {
    ignore_changes = [metadata[0].labels, metadata[0].annotations]
  }
}

resource "kubernetes_secret_v1" "backend" {
  metadata {
    name      = "backend-db"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  data = local.conn
}

resource "kubernetes_secret_v1" "migrate" {
  metadata {
    name      = "db-migrate"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }
  # DB_USER/DB_PASSWORD = the app role db-bootstrap creates; BOOTSTRAP_OWNER_* = the owner.
  data = merge(local.conn, {
    BOOTSTRAP_OWNER_USER     = var.db.owner_username
    BOOTSTRAP_OWNER_PASSWORD = var.db.owner_password
  })
}
