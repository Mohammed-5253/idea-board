# =============================================================================
# MODULE aws/ecr – private container registries (one per image)
#   <name>/backend, <name>/frontend  →  <account>.dkr.ecr.<region>.amazonaws.com/<name>/<image>
# * IMMUTABLE tags: a tag (CI uses the git commit SHA) can never be overwritten, so what
#   was tested is exactly what runs.
# * scan_on_push: free basic vulnerability scan of every pushed image.
# * Lifecycle: keep the newest 20 images per repo (storage cost stays tiny).
# * force_delete: `terraform destroy` also removes images (demo convenience).
# EKS nodes can pull without extra setup: their IAM role has AmazonEC2ContainerRegistryReadOnly.
# =============================================================================
resource "aws_ecr_repository" "this" {
  for_each = toset(var.images)

  name                 = "${var.name}/${each.value}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the newest 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}
