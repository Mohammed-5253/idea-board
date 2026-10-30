output "private_ip" {
  value = google_sql_database_instance.this.private_ip_address
}

output "secret_ids" {
  value = [for s in google_secret_manager_secret.db : s.secret_id]
}
