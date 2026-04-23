# End-to-end deployment runbook

This walks through a full `dev` deployment from a clean AWS account to a
running stack exposed via an ALB.

## Prerequisites (local)

- `terraform` ≥ 1.6
- `helm` ≥ 3.11
- `kubectl`
- `aws` CLI ≥ 2
- `docker` with `buildx`
- `abi` CLI (`uv sync` at the repo root, then `uv run abi ...`)

## Prerequisites (AWS)

- Access to an account with permission to create VPC/EKS/RDS/Neptune/etc. A fresh sandbox account with `AdministratorAccess` is ideal.
- `aws sso login` (or `AWS_PROFILE=...`) — the `abi` CLI uses the default provider chain.
- Service quotas — for `dev` defaults: ≥ 5 EIPs (NAT + ALB + ...), ≥ 3 RDS instances (you only need 1, quota is at account level).

## Steps

### 1. Bootstrap (once per account)

```sh
cd infra/terraform/bootstrap
terraform init
terraform apply -var region=us-east-1 -var 'github_repos=["jupyter-naas/abi"]'
```

Note the outputs — especially `state_bucket`, `lock_table`, `github_actions_role_arn`.

### 2. Scaffold the dev env

```sh
cd -   # back to repo root
abi deploy aws init -e dev
# Answers the prompts; writes infra/terraform/envs/dev/ and .abi-aws.json
```

### 3. Apply infrastructure

```sh
make -C infra apply ENV=dev
# Takes ~20-25 min on a fresh account (EKS + RDS + Neptune dominate).
```

### 4. Configure kubectl + build/push images

```sh
make -C infra kubeconfig ENV=dev
make -C infra build-push ENV=dev IMAGE_TAG=dev-$(git rev-parse --short HEAD)
# Today this only builds `abi` and `nexus-web` — other services are TODO
# (placeholders in build-push).
```

### 5. Deploy the apps

```sh
make -C infra deploy-apps ENV=dev \
  IMAGE_TAG=dev-$(git rev-parse --short HEAD) \
  NAMESPACE=abi
```

### 6. Find the URL

```sh
kubectl -n abi get ingress abi \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
# http://<hostname>/api/       → ABI REST API
# http://<hostname>/           → Nexus web
```

The ALB provisions in ~2-3 minutes after `deploy-apps` completes. The hostname may return 503 until target groups go healthy — check pod readiness with `kubectl -n abi get pods`.

### 7. (Optional) Enable a custom domain

```sh
# Create an ACM cert for your domain, point Route 53 at the ALB, then:
helm upgrade abi infra/helm/abi \
  --reuse-values \
  --set ingress.certificateArn=arn:aws:acm:us-east-1:<account>:certificate/<id> \
  --set-string "ingress.hosts[0].host=dev.abi.example.com"
```

Or — do it via Terraform in a follow-up (ACM + Route 53 modules are listed as follow-ups in `infra/README.md`).

## Teardown

```sh
# Remove Helm releases first so finalizers don't block terraform destroy.
helm -n abi uninstall abi
make -C infra destroy ENV=dev
```

## Known gaps (to address before production)

- `pgvector` extension must be enabled manually (`CREATE EXTENSION vector;`) on the RDS instance — future work: `null_resource` + psql from a bastion.
- Only `abi` and `nexus-web` images have build contexts registered in `abi deploy aws build-push`. Add more as Dockerfiles appear.
- No ACM/Route 53 Terraform module yet — ingress ACM cert is passed manually.
- Staging/prod environments are scaffolded as placeholders only.
- Synapse is rendered but untested end-to-end (disabled by default).
