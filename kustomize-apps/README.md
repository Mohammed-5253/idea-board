# kustomize-apps/

```
kustomize-apps/
├── base/                     same on every cloud
│   ├── namespace.yaml          idea-board (Pod Security "restricted")
│   ├── configmap.yaml          non-secret settings
│   ├── secret.yaml             DB passwords: owner + app user (placeholders only!)
│   ├── serviceaccounts.yaml
│   ├── postgres-statefulset.yaml · postgres-service.yaml   in-cluster PostgreSQL 17
│   ├── backend-deployment.yaml · backend-service.yaml
│   ├── frontend-deployment.yaml · frontend-service.yaml
│   └── ingress.yaml            /api → backend, / → frontend
└── overlays/
    ├── aws/                  ECR images + ALB ingress + gp3 default StorageClass
    └── gcp/                  image registry (Artifact Registry) + GKE ingress class
```

Argo CD (installed by `terraform/`) syncs `overlays/aws` on EKS and `overlays/gcp` on GKE.
Preview what will be applied: `kubectl kustomize kustomize-apps/overlays/aws`.

Replace `<AWS_ACCOUNT_ID>` / `<GCP_PROJECT_ID>` in the overlay `images:` once the registries exist.
