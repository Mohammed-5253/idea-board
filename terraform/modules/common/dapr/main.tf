# =============================================================================
# MODULE common/dapr – Dapr control plane (operator, sidecar injector, sentry, ...)
# Pods annotated `dapr.io/enabled: "true"` get a Dapr sidecar injected.
# =============================================================================
resource "helm_release" "dapr" {
  name             = "dapr"
  repository       = "https://dapr.github.io/helm-charts"
  chart            = "dapr"
  version          = "1.18.9"
  namespace        = "dapr-system"
  create_namespace = true
  atomic           = true
  timeout          = 600

  values = [file("${path.module}/values.yaml")]
}
