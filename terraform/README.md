# terraform/

Two roots (`aws/`, `gcp/`) that only wire modules together and set variables. All logic
lives in `modules/`. Argo CD is installed from charts vendored in this folder,
so an apply never downloads charts.

```
terraform/
├── tf.sh                    wrapper: external tfvars + terraform + refresh <cloud>/inventory.txt
├── budget/{aws,gcp}         monthly cost budgets ($25, e-mail alerts only), kept across app destroys
├── aws/                     root for AWS (ap-south-1)
├── gcp/                     root for GCP (asia-south1)
├── argo-cd/                 vendored upstream argo-cd chart 10.11.6 (Argo CD v3.5.6)
├── argocd-app/              our one-template chart: the idea-board Argo CD Application
└── modules/
    ├── aws/vpc                VPC, public + private subnets, NAT
    ├── aws/eks                EKS + managed node group (access entries, IRSA, network policies)
    ├── aws/ecr                ECR repositories: backend, frontend
    ├── aws/github-oidc        CI role for GitHub Actions (ECR push, eks:DescribeCluster)
    ├── aws/alb-controller     AWS Load Balancer Controller (Ingress → ALB) + IAM role
    ├── aws/cloudfront         free HTTPS URL (*.cloudfront.net) in front of the app ALB
    ├── aws/rds                RDS PostgreSQL 17 (db.t4g.micro), owner + app passwords
    ├── gcp/vpc                VPC, subnet with pod/service ranges, Cloud Router + NAT
    ├── gcp/gke                zonal GKE Standard, Spot node pool, Workload Identity
    ├── gcp/artifact-registry  Docker repository for backend and frontend
    ├── gcp/cloudsql           Cloud SQL PostgreSQL 17 (db-f1-micro, private IP), owner + app passwords
    ├── gcp/github-wif         CI service account for GitHub Actions (Artifact Registry push, GKE clusterViewer)
    ├── common/argocd          Argo CD + Application, plus read-only RBAC for CI verify-deploy
    └── common/app-db-secret   namespace idea-board + Secrets backend-db (app user) and db-migrate (owner)
```

## Apply

Each cloud is built in two passes:

1. `install_addons = false`: network, cluster, registry, CI identity, managed PostgreSQL
   (RDS / Cloud SQL), the app namespace and its two DB Secrets. GCP also creates the app's static IP.
2. `install_addons = true`: ALB controller (AWS only) and Argo CD. From then on, Argo CD
   deploys `kustomize-apps/overlays/<cloud>` from Git.
3. AWS only: once Argo CD has created the app ALB, apply again with
   `-var enable_cloudfront=true` for the HTTPS URL.

```sh
# tfvars + state live outside the repo: ../terraform-state-idea-board/<root>/ (see tf.sh)
cp ../terraform-state-idea-board/gcp/terraform.tfvars.example ../terraform-state-idea-board/gcp/terraform.tfvars
terraform -chdir=terraform/gcp init
terraform/tf.sh gcp plan
terraform/tf.sh gcp apply
```

`tf.sh` runs the terraform command, then writes `terraform state list` to
`<cloud>/inventory.txt`. That file holds resource addresses only, never attribute values,
so it contains no secrets. The PR infra-compatibility check in CI reads it, so commit it after every
apply or destroy. If you ran plain `terraform`, refresh it with `terraform/tf.sh <cloud> plan`.

After the first apply, copy the CI outputs (`github_ci_role_arn`, `github_wif_provider`,
`github_ci_service_account`) into the GitHub repository variables listed in the
[main README](../README.md#configuration).

Private repo: never put the Git token in a file. Export it instead:
`export TF_VAR_git_username=<user> TF_VAR_git_token=<read-only token>`.

## Budgets

Apply once per cloud; they are not part of the app stacks and survive `destroy`.
Alerts only: neither cloud can hard-cap spending, and billing data lags hours. E-mails go
out at 50%, 80% and 100% of actual spend and at 100% forecast. AWS sends them to
`alert_emails` (git-ignored tfvars), GCP to the billing account admins.

```sh
echo 'alert_emails = ["<you@example.com>"]' > ../terraform-state-idea-board/budget-aws/terraform.tfvars
terraform -chdir=terraform/budget/aws init && terraform/tf.sh budget/aws apply
terraform -chdir=terraform/budget/gcp init && terraform/tf.sh budget/gcp apply   # ₹2100 (≈ $25): the billing account is in INR
```

## State and tfvars

Both live outside the repo, next to it:

```
../terraform-state-idea-board/
├── aws/         terraform.tfstate, terraform.tfvars
├── gcp/         terraform.tfstate, terraform.tfvars, terraform.tfvars.example
├── budget-aws/  terraform.tfstate, terraform.tfvars
└── budget-gcp/  terraform.tfstate
```

Each root's `backend "local"` path points there (relative, so the repo and that folder
must stay siblings). Terraform only auto-loads `terraform.tfvars` from the root folder,
so run plan/apply/destroy/import through `tf.sh`, which passes it as `-var-file`. The
state holds the DB passwords: keep the folder private and back it up. A remote backend
(S3 / GCS) can replace it later in `versions.tf`.

## Destroy

- **GCP:** `kubectl delete ns idea-board` first. The load balancer's NEGs otherwise block
  the VPC delete (terraform then just forgets the already-deleted namespace and Secrets).
  Then run `terraform/tf.sh gcp destroy`. Cloud SQL is destroyed without
  backups (data is lost). The Workload Identity pool ID is soft-deleted for 30 days. Recreating it within that time needs
  `gcloud iam workload-identity-pools undelete`.
- **AWS:** run `terraform/tf.sh aws destroy`. If the ALB is already gone, add
  `-var enable_cloudfront=false -var install_addons=false`. Afterwards, check for an orphaned
  `k8s-ideaboar-…` ALB, its security groups and target groups. RDS is destroyed without a
  final snapshot (data is lost).

## Updating the Argo CD chart

Copy the new upstream chart over `argo-cd/`, then delete its `redis-ha` dependency block
from `Chart.yaml`. We never enable redis-ha, and Helm refuses a declared dependency
that is missing from `charts/`.
