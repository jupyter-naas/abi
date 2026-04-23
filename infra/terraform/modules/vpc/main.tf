terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name = "${var.project}-${var.env}"
  cidr = var.cidr

  azs              = local.azs
  public_subnets   = [for i, _ in local.azs : cidrsubnet(var.cidr, 4, i)]
  private_subnets  = [for i, _ in local.azs : cidrsubnet(var.cidr, 4, i + 4)]
  database_subnets = [for i, _ in local.azs : cidrsubnet(var.cidr, 4, i + 8)]

  enable_nat_gateway     = true
  single_nat_gateway     = var.env != "prod"
  one_nat_gateway_per_az = var.env == "prod"

  enable_dns_hostnames = true
  enable_dns_support   = true

  create_database_subnet_group = true

  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }

  tags = var.tags
}

module "vpc_endpoints" {
  source  = "terraform-aws-modules/vpc/aws//modules/vpc-endpoints"
  version = "~> 5.13"

  vpc_id = module.vpc.vpc_id

  endpoints = {
    s3 = {
      service         = "s3"
      service_type    = "Gateway"
      route_table_ids = module.vpc.private_route_table_ids
    }
  }

  tags = var.tags
}
