output "private_ip" {
  value = google_sql_database_instance.this.private_ip_address
}

output "db" {
  description = "Connection details for the backend (terraform/modules/common/app-db-secret)."
  value = {
    host           = google_sql_database_instance.this.private_ip_address
    port           = 5432
    dbname         = local.db_name
    owner_username = google_sql_user.owner.name
    owner_password = random_password.owner.result
    app_username   = "ideas_app"
    app_password   = random_password.app.result
  }
  sensitive = true
}
