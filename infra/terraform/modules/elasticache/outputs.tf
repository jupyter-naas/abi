output "endpoint" { value = aws_elasticache_replication_group.this.primary_endpoint_address }
output "port" { value = aws_elasticache_replication_group.this.port }
output "secret_arn" { value = aws_secretsmanager_secret.redis.arn }
output "security_group_id" { value = aws_security_group.redis.id }
