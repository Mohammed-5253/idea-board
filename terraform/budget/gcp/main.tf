# =============================================================================
# ROOT terraform/budget/gcp – monthly budget for the project, alerts only (no auto-stop)
# Separate from terraform/gcp on purpose: `terraform destroy` of the app stack keeps it.
# GCP budgets never stop spending and billing data lags a few hours.
# E-mails go to the billing account's admins/users (default IAM recipients), i.e. you.
# The amount is in the BILLING ACCOUNT's currency (check: Billing → Account management).
# =============================================================================
terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 8.7.0, < 9.0.0"
    }
  }
}

# The Budgets API needs a quota project when called with your gcloud user credentials.
provider "google" {
  project               = var.project_id
  billing_project       = var.project_id
  user_project_override = true
}

variable "project_id" {
  type    = string
  default = "project-7e93dfd0-5ad8-4ac0-aec"
}

variable "billing_account" {
  description = "Billing account of the project (gcloud billing projects describe <project>)."
  type        = string
  default     = "0159CC-A0A8F0-27D01F" # Mkk-Billing
}

variable "limit" {
  description = "In `currency`. 2100 INR ≈ 25 USD."
  type        = number
  default     = 2100
}

variable "currency" {
  description = "Must equal the billing account's currency, or the API rejects the budget."
  type        = string
  default     = "INR"
}

resource "google_project_service" "budgets" {
  service            = "billingbudgets.googleapis.com"
  disable_on_destroy = false
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account
  display_name    = "idea-board-monthly"

  budget_filter {
    projects        = ["projects/${data.google_project.this.number}"]
    calendar_period = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = var.currency
      units         = tostring(var.limit)
    }
  }

  # Actual spend at 50 / 80 / 100 %, plus a month-end forecast above the limit.
  dynamic "threshold_rules" {
    for_each = [0.5, 0.8, 1.0]
    content {
      threshold_percent = threshold_rules.value
    }
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  depends_on = [google_project_service.budgets]
}
