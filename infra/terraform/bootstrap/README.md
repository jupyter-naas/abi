# Bootstrap

One-shot stack that provisions the prerequisites for the rest of the Terraform code:

- S3 bucket + DynamoDB table for remote state
- GitHub OIDC provider + IAM role for keyless CI auth

This stack stores its **own** state locally — commit the resulting `terraform.tfstate` to a secure location (e.g. 1Password) or re-import on demand. After `apply`, every other stack uses the S3 backend.

## Usage

```sh
cd infra/terraform/bootstrap
terraform init
terraform apply -var region=us-east-1 -var 'github_repos=["jupyter-naas/abi"]'
```

Take note of the outputs (`state_bucket`, `lock_table`, `github_actions_role_arn`) — env stacks reference them in `backend.tf` and CI workflows reference the role ARN.
