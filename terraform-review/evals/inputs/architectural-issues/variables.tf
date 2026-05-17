variable "subnet_ids" {
  type        = list(string)
  description = "Subnets where the application runs."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all taggable resources."
}

variable "vpc_id" {
  type        = string
  description = "VPC ID for the security group."
}
