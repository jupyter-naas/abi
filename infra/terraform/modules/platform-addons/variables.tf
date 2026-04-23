variable "project" { type = string }
variable "env" { type = string }
variable "region" { type = string }
variable "vpc_id" { type = string }
variable "cluster_name" { type = string }
variable "oidc_provider_arn" { type = string }

variable "lb_controller_chart_version" {
  type    = string
  default = "1.9.2"
}

variable "external_secrets_chart_version" {
  type    = string
  default = "0.10.5"
}

variable "tags" {
  type    = map(string)
  default = {}
}
