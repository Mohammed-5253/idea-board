# =============================================================================
# MODULE gcp/cloudsql – managed PostgreSQL 17 for the app + its credentials (GCP twin of aws/rds)
#   - cheapest setup: db-f1-micro (shared core, Enterprise edition), zonal, 10 GiB HDD,
#     no backups, no public IP
#   - private IP through Private Service Access (VPC peering with Google's service network)
#   - two Secret Manager secrets (same model as AWS):
#       <name>-db-owner  owner user: db-bootstrap + migrations
#       <name>-db-app    app user (created by db-bootstrap): the running API
#     Each is one JSON document {host, port, dbname, username, password, sslmode}, read
#     by the backend through the Dapr secret store (secretstores.gcp.secretmanager).
#   - Workload Identity: the backend KSA principal may read those two secrets (no GSA)
# Passwords come from random_password and are kept in the (local, git-ignored) state.
# =============================================================================
locals {
  db_name = "ideas"
  secrets = {
    owner = { username = google_sql_user.owner.name, password = random_password.owner.result }
    app   = { username = "ideas_app", password = random_password.app.result }
  }
  # GKE Workload Identity principal of the backend Kubernetes ServiceAccount.
  backend_principal = "principal://iam.googleapis.com/projects/${data.google_project.this.number}/locations/global/workloadIdentityPools/${var.project_id}.svc.id.goog/subject/ns/${var.k8s_namespace}/sa/${var.k8s_service_account}"
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "random_password" "owner" {
  length  = 32
  special = false
}

resource "random_password" "app" {
  length  = 32
  special = false
}

# Private Service Access: an IP range in our VPC peered to Google's network, where
# Cloud SQL gets its private IP.
resource "google_compute_global_address" "psa" {
  name          = "${var.name}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 24
  network       = var.network_id
}

resource "google_service_networking_connection" "psa" {
  network                 = var.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.psa.name]
  # Let terraform destroy remove the peering (default ABANDON leaves it behind).
  deletion_policy = "DELETE"
}

resource "google_sql_database_instance" "this" {
  name             = var.name
  database_version = "POSTGRES_17"
  region           = var.region

  settings {
    edition           = "ENTERPRISE" # PG16+ defaults to ENTERPRISE_PLUS, which has no shared-core tiers
    tier              = var.tier
    availability_type = "ZONAL"
    disk_type         = "PD_HDD"
    disk_size         = 10
    disk_autoresize   = false

    location_preference {
      zone = var.zone
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
      ssl_mode        = "ENCRYPTED_ONLY" # TLS required, no client certificates
    }

    # Demo / cost: no automated backups or point-in-time recovery.
    backup_configuration {
      enabled = false
    }
  }

  deletion_protection = false
  depends_on          = [google_service_networking_connection.psa]
}

resource "google_sql_database" "ideas" {
  name     = local.db_name
  instance = google_sql_database_instance.this.name
}

# Users created through the API get the cloudsqlsuperuser role (CREATEROLE, CREATEDB).
resource "google_sql_user" "owner" {
  name     = "ideas_owner"
  instance = google_sql_database_instance.this.name
  password = random_password.owner.result
}

resource "google_secret_manager_secret" "db" {
  for_each  = local.secrets
  secret_id = "${var.name}-db-${each.key}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db" {
  for_each = local.secrets
  secret   = google_secret_manager_secret.db[each.key].id
  secret_data = jsonencode({
    host     = google_sql_database_instance.this.private_ip_address
    port     = 5432
    dbname   = local.db_name
    username = each.value.username
    password = each.value.password
    sslmode  = "require"
  })
}

resource "google_secret_manager_secret_iam_member" "backend" {
  for_each  = local.secrets
  secret_id = google_secret_manager_secret.db[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.backend_principal
}
