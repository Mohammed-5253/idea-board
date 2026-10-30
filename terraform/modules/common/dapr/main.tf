# =============================================================================
# MODULE common/dapr – Dapr control plane (same on EKS and GKE)
# Chart vendored in the repo (terraform/dapr, upstream 1.18.9 = the daprd version in
# docker-compose): no download at apply time.
# The app reads its DB credentials from the Dapr sidecar (secret store component in
# kustomize-apps/overlays/<cloud>), so the backend holds no cloud SDK.
# =============================================================================
resource "helm_release" "dapr" {
  name             = "dapr"
  chart            = "${path.module}/../../../dapr"
  namespace        = "dapr-system"
  create_namespace = true
  atomic           = true
  timeout          = 600

  values = [yamlencode({
    global = {
      ha        = { enabled = false }
      actors    = { enabled = false } # no placement service: we use no actors/workflows
      scheduler = { enabled = false } # no scheduler (it needs a 16Gi PVC): we use no jobs API
    }
    dapr_sidecar_injector = {
      # daprd as a native sidecar (init container with restartPolicy Always): it starts
      # BEFORE the backend's init containers, so db-bootstrap and migrate can read secrets too.
      nativeSidecar = true
      # Pod Security "restricted" (namespace idea-board) requires dropping all capabilities.
      sidecarDropALLCapabilities = true
    }
  })]
}
