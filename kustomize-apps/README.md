# kustomize-apps/

Kubernetes manifests for the app. Argo CD (installed by `terraform/`) syncs
`overlays/aws` on EKS and `overlays/gcp` on GKE.

```
kustomize-apps/
├── base/                      same on every cloud
│   ├── namespace.yaml           idea-board (Pod Security "restricted"); terraform creates it
│   │                            first, Argo CD adopts it
│   ├── configmap.yaml           non-secret settings (no DB details)
│   ├── serviceaccounts.yaml     backend, frontend (no API tokens)
│   ├── db-migrate-job.yaml      PreSync hook: ServiceAccount (wave -1) + Job db-migrate
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
app user, then `alembic upgrade head`. Only then are the Deployments updated. The backend
only gets the app user (Secret `backend-db`). Both Secrets come from terraform
(`terraform/modules/common/app-db-secret`), never from Git.

PreSync runs before any normal resource of the same sync is applied, so the Job must not
depend on them: its ServiceAccount is a hook too, and it does not read `backend-config`
(it would see the previous revision). If the Job fails, the sync stops and the old backend
keeps running. To retry after a fix is pushed:

```sh
kubectl -n argocd patch application idea-board --type merge -p '{"operation":null}'
kubectl -n idea-board delete job db-migrate
kubectl -n argocd annotate application idea-board argocd.argoproj.io/refresh=hard --overwrite
```

The `images:` tags in each overlay are written by CI (`deploy(<cloud>): images <tag>`
commits). Don't edit them by hand except to roll back: set the previous tag and push,
and Argo CD redeploys it.

When you merge a long-lived branch, merge `origin/main` into it first. Otherwise an
old overlay tag can overwrite the live one.

Preview the rendered manifests:

```sh
kubectl kustomize kustomize-apps/overlays/gcp
```
