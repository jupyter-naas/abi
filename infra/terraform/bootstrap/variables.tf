variable "project" {
  type        = string
  description = "Project name used as a prefix for shared resources."
  default     = "abi"
}

variable "region" {
  type        = string
  description = "AWS region for the bootstrap stack."
}

variable "github_repos" {
  type        = list(string)
  description = "GitHub repositories (org/repo) allowed to assume the GitHub Actions role."
  default     = ["jupyter-naas/abi"]
}
