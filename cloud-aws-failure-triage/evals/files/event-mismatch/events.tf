resource "aws_cloudwatch_event_rule" "bucket_created" {
  name           = "provisioner-bucket-created"
  description    = "Start the bucket provisioning state machine when a bucket create is requested"
  event_bus_name = aws_cloudwatch_event_bus.provisioner.name

  event_pattern = jsonencode({
    source        = ["sandy.manager"]
    "detail-type" = ["bucket_create_requested"]
    detail = {
      resource_type = ["s3_bucket"]
    }
  })
}

resource "aws_cloudwatch_event_target" "bucket_created_sfn" {
  rule           = aws_cloudwatch_event_rule.bucket_created.name
  event_bus_name = aws_cloudwatch_event_bus.provisioner.name
  arn            = aws_sfn_state_machine.create_bucket.arn
  role_arn       = aws_iam_role.events_to_sfn.arn
}
