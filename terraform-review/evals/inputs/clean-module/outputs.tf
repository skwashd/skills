output "bucket_arn" {
  description = "The ARN of the bucket."
  value       = aws_s3_bucket.this.arn
}

output "bucket_name" {
  description = "The resolved name of the bucket (includes account regional suffix)."
  value       = aws_s3_bucket.this.id
}
