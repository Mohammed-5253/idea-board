# =============================================================================
# MODULE gcp/vpc – VPC + subnet + Cloud NAT
# GCP differences vs AWS: the VPC is global, subnets are regional (no per-AZ subnets),
# and pods/services get IPs from SECONDARY ranges of the node subnet (VPC-native GKE).
# Nodes are private (no public IPs) → Cloud NAT gives them outbound internet.
# =============================================================================
resource "google_compute_network" "this" {
  name                    = var.name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

}

resource "google_compute_subnetwork" "nodes" {
  name                     = "${var.name}-nodes"
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = var.subnet_cidr
  private_ip_google_access = true # reach Google APIs without public IPs

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}

resource "google_compute_router" "this" {
  name    = "${var.name}-router"
  region  = var.region
  network = google_compute_network.this.id
}

resource "google_compute_router_nat" "this" {
  name                               = "${var.name}-nat"
  router                             = google_compute_router.this.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# The private control plane must reach the Dapr sidecar-injector webhook on the nodes.
resource "google_compute_firewall" "dapr_webhook" {
  name          = "${var.name}-dapr-webhook"
  network       = google_compute_network.this.id
  direction     = "INGRESS"
  source_ranges = [var.master_cidr]
  allow {
    protocol = "tcp"
    ports    = ["4000"]
  }
}
