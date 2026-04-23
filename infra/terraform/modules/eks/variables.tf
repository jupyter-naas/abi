variable "project" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "private_subnets" { type = list(string) }

variable "cluster_version" {
  type    = string
  default = "1.30"
}

variable "cluster_endpoint_public_access" {
  type    = bool
  default = true
}

variable "general_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}
variable "general_min_size" { default = 2 }
variable "general_max_size" { default = 6 }
variable "general_desired_size" { default = 2 }

variable "memory_instance_types" {
  type    = list(string)
  default = ["r6i.xlarge"]
}
variable "memory_max_size" { default = 3 }
variable "memory_desired_size" { default = 0 }

variable "tags" {
  type    = map(string)
  default = {}
}
