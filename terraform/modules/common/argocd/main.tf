# =============================================================================
# MODULE common/argocd – Argo CD + one Application (same on EKS and GKE)
# Terraform installs Argo CD once. From then on Argo CD deploys the app by watching
# `app_path` (kustomize-apps/overlays/<cloud>) in Git: push to Git = deploy.
# =============================================================================
locals {
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
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "10.10.5"
  namespace        = "argocd"
  create_namespace = true
  atomic           = true
  timeout          = 600

  values = [
    file("${path.module}/values.yaml"),
    yamlencode(local.repo_values),
  ]
}

resource "helm_release" "app" {
  name       = "idea-board-app"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argocd-apps"
  version    = "2.0.7"
  namespace  = "argocd"

  values = [yamlencode({
    applications = {
      idea-board = {
        namespace = "argocd"
        project   = "default"
        source = {
          repoURL        = var.git_repo_url
          targetRevision = var.git_revision
          path           = var.app_path
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "idea-board"
        }
        syncPolicy = {
          automated = { prune = true, selfHeal = true }
        }
      }
    }
  })]

  depends_on = [helm_release.argocd]
}
