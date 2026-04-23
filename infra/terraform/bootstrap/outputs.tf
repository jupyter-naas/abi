output "state_bucket" {
  value       = aws_s3_bucket.state.id
  description = "S3 bucket for Terraform remote state."
}

output "lock_table" {
  value       = aws_dynamodb_table.lock.id
  description = "DynamoDB table for state locking."
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "Role ARN that GitHub Actions assumes via OIDC."
}
