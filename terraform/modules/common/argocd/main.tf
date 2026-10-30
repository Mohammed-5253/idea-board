# =============================================================================
# MODULE common/argocd – Argo CD + one Application (same on EKS and GKE)
# Both charts are vendored in the repo (terraform/argo-cd, terraform/argocd-app): no
# download from argoproj.github.io at apply time (it kept timing out).
# Terraform installs Argo CD once. From then on Argo CD deploys the app by watching
# `app_path` (kustomize-apps/overlays/<cloud>) in Git: push to Git = deploy.
# =============================================================================
locals {
  # Read-only access for CI verify-deploy (ci.yml): Argo CD Application status + pods,
  # events and logs. No Secrets. Shipped through the chart's extraObjects.
  ci_rbac_values = {
    extraObjects = [
      {
        apiVersion = "rbac.authorization.k8s.io/v1"
        kind       = "ClusterRole"
        metadata   = { name = "idea-board-ci-read" }
        rules = [
          { apiGroups = ["argoproj.io"], resources = ["applications"], verbs = ["get", "list"] },
          { apiGroups = [""], resources = ["pods", "pods/log", "events"], verbs = ["get", "list"] },
        ]
      },
      {
        apiVersion = "rbac.authorization.k8s.io/v1"
        kind       = "ClusterRoleBinding"
        metadata   = { name = "idea-board-ci-read" }
        roleRef    = { apiGroup = "rbac.authorization.k8s.io", kind = "ClusterRole", name = "idea-board-ci-read" }
        subjects   = [merge(var.ci_rbac_subject, { apiGroup = "rbac.authorization.k8s.io" })]
      },
    ]
  }

  # Private repo → Argo CD needs read credentials. Public repo → nothing.
  repo_values = var.git_token == "" ? {} : {
    configs = {
      repositories = {
        idea-board = {
          url      = var.git_repo_url
          username = var.git_username
          password = var.git_token
        }
      }
    }
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  chart            = "${path.module}/../../../argo-cd" # vendored argo-cd 10.11.6 (Argo CD v3.5.6)
  namespace        = "argocd"
  create_namespace = true
  atomic           = true
  timeout          = 600

  values = [
    file("${path.module}/values.yaml"),
    yamlencode(local.repo_values),
    yamlencode(local.ci_rbac_values),
  ]
}

resource "helm_release" "app" {
  name      = "idea-board-app"
  chart     = "${path.module}/../../../argocd-app" # our own one-Application chart
  namespace = "argocd"

  values = [yamlencode({
    repoURL        = var.git_repo_url
    targetRevision = var.git_revision
    path           = var.app_path
  })]

  depends_on = [helm_release.argocd]
}
