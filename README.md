# Idea Board

A small full-stack app (React + FastAPI + PostgreSQL) deployed to Kubernetes on AWS (EKS) and GCP (GKE).

```
idea-board/
├── app/              backend (FastAPI) + frontend (React/nginx), each with its Dockerfile
├── terraform/        infrastructure: aws/ and gcp/ roots + reusable modules/
├── kustomize-apps/   Kubernetes manifests: base/ + overlays/aws, overlays/gcp
├── docker-compose.yml  run everything locally: `docker compose up`
├── dapr/             local Dapr component for docker-compose
└── version.txt       app version (SemVer) → CI image tag, e.g. backend:1.0.0
```

- Local: `docker compose up` → http://localhost:8080
- Cloud: see `terraform/README.md`, then Argo CD syncs `kustomize-apps/overlays/<cloud>`.
