output "endpoints" { value = aws_mq_broker.this.instances[*].endpoints }
output "secret_arn" { value = aws_secretsmanager_secret.broker.arn }
output "security_group_id" { value = aws_security_group.broker.id }
