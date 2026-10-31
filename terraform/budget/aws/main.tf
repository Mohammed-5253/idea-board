# =============================================================================
# ROOT terraform/budget/aws – monthly cost budget with e-mail alerts (alerts only, no auto-stop)
# Separate from terraform/aws on purpose: `terraform destroy` of the app stack keeps it.
# AWS has no hard spending cap and billing data lags 8-24 h, so the alert can fire after the
# limit is already passed. The forecast alert warns before that happens.
# First 2 budgets per account are free.
# =============================================================================
terraform {
  required_version = ">= 1.11.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.70.0, < 7.0.0"
    }
  }
}

provider "aws" {
  region  = "ap-south-1" # Budgets is global; any region works
  profile = var.aws_profile
}

variable "aws_profile" {
  type    = string
  default = "mkk"
}

variable "limit_usd" {
  type    = number
  default = 25
}

variable "alert_emails" {
  description = "Who gets the alerts (set in terraform.tfvars, git-ignored)."
  type        = list(string)
}

resource "aws_budgets_budget" "monthly" {
  name         = "idea-board-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Actual spend at 50 / 80 / 100 % of the limit.
  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = var.alert_emails
    }
  }

  # Month-end forecast above the limit → early warning.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.alert_emails
  }
}
