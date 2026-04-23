variable "project" { type = string }
variable "env" { type = string }
variable "oidc_provider_arn" { type = string }
variable "oidc_provider_url" {
  type        = string
  description = "OIDC provider URL without the https:// prefix (e.g. oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED)."
}
variable "namespace" { type = string }
variable "service_account" { type = string }
variable "policy_arns" {
  type    = list(string)
  default = []
}
variable "inline_policy_json" {
  type    = string
  default = null
}
variable "tags" {
  type    = map(string)
  default = {}
}
