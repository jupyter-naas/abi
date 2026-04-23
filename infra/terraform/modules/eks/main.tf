terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.24"

  cluster_name    = "${var.project}-${var.env}"
  cluster_version = var.cluster_version

  vpc_id                         = var.vpc_id
  subnet_ids                     = var.private_subnets
  cluster_endpoint_public_access = var.cluster_endpoint_public_access

  enable_irsa                              = true
  enable_cluster_creator_admin_permissions = true

  cluster_addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = {}
    aws-ebs-csi-driver     = {}
    eks-pod-identity-agent = {}
  }

  eks_managed_node_groups = {
    general = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.general_instance_types
      min_size       = var.general_min_size
      max_size       = var.general_max_size
      desired_size   = var.general_desired_size
      labels         = { workload = "general" }
    }
    memory = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.memory_instance_types
      min_size       = 0
      max_size       = var.memory_max_size
      desired_size   = var.memory_desired_size
      labels         = { workload = "memory" }
      taints = [{
        key    = "workload"
        value  = "memory"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = var.tags
}
