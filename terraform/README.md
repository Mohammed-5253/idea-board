# terraform/

Modular layout: **modules** hold the code, the two **roots** (`aws/`, `gcp/`) only call
modules and set variables.

```
terraform/
├── aws/                 root for AWS  (main.tf calls the modules below)
├── gcp/                 root for GCP
└── modules/
    ├── aws/vpc              VPC, public + private subnets, NAT
    ├── aws/eks              EKS + managed node group (IRSA, network policies) + EBS CSI driver
    ├── aws/ecr              ECR repositories: backend, frontend
    ├── aws/github-oidc      GitHub Actions → AWS login without keys (CI role, ECR push only)
    ├── aws/cloudfront       free HTTPS URL (*.cloudfront.net) in front of the app ALB
    ├── aws/alb-controller   AWS Load Balancer Controller (Ingress → ALB) + its IAM role
    ├── gcp/vpc              VPC, subnet (+ pod/service ranges), Cloud Router + NAT
    ├── gcp/gke              GKE Standard (zonal) + node pool (Workload Identity)
    ├── gcp/artifact-registry  Artifact Registry Docker repo (images backend, frontend)
    ├── gcp/github-wif       GitHub Actions → GCP login without keys (WIF + CI service account)
    └── common/argocd        Argo CD (same on both clouds) + Application → kustomize-apps/overlays/<cloud>
```

Order inside each root: network → cluster → (ALB controller on AWS) → Argo CD.
Step 1 (`install_addons = false`): network + cluster + registry + CI identity
(GCP: + the app's static IP). Step 2 (`true`): Argo CD.
After that, Argo CD deploys the app from `kustomize-apps/` in Git.

## Run

```bash
cd terraform/aws        # or terraform/gcp
cp terraform.tfvars.example terraform.tfvars   # fill in your values (git-ignored)
terraform init
terraform plan
terraform apply
```

State is local for now (`terraform.tfstate`, git-ignored). A remote backend (S3 / GCS)
can be added later in `versions.tf`.

Not here yet (later steps): database, container registry, Dapr, Karpenter, cloud-agnostic layer.
