variable "project" {
  type    = string
  default = "abi"
}
variable "env" {
  type    = string
  default = "dev"
}
variable "region" { type = string }

variable "vpc_cidr" {
  type    = string
  default = "10.10.0.0/16"
}

variable "synapse_enabled" {
  type    = bool
  default = false
}
