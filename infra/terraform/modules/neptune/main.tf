terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

resource "aws_security_group" "neptune" {
  name        = "${var.project}-${var.env}-neptune"
  description = "Neptune access from EKS"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8182
    to_port         = 8182
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

resource "aws_neptune_subnet_group" "this" {
  name       = "${var.project}-${var.env}-neptune"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_neptune_cluster" "this" {
  cluster_identifier                  = "${var.project}-${var.env}"
  engine                              = "neptune"
  engine_version                      = var.engine_version
  neptune_subnet_group_name           = aws_neptune_subnet_group.this.name
  vpc_security_group_ids              = [aws_security_group.neptune.id]
  iam_database_authentication_enabled = true
  storage_encrypted                   = true
  apply_immediately                   = true
  skip_final_snapshot                 = !var.deletion_protection
  deletion_protection                 = var.deletion_protection
  backup_retention_period             = var.backup_retention_period

  tags = var.tags
}

resource "aws_neptune_cluster_instance" "this" {
  count              = var.instance_count
  cluster_identifier = aws_neptune_cluster.this.id
  instance_class     = var.instance_class
  engine             = "neptune"
  apply_immediately  = true
  tags               = var.tags
}
