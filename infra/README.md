# ABI Infrastructure

Terraform + GitHub Actions for deploying ABI on AWS.

See [`docs/architecture-aws.drawio`](../docs/architecture-aws.drawio) for the target architecture and [issue #859](https://github.com/jupyter-naas/abi/issues/859) for the full rollout plan.

## Layout

```
infra/terraform/
  bootstrap/        # one-shot: TF state S3+DynamoDB, GitHub OIDC provider
  modules/
    vpc/            # 3-AZ VPC + endpoints (terraform-aws-modules/vpc/aws)
    eks/            # EKS + managed node groups + IRSA (terraform-aws-modules/eks/aws)
    ecr/            # per-workload ECR repos with lifecycle policy
    rds-postgres/   # Postgres 17 + pgvector (terraform-aws-modules/rds/aws)
    neptune/        # Neptune cluster + instance
    elasticache/    # Redis cluster-mode, encrypted in transit
    amazon-mq/      # RabbitMQ broker
    s3/             # KMS-encrypted buckets (storage/backups/logs)
    iam-irsa/       # per-workload IRSA role helper
  envs/
    dev/            # wires all modules — working reference
    staging/        # placeholder (milestone M9)
    prod/           # placeholder (milestone M9)
```

## One-time setup per AWS account

```sh
cd infra/terraform/bootstrap
terraform init
terraform apply -var region=us-east-1 -var 'github_repos=["jupyter-naas/abi"]'
```

Record the outputs — they feed the env stacks and CI:

- `state_bucket` → `TF_STATE_BUCKET` (GitHub repo variable)
- `lock_table` → `TF_LOCK_TABLE`
- `github_actions_role_arn` → `AWS_ROLE_ARN` (GitHub repo secret)

Also set `AWS_REGION`, `AWS_ACCOUNT_ID`, and optionally `PROJECT` as GitHub repo variables so CI workflows pick them up.

## Deploy via the CLI

```sh
abi deploy aws init -e dev        # prompts, scaffolds infra/terraform/envs/dev
abi deploy aws plan -e dev        # terraform plan
abi deploy aws apply -e dev       # terraform apply
abi deploy aws output -e dev      # outputs as JSON
abi deploy aws destroy -e dev     # terraform destroy (confirms)
```

The `init` subcommand asks for project name, region, AWS account ID, base domain, GitHub repo (for OIDC), Synapse toggle, and multi-tenant toggle; saves them to `.abi-aws.json` at the project root; renders templates into `infra/terraform/envs/<env>/`.

## Deploy via CI (recommended)

1. **PRs touching `infra/terraform/**`** → `terraform-plan.yml` posts the plan as a PR comment
2. **Merge to `main`** → `terraform-apply.yml` applies `dev` automatically
3. **Staging / prod** → manual `workflow_dispatch` on `terraform-apply.yml`
4. **Images** → `build-images-ecr.yml` builds on `v*` tags

All workflows authenticate via GitHub OIDC — no long-lived AWS keys in the repo.

## Key design decisions

| Decision | Rationale |
|---|---|
| Neptune over self-hosted Fuseki | Managed SPARQL, multi-AZ for free |
| `pgvector` on RDS instead of Qdrant | One less data plane to run |
| S3 instead of MinIO | Native durability, IAM, versioning |
| Amazon MQ for RabbitMQ | Managed, encrypted, no Kubernetes stateful set |
| Multi-tenant via K8s namespaces | Per-tenant IRSA role, `NetworkPolicy`, `ResourceQuota` |
| Matrix/Synapse optional | `synapse_enabled = false` by default |

## Module conventions

- Every module pins its AWS provider to `~> 5.70`
- Every stateful resource gets a dedicated security group, gated on the EKS node SG
- Master credentials → Secrets Manager, never exposed as Terraform outputs in plaintext
- All resources tagged `Project`, `Env`, `ManagedBy=terraform` via `default_tags`

## What's not here yet

- Helm charts for the workloads (follow-up PR — needs the cluster to exist first)
- App-side adapters (Neptune client, pgvector adapter, S3 adapter) — tracked in issue #859
- Staging / prod env wiring — milestone M9
- Karpenter, Managed Prometheus, FluentBit — milestone M8
