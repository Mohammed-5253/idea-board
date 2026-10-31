# =============================================================================
# MODULE gcp/cloudsql – managed PostgreSQL 17 for the app + its credentials (GCP twin of aws/rds)
#   - cheapest setup: db-f1-micro (shared core, Enterprise edition), zonal, 10 GiB HDD,
#     no backups, no public IP
#   - private IP through Private Service Access (VPC peering with Google's service network)
#   - two users, output `db` → K8s Secrets (terraform/modules/common/app-db-secret):
#       ideas_owner  db-migrate Job only (bootstrap + migrations)
#       ideas_app    created by db-bootstrap: the running API (SELECT/INSERT only)
# Passwords come from random_password and are kept in the (local, git-ignored) state.
# =============================================================================
locals {
  db_name = "ideas"
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
