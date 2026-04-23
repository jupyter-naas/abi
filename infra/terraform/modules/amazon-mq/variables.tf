variable "project" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_security_group_ids" { type = list(string) }

variable "engine_version" {
  type    = string
  default = "3.13"
}
variable "host_instance_type" {
  type    = string
  default = "mq.t3.micro"
}
variable "deployment_mode" {
  type    = string
  default = "SINGLE_INSTANCE"
}
variable "username" {
  type    = string
  default = "abi"
}
variable "tags" {
  type    = map(string)
  default = {}
}
