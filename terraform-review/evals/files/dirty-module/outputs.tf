output "lambda_arn" {
  value = aws_lambda_function.processor.arn
}

output "bucket_arn" {
  description = "The S3 bucket's ARN."
  value       = aws_s3_bucket.s3_bucket.arn
}
