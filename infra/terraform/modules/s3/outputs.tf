output "buckets" {
  value = { for k, b in aws_s3_bucket.this : k => b.bucket }
}
output "bucket_arns" {
  value = { for k, b in aws_s3_bucket.this : k => b.arn }
}
output "kms_key_arn" { value = aws_kms_key.this.arn }
