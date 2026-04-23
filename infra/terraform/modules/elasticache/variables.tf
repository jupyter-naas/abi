variable "project" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "allowed_security_group_ids" { type = list(string) }

variable "engine_version" {
  type    = string
  default = "7.1"
}
variable "node_type" {
  type    = string
  default = "cache.t4g.small"
}
variable "num_cache_clusters" {
  type    = number
  default = 1
}
variable "snapshot_retention_limit" {
  type    = number
  default = 1
}
variable "tags" {
  type    = map(string)
  default = {}
}
