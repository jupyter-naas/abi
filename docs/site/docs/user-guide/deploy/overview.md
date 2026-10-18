---
sidebar_position: 1
title: "Deploy ABI"
---

# Deploy ABI

A project made by `abi new project` runs the same way everywhere: an engine, a NATS broker,
remote modules, Nexus, and the backing services your config points at. What changes between a laptop
and production is the config file and who runs the pieces.

## Pick a way to run it

| You want | Use | Guide |
|---|---|---|
| To develop, on your machine, without Docker | `abi dev up` | [Quickstart](/user-guide/get-started/quickstart) |
| The full stack on one machine | `abi deploy local`, `abi stack start` | [Deploy with Docker](/user-guide/deploy/local-docker) |
| One server with a domain and certificates | `abi deploy dokploy` | [Deploy with Dokploy](/user-guide/deploy/dokploy) |
| Your cluster, a container platform or Naas Spaces; a managed NATS | `config.remote.yaml`, `abi deploy naas` | [Production and remote deployments](/user-guide/deploy/production) |
| No outbound network | Local models, an offline bundle | [Air-gapped deployment](/user-guide/deploy/air-gapped) |

[Deployment models](/user-guide/deploy/deployment-models) compares them, from local development to
self-hosted production and the enterprise reference architectures.

## Before production

- **Secrets.** Nothing in the config is a secret: `{{ secret.X }}` resolves from the environment or a
  secret adapter. See [Add secrets to production](/user-guide/deploy/add_secrets_to_production).
- **Security.** There is no default password, sign-up is off, and the broker must stay private. See
  [Security and compliance](/user-guide/deploy/security-compliance) and the
  [security model](/developer-guide/architecture/security).
- **Availability.** One engine serves the kernel services per NATS account; deploys without downtime
  need shared backends and `ABI_ROLLOUT_ID`. See [High availability and disaster recovery](/user-guide/deploy/high-availability).
- **Upgrades.** Moving a 2.x deployment: [Migrate from 2.x to 3.0](/user-guide/upgrade/migrate-to-3).
- **Remote agents.** [Publish remote agents](/user-guide/deploy/publish_remote_agents).

## Enterprise implementation

:::info Professional services
naas.ai's team designs and implements enterprise deployments (on-premises, air-gapped, hybrid,
government) with you. Contact [support@naas.ai](mailto:support@naas.ai) to discuss your needs and
timeline. The pages of this section describe what ABI itself provides; what a deployment must add
(identity provider, monitoring, backups, network controls) is yours or your integrator's.
:::
