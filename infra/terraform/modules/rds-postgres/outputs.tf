output "endpoint" { value = module.db.db_instance_address }
output "port" { value = module.db.db_instance_port }
output "database_name" { value = var.database_name }
output "secret_arn" { value = aws_secretsmanager_secret.db.arn }
output "security_group_id" { value = aws_security_group.db.id }
