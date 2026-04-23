variable "project" { type = string }
variable "env" { type = string }
variable "bucket_names" {
  type    = list(string)
  default = ["storage", "backups", "logs"]
}
variable "tags" {
  type    = map(string)
  default = {}
}
