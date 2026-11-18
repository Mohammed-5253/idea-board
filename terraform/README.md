# terraform/

Two roots (`aws/`, `gcp/`) that only wire modules together and set variables. All logic
lives in `modules/`. Argo CD is installed from charts vendored in this folder,
so an apply never downloads charts.

```
terraform/
├── bootstrap/{aws,gcp}      state buckets + read-only CI state identity, applied once from a laptop
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

Apply the cloud's bootstrap root first (see [State](#state-and-tfvars)).

```sh
# tfvars live outside the repo: ../terraform-state-idea-board/<root>/terraform.tfvars
cp ../terraform-state-idea-board/gcp/terraform.tfvars.example ../terraform-state-idea-board/gcp/terraform.tfvars
terraform -chdir=terraform/gcp init
terraform -chdir=terraform/gcp plan  -var-file=../../../terraform-state-idea-board/gcp/terraform.tfvars
terraform -chdir=terraform/gcp apply -var-file=../../../terraform-state-idea-board/gcp/terraform.tfvars
```

CI reads the resource list straight from the remote state (addresses only, see
`ci/state_addresses.py`), so nothing has to be committed after an apply or destroy.

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
terraform -chdir=terraform/budget/aws init && terraform -chdir=terraform/budget/aws apply -var-file=../../../../terraform-state-idea-board/budget-aws/terraform.tfvars
terraform -chdir=terraform/budget/gcp init && terraform -chdir=terraform/budget/gcp apply   # ₹2100 (≈ $25): the billing account is in INR
```

## State and tfvars

State is remote and versioned; only the two bootstrap roots keep local state:

| Root | State |
|------|-------|
| `bootstrap/aws`, `bootstrap/gcp` | local: `../terraform-state-idea-board/bootstrap-{aws,gcp}/terraform.tfstate` |
| `aws` | `s3://idea-board-tfstate-326435482847/terraform/aws/terraform.tfstate` (S3 lock file) |
| `budget/aws` | `s3://idea-board-tfstate-326435482847/terraform/budget-aws/terraform.tfstate` |
| `gcp` | `gs://idea-board-tfstate-7e93dfd0/terraform/gcp/default.tfstate` |
| `budget/gcp` | `gs://idea-board-tfstate-7e93dfd0/terraform/budget-gcp/default.tfstate` |
| `pulumi/` | `s3://idea-board-tfstate-326435482847/pulumi`, secrets in KMS `alias/idea-board-pulumi` |

Order, once per cloud:

1. Bootstrap: `terraform -chdir=terraform/bootstrap/aws init && terraform -chdir=terraform/bootstrap/aws apply`
   (GCP: `terraform -chdir=terraform/bootstrap/gcp apply -var project_id=<project>`). It creates the state bucket
   (versioned, encrypted, never public, `prevent_destroy`), the Pulumi KMS key, the account's GitHub OIDC
   provider (AWS) and the read-only `idea-board-state-reader` identity CI uses. Its local state is small and has no secrets.
2. Move each existing root's local state into the bucket: `terraform -chdir=terraform/<root> init -migrate-state`
   (answer `yes`), then delete the old `terraform.tfstate*` files in `../terraform-state-idea-board/<root>/`.
   On AWS, the OIDC provider used to belong to `terraform/aws`: before its next plan, run
   `terraform -chdir=terraform/aws state rm module.github_oidc.aws_iam_openid_connect_provider.github` and
   `terraform -chdir=terraform/bootstrap/aws import aws_iam_openid_connect_provider.github <provider arn>`
   (or apply bootstrap before the first apply of terraform/aws).
3. Set the repository variables `AWS_STATE_READER_ROLE_ARN`, `GCP_STATE_WIF_PROVIDER` and
   `GCP_STATE_SERVICE_ACCOUNT` from the bootstrap outputs.

Terraform only auto-loads `terraform.tfvars` from the root folder, so pass the external one with
`-var-file`. The S3 backend uses your normal AWS credentials (`export AWS_PROFILE=mkk`), the GCS
backend your `gcloud auth application-default login`. The state holds the DB passwords: only the
operator and the read-only CI identity can read the buckets.

## Destroy

- **GCP:** `kubectl delete ns idea-board` first. The load balancer's NEGs otherwise block
  the VPC delete (terraform then just forgets the already-deleted namespace and Secrets).
  Then run `terraform -chdir=terraform/gcp destroy -var-file=…`. Cloud SQL is destroyed without
  backups (data is lost). The Workload Identity pool ID is soft-deleted for 30 days. Recreating it within that time needs
  `gcloud iam workload-identity-pools undelete`.
- The bootstrap roots are never destroyed with the app (`prevent_destroy` on the buckets).
- **AWS:** run `terraform -chdir=terraform/aws destroy -var-file=…`. If the ALB is already gone, add
  `-var enable_cloudfront=false -var install_addons=false`. Afterwards, check for an orphaned
  `k8s-ideaboar-…` ALB, its security groups and target groups. RDS is destroyed without a
  final snapshot (data is lost).

## Updating the Argo CD chart

Copy the new upstream chart over `argo-cd/`, then delete its `redis-ha` dependency block
from `Chart.yaml`. We never enable redis-ha, and Helm refuses a declared dependency
that is missing from `charts/`.
