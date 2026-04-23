variable "project" { type = string }
variable "env" { type = string }
variable "identifier" {
  type    = string
  default = "main"
}
variable "vpc_id" { type = string }
variable "db_subnet_group_name" { type = string }
variable "allowed_security_group_ids" { type = list(string) }

variable "engine_version" {
  type    = string
  default = "17.2"
}
variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}
variable "allocated_storage" {
  type    = number
  default = 50
}
variable "max_allocated_storage" {
  type    = number
  default = 200
}
variable "database_name" {
  type    = string
  default = "abi"
}
variable "master_username" {
  type    = string
  default = "abi"
}
variable "multi_az" {
  type    = bool
  default = false
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
