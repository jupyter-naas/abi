variable "project" { type = string }
variable "env" { type = string }
variable "region" { type = string }
variable "vpc_cidr" {
  type    = string
  default = "10.10.0.0/16"
}
variable "synapse_enabled" {
  type    = bool
  default = false
}
variable "multi_tenant" {
  type    = bool
  default = true
}
