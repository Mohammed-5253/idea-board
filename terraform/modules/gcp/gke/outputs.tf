output "cluster_name" {
  value = google_container_cluster.this.name
}

output "cluster_endpoint" {
  value = "https://${google_container_cluster.this.endpoint}"
}

output "cluster_ca_certificate" {
  description = "Base64-encoded."
  value       = google_container_cluster.this.master_auth[0].cluster_ca_certificate
}

output "node_pool_id" {
  description = "Depend on this to wait until nodes exist."
  value       = google_container_node_pool.default.id
}
