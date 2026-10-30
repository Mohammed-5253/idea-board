# terraform/

Two roots (`aws/`, `gcp/`) that only wire modules together and set variables. All logic
lives in `modules/`. Argo CD is installed from charts vendored in this folder, so an apply
never downloads charts.

```
terraform/
├── tf.sh                    wrapper: terraform + refresh <cloud>/inventory.txt
├── aws/                     root for AWS (ap-south-1)
├── gcp/                     root for GCP (asia-south1)
├── argo-cd/                 vendored upstream argo-cd chart 10.11.6 (Argo CD v3.5.6)
├── argocd-app/              our one-template chart: the idea-board Argo CD Application
├── dapr/                    vendored upstream dapr chart 1.18.9 (no scheduler/placement)
└── modules/
    ├── aws/vpc                VPC, public + private subnets, NAT
    ├── aws/eks                EKS + managed node group (access entries, IRSA, network policies)
    ├── aws/ecr                ECR repositories: backend, frontend
    ├── aws/github-oidc        CI role for GitHub Actions (ECR push, eks:DescribeCluster)
    ├── aws/alb-controller     AWS Load Balancer Controller (Ingress → ALB) + IAM role
    ├── aws/cloudfront         free HTTPS URL (*.cloudfront.net) in front of the app ALB
    ├── aws/rds                RDS PostgreSQL 17 (db.t4g.micro), DB secrets in Secrets Manager, backend IRSA role
    ├── gcp/vpc                VPC, subnet with pod/service ranges, Cloud Router + NAT
    ├── gcp/gke                zonal GKE Standard, Spot node pool, Workload Identity
    ├── gcp/artifact-registry  Docker repository for backend and frontend
    ├── gcp/cloudsql           Cloud SQL PostgreSQL 17 (db-f1-micro, private IP), DB secrets in Secret Manager
    ├── gcp/github-wif         CI service account for GitHub Actions (Artifact Registry push, GKE clusterViewer)
    ├── common/argocd          Argo CD + Application, plus read-only RBAC for CI verify-deploy
    └── common/dapr            Dapr control plane (sidecar injector, native sidecar mode)
```

## Apply

Each cloud is built in two passes:

1. `install_addons = false`: network, cluster, registry, CI identity
   managed PostgreSQL (RDS / Cloud SQL) and its secrets. GCP also creates the app's static IP.
2. `install_addons = true`: ALB controller (AWS only), Dapr and Argo CD. From then on, Argo CD
   deploys `kustomize-apps/overlays/<cloud>` from Git.

```sh
cd terraform/gcp && cp terraform.tfvars.example terraform.tfvars   # AWS: defaults in variables.tf
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

## State

State is local (`<cloud>/terraform.tfstate`, git-ignored). A remote backend
(S3 / GCS) can be added in `versions.tf` later.

## Destroy

- **GCP:** `kubectl delete ns idea-board` first. The load balancer's NEGs otherwise block
  the VPC delete. Cloud SQL is destroyed without backups (data is lost). Then run `terraform/tf.sh gcp destroy`. The Workload Identity pool ID
  is soft-deleted for 30 days. Recreating it within that time needs
  `gcloud iam workload-identity-pools undelete`.
- **AWS:** run `terraform/tf.sh aws destroy`. If the ALB is already gone, add
  `-var enable_cloudfront=false -var install_addons=false`. Afterwards, check for an orphaned
  `k8s-ideaboar-…` ALB, its security groups and target groups. RDS is destroyed without a
  final snapshot (data is lost) and its secrets are deleted immediately.

## Updating the Dapr chart

`helm pull dapr --repo https://dapr.github.io/helm-charts --version <v> --untar`, copy it
over `dapr/`, and bump the daprd image in `docker-compose.yml` to the same version.

## Updating the Argo CD chart

Copy the new upstream chart over `argo-cd/`, then delete its `redis-ha` dependency block
from `Chart.yaml`. We never enable redis-ha, and Helm refuses a declared dependency
that is missing from `charts/`.
