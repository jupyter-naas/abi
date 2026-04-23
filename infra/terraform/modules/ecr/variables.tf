variable "project" { type = string }
variable "repositories" {
  type    = list(string)
  default = ["abi", "dagster", "mcp-server", "nexus-web", "service-portal"]
}
variable "keep_last_images" {
  type    = number
  default = 30
}
variable "tags" {
  type    = map(string)
  default = {}
}
