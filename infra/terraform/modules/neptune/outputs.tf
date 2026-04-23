output "endpoint" { value = aws_neptune_cluster.this.endpoint }
output "reader_endpoint" { value = aws_neptune_cluster.this.reader_endpoint }
output "port" { value = aws_neptune_cluster.this.port }
output "security_group_id" { value = aws_security_group.neptune.id }
