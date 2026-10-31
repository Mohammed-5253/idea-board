# kustomize-apps/

Kubernetes manifests for the app. Argo CD (installed by `terraform/`) syncs
`overlays/aws` on EKS and `overlays/gcp` on GKE.

```
kustomize-apps/
├── base/                      same on every cloud
│   ├── namespace.yaml           idea-board (Pod Security "restricted")
│   ├── configmap.yaml           non-secret settings (no DB details)
│   ├── serviceaccounts.yaml
│   ├── backend-*.yaml           FastAPI Deployment + Service; DB credentials from Secret
│   │                            backend-db (written by terraform, not in Git)
│   ├── frontend-*.yaml          nginx Deployment + Service
│   └── ingress.yaml             /api → backend, / → frontend
└── overlays/
    ├── aws/                   ECR images, ALB ingress
    └── gcp/                   Artifact Registry images, GKE ingress, static IP,
                               ManagedCertificate (<ip>.sslip.io) + HTTPS redirect
```

No database runs in the cluster. Before each sync, Argo CD runs the `db-migrate` Job
(PreSync hook, owner user from Secret `db-migrate`): `idea-board-db-bootstrap` creates the
app user, then `alembic upgrade head`. The backend only gets the app user (Secret `backend-db`).

The `images:` tags in each overlay are written by CI (`deploy(<cloud>): images <tag>`
commits). Don't edit them by hand except to roll back: set the previous tag and push,
and Argo CD redeploys it.

When you merge a long-lived branch, merge `origin/main` into it first. Otherwise an
old overlay tag can overwrite the live one.

Preview the rendered manifests:

```sh
kubectl kustomize kustomize-apps/overlays/gcp
```
