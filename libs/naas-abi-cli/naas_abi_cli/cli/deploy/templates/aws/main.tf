provider "aws" {
  region = var.region
  default_tags {
    tags = local.tags
  }
}

locals {
  tags = {
    Project   = var.project
    Env       = var.env
    ManagedBy = "terraform"
  }
}

module "vpc" {
  source   = "../../modules/vpc"
  project  = var.project
  env      = var.env
  cidr     = var.vpc_cidr
  az_count = 3
  tags     = local.tags
}

module "eks" {
  source          = "../../modules/eks"
  project         = var.project
  env             = var.env
  vpc_id          = module.vpc.vpc_id
  private_subnets = module.vpc.private_subnets
  tags            = local.tags
}

module "ecr" {
  source  = "../../modules/ecr"
  project = var.project
  tags    = local.tags
}

module "s3" {
  source  = "../../modules/s3"
  project = var.project
  env     = var.env
  tags    = local.tags
}

module "rds_postgres" {
  source                     = "../../modules/rds-postgres"
  project                    = var.project
  env                        = var.env
  vpc_id                     = module.vpc.vpc_id
  db_subnet_group_name       = module.vpc.database_subnet_group
  allowed_security_group_ids = [module.eks.node_security_group_id]
  multi_az                   = var.env == "prod"
  deletion_protection        = var.env == "prod"
  tags                       = local.tags
}

module "neptune" {
  source                     = "../../modules/neptune"
  project                    = var.project
  env                        = var.env
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.database_subnets
  allowed_security_group_ids = [module.eks.node_security_group_id]
  instance_count             = var.env == "prod" ? 2 : 1
  deletion_protection        = var.env == "prod"
  tags                       = local.tags
}

module "redis" {
  source                     = "../../modules/elasticache"
  project                    = var.project
  env                        = var.env
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnets
  allowed_security_group_ids = [module.eks.node_security_group_id]
  num_cache_clusters         = var.env == "prod" ? 2 : 1
  tags                       = local.tags
}

module "rabbitmq" {
  source                     = "../../modules/amazon-mq"
  project                    = var.project
  env                        = var.env
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_subnets
  allowed_security_group_ids = [module.eks.node_security_group_id]
  deployment_mode            = var.env == "prod" ? "CLUSTER_MULTI_AZ" : "SINGLE_INSTANCE"
  tags                       = local.tags
}

data "aws_iam_policy_document" "abi_api" {
  statement {
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [
      module.rds_postgres.secret_arn,
      module.redis.secret_arn,
      module.rabbitmq.secret_arn,
    ]
  }
  statement {
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = [
      module.s3.bucket_arns["storage"],
      "${module.s3.bucket_arns["storage"]}/*",
    ]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [module.s3.kms_key_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["*"]
  }
}

module "irsa_abi_api" {
  source             = "../../modules/iam-irsa"
  project            = var.project
  env                = var.env
  oidc_provider_arn  = module.eks.oidc_provider_arn
  oidc_provider_url  = module.eks.oidc_provider_url
  namespace          = "abi"
  service_account    = "abi-api"
  inline_policy_json = data.aws_iam_policy_document.abi_api.json
  tags               = local.tags
}

module "platform_addons" {
  source            = "../../modules/platform-addons"
  project           = var.project
  env               = var.env
  region            = var.region
  vpc_id            = module.vpc.vpc_id
  cluster_name      = module.eks.cluster_name
  oidc_provider_arn = module.eks.oidc_provider_arn
  tags              = local.tags
}
