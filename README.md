# Idea Board

A small full-stack app (React + FastAPI + PostgreSQL) that runs on Kubernetes on AWS (EKS)
or GCP (GKE). Infrastructure is Terraform, deployments are GitOps with Argo CD, and CI is
GitHub Actions with an AI assistant for reviews and failure analysis.

The database is managed PostgreSQL: RDS on AWS, Cloud SQL on GCP (smallest instances).
The backend never sees cloud-specific config. Terraform writes the DB connection details
into the Kubernetes Secret `backend-db`, which the backend reads as env vars.

## How it fits together

```
Run workflow (pick aws / gcp / aws,gcp)
   └─► GitHub Actions: test → AI infra check → build → push to the picked registries
                                    └─► commit new tag to kustomize-apps/overlays/<cloud>
                                                   │
                         Argo CD (in the cluster) ◄┘ syncs the overlay → app rolls out
                                                   │
                         CI verify-deploy waits for Synced + Healthy, opens an issue if not

backend pod ─► env from Secret backend-db (terraform) ─► RDS / Cloud SQL
```

## Repository layout

```
app/backend/        FastAPI API (GET/POST /api/ideas, /api/version), Alembic migrations
app/frontend/       React (Vite) served by nginx, proxies /api to the backend
kustomize-apps/     Kubernetes manifests: base/ + overlays/aws, overlays/gcp
terraform/          aws/ and gcp/ roots, shared modules/, vendored Helm charts
ci/ai/assist.py     AI helper used by the workflows (no third-party packages)
.github/workflows/  ci.yml (build + deploy), ai-assist.yml (AI review + release notes)
docker-compose.yml  full stack locally, including a Dapr sidecar
version.txt         app version; part of every image tag
```

## Run locally

```sh
docker compose up --build                       # http://localhost:8080
docker compose --profile tools run --rm seed    # optional sample data
docker compose down -v                          # stop and wipe the database
```

## Deploy to a cloud

Infrastructure is created in two passes from `terraform/aws` or `terraform/gcp`
(see [terraform/README.md](terraform/README.md) for the modules):

1. `install_addons = false`: network, cluster, registry, the CI identity (OIDC / WIF) and
   managed PostgreSQL, plus the app namespace and its DB Secret.
2. `install_addons = true`: Argo CD (plus the ALB controller on AWS). Argo CD then
   deploys the app from Git.

Use the wrapper instead of plain `terraform`, so the PR infra check stays current:

```sh
terraform/tf.sh gcp plan
terraform/tf.sh gcp apply     # also writes terraform/gcp/inventory.txt – commit it
```

Terraform state is local and git-ignored. The Argo CD charts live in
`terraform/argo-cd` and `terraform/argocd-app`, so an apply never
downloads charts.

Monthly budgets (about $25 per cloud, e-mail alerts only, no hard stop) are separate roots
in `terraform/budget/`.

## CI/CD

| Trigger | What happens |
|---|---|
| Pull request | Tests (ruff, pytest, eslint, vitest, build). AI comments a summary, risk score, test ideas and an infra-compatibility verdict. |
| Push to main | Tests only. Nothing is built or deployed. |
| Run workflow (manual) | The only way to release. The operator picks `aws`, `gcp` or `aws,gcp`. Tests, AI infra check for the picked clouds (stops the release on `COMPATIBLE: no`), build once, push to the picked clouds' registries only, one `deploy(<clouds>)` commit to their overlays, then verify the Argo CD rollout. |
| CI run fails | AI explains the failed log (job summary, and a PR comment when there is a PR). |
| Rollout fails | AI explains the Argo CD status, pods, events and logs in a GitHub issue assigned to the repo owner. |
| `version.txt` changes on main | GitHub Release `v<version>` with AI-written notes. |

Image tags look like `1.1.2-19b5615-12` (`version-commit-run`). Registries are immutable,
so re-running a job skips images that already exist.

PR labels: `needs-review` (AI risk 4–5) and `infra-mismatch` (the PR needs infrastructure
that is not in `terraform/aws/inventory.txt` or `terraform/gcp/inventory.txt`). Both are
advisory and never block a merge. At release time the same check runs only for the picked
clouds, against the changes since each cloud's last deploy, and does block.
Keep each `inventory.txt` current: run terraform through `terraform/tf.sh` and commit it.

## Configuration

Repository variables (Settings → Secrets and variables → Actions). The target cloud is
picked per release in the Run workflow form, not in a variable.

| Variable | Example |
|---|---|
| `AWS_REGISTRY` | `<account>.dkr.ecr.ap-south-1.amazonaws.com/idea-board` |
| `AWS_REGION` | `ap-south-1` |
| `AWS_CI_ROLE_ARN` | Terraform output `github_ci_role_arn` |
| `EKS_CLUSTER` | `idea-board` |
| `GCP_REGISTRY` | `asia-south1-docker.pkg.dev/<project>/idea-board` |
| `GCP_WIF_PROVIDER` | Terraform output `github_wif_provider` |
| `GCP_CI_SERVICE_ACCOUNT` | Terraform output `github_ci_service_account` |
| `GKE_CLUSTER`, `GKE_LOCATION` | `idea-board`, `asia-south1-a` |
| `AI_BASE_URL`, `AI_MODEL` | Any OpenAI-compatible API. Empty means OpenRouter, `openrouter/free`. |

Secret: `AI_API_KEY`. No cloud keys are stored in GitHub: CI logs in through OIDC
(AWS) and Workload Identity Federation (GCP). All AI steps are fail-open, so an AI outage
never fails the pipeline.

## Switching clouds

1. `terraform/tf.sh <cloud> apply` (both passes) and commit the inventory.
2. Run the `ci` workflow and pick the new cloud. The first run fills the empty registry.

## Tearing down

- **GCP:** `kubectl delete ns idea-board` first. The load balancer's NEGs otherwise block
  the VPC delete. Then run `terraform/tf.sh gcp destroy`.
- **AWS:** run `terraform/tf.sh aws destroy`. Afterwards, check for an orphaned ALB and
  its security groups. If the ALB is already gone, add
  `-var enable_cloudfront=false -var install_addons=false`.
- Both destroy the database without a backup, so its data is lost.
- Budgets in `terraform/budget/` are not touched by these destroys.
