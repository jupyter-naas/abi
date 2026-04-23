terraform {
  backend "s3" {
    # bucket / key / region / dynamodb_table are supplied at `terraform init`
    # time by `abi deploy aws plan|apply` (or the CI workflows).
  }
}
