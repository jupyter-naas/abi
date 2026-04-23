terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.70" }
    helm       = { source = "hashicorp/helm", version = "~> 2.16" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.33" }
  }
}

# ------------------------------------------------------------------
# AWS Load Balancer Controller — IRSA + Helm release
# ------------------------------------------------------------------

module "lb_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.44"

  role_name                              = "${var.project}-${var.env}-aws-lb-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = var.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }

  tags = var.tags
}

resource "helm_release" "aws_lb_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = var.lb_controller_chart_version

  set {
    name  = "clusterName"
    value = var.cluster_name
  }
  set {
    name  = "serviceAccount.create"
    value = "true"
  }
  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.lb_controller_irsa.iam_role_arn
  }
  set {
    name  = "region"
    value = var.region
  }
  set {
    name  = "vpcId"
    value = var.vpc_id
  }
}

# ------------------------------------------------------------------
# External Secrets Operator — IRSA + Helm release
# ------------------------------------------------------------------

data "aws_iam_policy_document" "external_secrets" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:ListSecrets",
    ]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "external_secrets" {
  name   = "${var.project}-${var.env}-external-secrets"
  policy = data.aws_iam_policy_document.external_secrets.json
  tags   = var.tags
}

module "external_secrets_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.44"

  role_name = "${var.project}-${var.env}-external-secrets"

  # ESO installs its SA as `external-secrets` in `external-secrets` namespace.
  # The per-tenant abi chart references this role ARN via the
  # `externalSecrets.serviceAccountRoleArn` value for its own SA.
  role_policy_arns = {
    main = aws_iam_policy.external_secrets.arn
  }

  oidc_providers = {
    main = {
      provider_arn = var.oidc_provider_arn
      namespace_service_accounts = [
        "external-secrets:external-secrets",
      ]
    }
  }

  tags = var.tags
}

resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  namespace        = "external-secrets"
  version          = var.external_secrets_chart_version
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.external_secrets_irsa.iam_role_arn
  }
}

# Role that the per-tenant ABI chart's own external-secrets ServiceAccount
# assumes to read secrets — narrower than the ESO controller role.
data "aws_iam_policy_document" "tenant_secrets_read" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project}/${var.env}/*",
    ]
  }
}

data "aws_caller_identity" "current" {}

resource "aws_iam_policy" "tenant_secrets_read" {
  name   = "${var.project}-${var.env}-tenant-secrets-read"
  policy = data.aws_iam_policy_document.tenant_secrets_read.json
  tags   = var.tags
}

module "tenant_secrets_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.44"

  role_name = "${var.project}-${var.env}-tenant-secrets"

  role_policy_arns = {
    main = aws_iam_policy.tenant_secrets_read.arn
  }

  oidc_providers = {
    main = {
      provider_arn = var.oidc_provider_arn
      # Wildcard namespace — works for any tenant namespace
      namespace_service_accounts = [
        "*:external-secrets-sa",
      ]
    }
  }

  tags = var.tags
}
