# Convenience wrappers around `abi deploy aws`. Variables can be overridden
# on the command line, e.g. `make apply ENV=staging`.

ENV ?= dev
IMAGE_TAG ?= latest
NAMESPACE ?= abi

.PHONY: bootstrap init plan apply output destroy kubeconfig \
        ecr-login build-push deploy-apps e2e

bootstrap:
	cd terraform/bootstrap && terraform init && terraform apply

init:
	abi deploy aws init -e $(ENV)

plan:
	abi deploy aws plan -e $(ENV)

apply:
	abi deploy aws apply -e $(ENV) --auto-approve

output:
	abi deploy aws output -e $(ENV)

destroy:
	abi deploy aws destroy -e $(ENV)

kubeconfig:
	abi deploy aws kubeconfig -e $(ENV)

ecr-login:
	abi deploy aws ecr-login -e $(ENV)

build-push: ecr-login
	abi deploy aws build-push -e $(ENV) --image-tag $(IMAGE_TAG)

deploy-apps:
	abi deploy aws deploy-apps -e $(ENV) --image-tag $(IMAGE_TAG) --namespace $(NAMESPACE)

# End-to-end: assumes bootstrap + init already ran once.
e2e: apply kubeconfig build-push deploy-apps
	@echo ""
	@echo "=== Ingress hostname (once ALB is provisioned) ==="
	kubectl -n $(NAMESPACE) get ingress abi \
	  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' && echo
