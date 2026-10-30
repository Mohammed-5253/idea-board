# =============================================================================
# MODULE gcp/gke – GKE Standard (zonal) + one node pool
#   * Private nodes, public control-plane endpoint (auth = IAM).
#   * Workload Identity: pods get GCP permissions via their ServiceAccount, never the node's.
#   * Dataplane V2 (eBPF): enforces NetworkPolicy.
#   * Nodes run as a minimal service account (NOT the default Compute SA with Editor).
# =============================================================================
resource "google_service_account" "nodes" {
  account_id   = "${var.name}-nodes"
  display_name = "GKE nodes (${var.name})"
}

resource "google_project_iam_member" "nodes" {
  for_each = toset([
    "roles/container.defaultNodeServiceAccount", # logs, metrics (Google's minimal node role)
    "roles/artifactregistry.reader",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

resource "google_container_cluster" "this" {
  name     = var.name
  location = var.zone

  # Default pool: create with 1 node, then delete; ours is below. Works on every version.
  # shortcut: deprecated (warning) – once the channel is >= 1.36.4-gke.1469000, drop
  # remove_default_node_pool and set initial_node_count = 0.
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = var.network_id
  subnetwork = var.subnet_id
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  release_channel {
    channel = "REGULAR"
  }
  min_master_version = var.kubernetes_version # null = channel default

  datapath_provider = "ADVANCED_DATAPATH"

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_cidr
  }

  dynamic "master_authorized_networks_config" {
    for_each = length(var.public_access_cidrs) > 0 ? [1] : []
    content {
      dynamic "cidr_blocks" {
        for_each = var.public_access_cidrs
        content {
          cidr_block   = cidr_blocks.value
          display_name = "allowed-${cidr_blocks.key}"
        }
      }
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  enable_shielded_nodes = true
  deletion_protection   = false # demo: destroyable
}

resource "google_container_node_pool" "default" {
  name       = "default"
  cluster    = google_container_cluster.this.id
  location   = var.zone
  node_count = var.node_count

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = var.machine_type
    spot            = var.spot
    disk_size_gb    = 30
    disk_type       = "pd-balanced"
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"] # IAM roles decide access

    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }

  # Nodes need their roles before they start (image pulls, logging).
  depends_on = [google_project_iam_member.nodes]
}
