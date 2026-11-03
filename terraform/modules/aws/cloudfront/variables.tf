variable "name" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "ingress" {
  description = "<namespace>/<name> of the Ingress whose ALB is the origin."
  type        = string
}

variable "min_ttl" {
  description = "Seconds. Floor for cached objects; keep 0 so the origin's no-store/no-cache is respected."
  type        = number
  default     = 0
}

variable "default_ttl" {
  description = "Seconds. Used only when the origin sends no Cache-Control header (0 = don't cache)."
  type        = number
  default     = 0
}

variable "max_ttl" {
  description = "Seconds. Upper limit on the origin's max-age (hashed /assets/* ask for 1 year)."
  type        = number
  default     = 86400 # 1 day

  validation {
    condition     = var.max_ttl >= var.default_ttl && var.default_ttl >= var.min_ttl
    error_message = "TTLs must satisfy min_ttl <= default_ttl <= max_ttl."
  }
}
