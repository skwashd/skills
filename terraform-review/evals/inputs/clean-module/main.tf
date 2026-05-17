data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  bucket_prefix = "${var.app_name}-${var.environment}"
}

resource "aws_s3_bucket" "this" {
  bucket = format("%s-%s-%s-an",
    local.bucket_prefix,
    data.aws_caller_identity.current.account_id,
    data.aws_region.current.region,
  )
  bucket_namespace = "account-regional"

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
