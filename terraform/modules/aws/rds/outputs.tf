output "endpoint" {
  value = aws_db_instance.this.address
}

output "db" {
  description = "Connection details for the backend (terraform/modules/common/app-db-secret)."
  value = {
    host           = aws_db_instance.this.address
    port           = aws_db_instance.this.port
    dbname         = local.db_name
    owner_username = aws_db_instance.this.username
    owner_password = random_password.owner.result
    app_username   = "ideas_app"
    app_password   = random_password.app.result
  }
  sensitive = true
}
