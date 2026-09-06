variable "app_name" {
  type        = string
  description = "Short name of the application; used as the bucket prefix."
}

variable "environment" {
  type        = string
  description = "Deployment environment, e.g. prod, staging, dev."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all taggable resources. Must include an 'environment' key."

  validation {
    condition     = contains(keys(var.tags), "environment")
    error_message = "tags must contain an 'environment' key."
  }
}
