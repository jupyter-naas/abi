terraform {
  backend "s3" {
    # Filled in by `terraform init -backend-config=...` (see Makefile / CI).
    # bucket         = "abi-tfstate-<account-id>-<region>"
    # key            = "envs/dev/terraform.tfstate"
    # region         = "<region>"
    # dynamodb_table = "abi-tflock"
    # encrypt        = true
  }
}
