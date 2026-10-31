variable "namespace" {
  type    = string
  default = "idea-board"
}

variable "db" {
  description = "Connection details of the managed PostgreSQL (aws/rds or gcp/cloudsql output `db`)."
  type = object({
    host           = string
    port           = number
    dbname         = string
    owner_username = string
    owner_password = string
    app_username   = string
    app_password   = string
  })
  sensitive = true
}
