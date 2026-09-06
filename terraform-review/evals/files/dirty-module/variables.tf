variable "vpc_id" {
  type        = string
  description = "VPC where Lambda runs."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnets where Lambda runs."
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "tags" {
  description = "Tags applied to resources."
}
