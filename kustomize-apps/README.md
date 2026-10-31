# kustomize-apps/

Kubernetes manifests for the app. Argo CD (installed by `terraform/`) syncs
`overlays/aws` on EKS and `overlays/gcp` on GKE.

```
kustomize-apps/
├── base/                      same on every cloud
│   ├── namespace.yaml           idea-board (Pod Security "restricted")
│   ├── configmap.yaml           non-secret settings (no DB details)
│   ├── serviceaccounts.yaml
│   ├── backend-*.yaml           FastAPI Deployment + Service, Dapr sidecar: DB credentials
│   │                            from the Dapr secret store (RDS / Cloud SQL, via terraform)
│   ├── frontend-*.yaml          nginx Deployment + Service
│   └── ingress.yaml             /api → backend, / → frontend
└── overlays/
    ├── aws/                   ECR images, ALB ingress, dapr-secretstore.yaml → Secrets Manager,
    │                          backend ServiceAccount annotated with the IRSA role
    └── gcp/                   Artifact Registry images, GKE ingress, static IP,
                               ManagedCertificate (<ip>.sslip.io) + HTTPS redirect,
                               dapr-secretstore.yaml → Secret Manager (Workload Identity)
```

No database runs in the cluster. On every start the backend container runs, in order:
`idea-board-db-bootstrap` (creates the app DB user), `alembic upgrade head` (as the owner
user), then uvicorn. These steps can't be init containers: Dapr's native sidecar starts
after init containers, so they couldn't reach it.

The `images:` tags in each overlay are written by CI (`deploy(<cloud>): images <tag>`
commits). Don't edit them by hand except to roll back: set the previous tag and push,
and Argo CD redeploys it.

When you merge a long-lived branch, merge `origin/main` into it first. Otherwise an
old overlay tag can overwrite the live one.

Preview the rendered manifests:

```sh
kubectl kustomize kustomize-apps/overlays/gcp
```
