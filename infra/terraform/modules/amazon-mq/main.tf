terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.70" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

resource "random_password" "broker" {
  length  = 24
  special = false
}

resource "aws_secretsmanager_secret" "broker" {
  name = "${var.project}/${var.env}/rabbitmq"
}

resource "aws_secretsmanager_secret_version" "broker" {
  secret_id = aws_secretsmanager_secret.broker.id
  secret_string = jsonencode({
    username  = var.username
    password  = random_password.broker.result
    endpoints = aws_mq_broker.this.instances[*].endpoints
  })
}

resource "aws_security_group" "broker" {
  name   = "${var.project}-${var.env}-rabbitmq"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 5671
    to_port         = 5671
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  ingress {
    from_port       = 15671
    to_port         = 15671
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_mq_broker" "this" {
  broker_name         = "${var.project}-${var.env}"
  engine_type         = "RabbitMQ"
  engine_version      = var.engine_version
  host_instance_type  = var.host_instance_type
  deployment_mode     = var.deployment_mode
  publicly_accessible = false

  subnet_ids      = var.deployment_mode == "CLUSTER_MULTI_AZ" ? var.subnet_ids : [var.subnet_ids[0]]
  security_groups = [aws_security_group.broker.id]

  user {
    username = var.username
    password = random_password.broker.result
  }

  tags = var.tags
}
