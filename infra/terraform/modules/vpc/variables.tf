variable "project" { type = string }
variable "env" { type = string }
variable "cidr" {
  type    = string
  default = "10.0.0.0/16"
}
variable "az_count" {
  type    = number
  default = 3
}
variable "tags" {
  type    = map(string)
  default = {}
}
