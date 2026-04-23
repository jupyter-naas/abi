variable "project" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_security_group_ids" { type = list(string) }

variable "engine_version" {
  type    = string
  default = "1.3.2.0"
}
variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}
variable "instance_count" {
  type    = number
  default = 1
}
variable "backup_retention_period" {
  type    = number
  default = 7
}
variable "deletion_protection" {
  type    = bool
  default = false
}
variable "tags" {
  type    = map(string)
  default = {}
}
