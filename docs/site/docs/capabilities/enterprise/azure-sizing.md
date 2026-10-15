---
sidebar_position: 5
---

# Azure Sizing and Cost Reference

This page sizes a production ABI deployment on Microsoft Azure and estimates its monthly cost. It covers compute, databases, storage, networking, operations and self-hosted model inference with vLLM on GPUs.

- **Release sized:** ABI 2.x as released on `main` (naas-abi 2.83): one ABI API process that also serves the Nexus API, RabbitMQ as the message bus, Redis as the key-value store, and a SQLite event log. [ABI 3.0 (NATS)](#moving-to-abi-30-nats) changes a few lines and is covered at the end.
- **Prices:** Azure list prices for the **UAE North** region in USD, read from the [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) on **2026-10-15**. They exclude taxes and any enterprise agreement or commitment discount. Other regions differ; refresh them as described in [Refreshing the prices](#refreshing-the-prices).
- **Month:** 730 hours. "Business hours" means 12 hours a day, 22 days a month (264 hours).
- **Status:** these are planning estimates. Confirm them in the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) before committing a budget.

## Bottom line

| Scenario | What runs | Pay-as-you-go | With 1-year reservations |
|---|---|---|---|
| **Platform only** (inference bought per token, or none) | Everything except GPUs | **≈ $4,150 / month** | ≈ $3,020 / month |
| **Recommended start** | Platform + 1 × H100 NVL GPU node, 24×7 | **≈ $11,430 / month** | ≈ $8,480 / month |
| Same, GPU in business hours only | Platform + 1 × H100 NVL, 264 h | ≈ $6,780 / month | ≈ $5,660 / month (platform reserved, GPU pay-as-you-go) |
| Same, with a standby GPU node | Platform + 2 × H100 NVL, 24×7 | ≈ $18,720 / month | ≈ $13,950 / month |
| **Large open-weights models** | Platform + 1 × 8-GPU node (H200), 24×7 | ≈ $92,670 / month | ≈ $51,580 / month |
| Coding workspaces (optional add-on) | Coder + Forgejo, 10 workspaces in business hours | ≈ $640 / month | |
| Non-production environment (optional) | Small copy of the platform, no GPU | ≈ $1,450 / month | |

"With 1-year reservations" reserves the platform virtual machines, the PostgreSQL compute and, where it runs 24×7, the GPU node.

**GPU inference dominates the bill.** The platform is about $4,150 a month. A single GPU node adds $1,180 to $102,640 a month, depending on the model it must serve (see [GPU options](#gpu-options-for-vllm)). That matches the $1 to $100+ per hour range usually quoted for GPU inference: the hourly prices in UAE North run from $1.62 (a quarter of an RTX PRO 6000) to $140.60 (eight H100 GPUs).

**The model decides the GPU, not the number of users.** Pick the model first, then the smallest GPU it fits on, then add nodes for concurrency or availability.

## Reference architecture

ABI runs on Azure Kubernetes Service (AKS) with managed Azure services for the database, object storage, ingress and monitoring.

| ABI component | Azure resource | Sizing basis |
|---|---|---|
| ABI API (engine, agents and the Nexus API in one process), Nexus web, MCP server, RabbitMQ, Redis, Dagster | AKS **app node pool**: 3 × `Standard_D8s_v5` (8 vCPU, 32 GiB) in 3 availability zones | **One** ABI API replica (see [Availability](#availability)); 2 replicas of Nexus web; one pod each for the rest. The workloads need about 12 vCPU and 32 GiB, so the pool survives the loss of a node or a zone and has room for the coding-workspace control planes. |
| Knowledge graph (Apache Jena Fuseki, TDB2) and vector store (Qdrant) | AKS **data node pool**: 2 × `Standard_E8s_v5` (8 vCPU, 64 GiB) in 2 zones | One pod each. Both fit on one node, so either can restart on the other node. The development compose file caps Fuseki at 4 GB with a 2 GB heap; production gets 16 GB or more. |
| Kubernetes system services | AKS **system node pool**: 2 × `Standard_D4s_v5` (4 vCPU, 16 GiB) | Keeps Kubernetes system pods apart from the workload |
| Relational data: Nexus, document store, Dagster run storage, and the Coder and Forgejo databases if used | **Azure Database for PostgreSQL – Flexible Server**, General Purpose, 4 vCores, 256 GiB, zone-redundant high availability | One server with a database per component. Zone-redundant HA keeps a standby with the same compute and storage in another zone ([Microsoft docs](https://learn.microsoft.com/en-us/azure/postgresql/high-availability/concepts-high-availability)), so it roughly doubles this line. |
| Event log | Premium SSD **P10 ZRS** volume mounted by the ABI API | Holds the SQLite event log (`storage/events/events.sqlite` in `config.remote.yaml`) and the API's local storage |
| Message bus | RabbitMQ, one pod, on a Premium SSD **P10 ZRS** volume | |
| Graph and vector data | 2 × Premium SSD **P20 ZRS** (512 GiB) | Zone-redundant disks can be attached in any zone of the region, which lets the pods move after a zone loss |
| Files and documents | **Azure Blob Storage**, Hot, zone-redundant, 1 TB | See [Gaps to close](#gaps-to-close-before-go-live) |
| Ingress, TLS, web application firewall | **Application Gateway WAF v2** | One gateway, about 2 capacity units on average |
| Logs and metrics | **Log Analytics** (Container insights), about 50 GB a month | The first 5 GB a month are free |
| Images, secrets | Container Registry Standard, Key Vault | |
| Model inference | AKS **GPU node pool** running vLLM | See [GPU options](#gpu-options-for-vllm) |

### Availability

This design survives the loss of a node or of one availability zone, but it is not active-active:

- **ABI API, Fuseki, Qdrant and RabbitMQ run as single pods.** If their node or zone fails, Kubernetes restarts them on a surviving node and reattaches their zone-redundant disks. Expect a few minutes of interruption, and requests in flight are lost.
- **The ABI API cannot run as two replicas** on this release: each replica would write its own SQLite event log.
- **PostgreSQL** fails over to its standby automatically, in 60 to 120 seconds with zero data loss ([Microsoft docs](https://learn.microsoft.com/en-us/azure/postgresql/high-availability/concepts-high-availability)).
- **Nexus web** runs 2 replicas and does not interrupt.
- **A single GPU node** is a single point of failure for self-hosted inference (see [Recommendation](#recommendation-for-a-first-production-phase)).

## Gaps to close before go-live

Two pieces of the design need work in ABI itself. Neither is in the cost figures.

| Gap | Today | Work needed | Effort |
|---|---|---|---|
| **ABI cannot use a vLLM server yet** | Nexus stores and health-probes inference servers of type `vllm`, but its chat path has no route for them (`provider_runtime.py` raises `Unknown provider type`). The `custom` type is OpenAI-compatible but requires HTTPS and refuses `.local` hostnames and private IP addresses. No marketplace model module targets an OpenAI-compatible server, so ABI agents cannot use vLLM at all. | An OpenAI-compatible model module for agents (chat and embeddings), modelled on the existing Ollama module; a `vllm` route in the Nexus provider runtime | About 3–5 person-days, plus 1 for Nexus |
| **No Azure Blob adapter** | Object storage adapters are filesystem, S3-compatible, Cloudflare R2 and Naas. | An Azure Blob adapter with managed-identity authentication | About 2–4 person-days |

Interim options without code changes:

- **vLLM:** expose vLLM under an internal HTTPS hostname and register it in Nexus as a `custom` provider. That covers direct chat in Nexus only, not ABI agents.
- **Blob storage:** run an S3-compatible store in the cluster on a 1 TiB Premium SSD, which adds about $150 a month.

## Platform cost (production, no GPU)

| Line item | Specification | Pay-as-you-go | 1-year reserved |
|---|---|---|---|
| AKS control plane, Standard tier | Uptime SLA | $73 | $73 |
| System node pool | 2 × D4s_v5 at $0.235/h | $343 | $212 |
| App node pool | 3 × D8s_v5 at $0.471/h | $1,031 | $636 |
| Data node pool | 2 × E8s_v5 at $0.620/h | $905 | $559 |
| Node OS disks | 7 × P10 LRS (128 GiB) | $151 | $151 |
| Graph and vector volumes | 2 × P20 ZRS (512 GiB) | $240 | $240 |
| Event log and RabbitMQ volumes | 2 × P10 ZRS (128 GiB) | $65 | $65 |
| Disk snapshots | about 500 GB, ZRS | $25 | $25 |
| Blob storage | 1 TB Hot ZRS, plus operations | $36 | $36 |
| PostgreSQL Flexible Server compute | Ddsv5, 4 vCores, zone-redundant HA: 8 vCores at $0.109/h, or $571 per vCore-year reserved | $637 | $381 |
| PostgreSQL storage | 256 GiB, ×2 for HA ($0.138 per GiB-month) | $71 | $71 |
| Application Gateway WAF v2 | Fixed $0.475/h plus about 2 capacity units | $374 | $374 |
| Public IPs, internet egress | 2 static IPs; 200 GB out, first 100 GB free | $25 | $25 |
| Log Analytics | 50 GB ingested, first 5 GB free ($3.29/GB) | $148 | $148 |
| Container Registry, Key Vault | Standard registry; Key Vault operations | $25 | $25 |
| **Total** | | **≈ $4,149** | **≈ $3,020** |

- **Reservations:**
  - 1-year reserved instances on the seven platform VMs bring compute from $2,280 to $1,407 a month.
  - PostgreSQL reserved capacity brings the database compute from $637 to $381 a month.
  - Reservations can be paid monthly at no extra cost ([Microsoft docs](https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/prepare-buy-reservation)).
- **Database backups** fit in the free backup allowance, which equals the provisioned storage ([Microsoft docs](https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore)).
- **Not included:** Azure Bastion for administrator access (from about $139 a month), Microsoft Defender for Cloud, Azure Firewall, and private DNS zones. Add them if the landing zone requires them.

### Optional: coding workspaces (Coder and Forgejo)

| Line item | Specification | Monthly |
|---|---|---|
| Coder and Forgejo control planes | One pod each on the app node pool; a database each on the same PostgreSQL server | included above |
| Workspace node pool | `Standard_D8s_v5`, autoscaled, 3 workspaces of 2 vCPU / 8 GiB per node; 4 nodes for 10 concurrent workspaces, business hours | $497 |
| Workspace home volumes | 10 × P6 LRS (64 GiB) | $111 |
| Forgejo repositories | 1 × P10 ZRS (128 GiB) | $32 |
| **Total for 10 workspaces** | | **≈ $641** |

Each additional 3 workspaces in business hours add one node, about $124 a month (about $344 if they run 24×7). Coder supports only PostgreSQL as its database.

### If the database must be SQL Server

Azure SQL Database, General Purpose, 4 vCores with zone redundancy and 256 GB costs **≈ $1,017 a month**, against ≈ $707 for PostgreSQL Flexible Server at pay-as-you-go prices. ABI does not run on SQL Server today; porting it is a separate engineering project, and Coder cannot run on SQL Server at all.

## GPU options for vLLM

All sizes below are listed in UAE North. Monthly figures are for one node. Reserved prices are the reservation total divided by its term.

| Option | Azure size | GPUs (GPU memory) | vCPU / RAM | $/hour | 24×7 / month | Business hours / month | 1-year reserved / month | 3-year reserved / month |
|---|---|---|---|---|---|---|---|---|
| G1 | `Standard_NC24lds_xl_RTXPRO6000BSE_v6` | ¼ RTX PRO 6000 (24 GB) | 24 / 72 GiB | 1.62 | $1,180 | $427 | $755 | $519 |
| G2a | `Standard_NC144lds_xl_RTXPRO6000BSE_v6` | 1 RTX PRO 6000 (96 GB) | 144 / 264 GiB | 7.87 | $5,745 | $2,078 | $3,677 | $2,528 |
| **G2b** | `Standard_NC40ads_H100_v5` | 1 H100 NVL (94 GB) | 40 / 320 GiB | 9.98 | **$7,285** | $2,635 | $5,464 | $4,007 |
| G3 | `Standard_NC80adis_H100_v5` | 2 H100 NVL (188 GB) | 80 / 640 GiB | 19.96 | $14,571 | $5,269 | $10,928 | $8,014 |
| G4a | `Standard_ND96isr_MI300X_v5` | 8 MI300X (1,535 GB) | 96 / 1,850 GiB | 68.64 | $50,107 | $18,121 | $32,069 | $21,997 |
| G4b | `Standard_ND96isr_H200_v5` | 8 H200 (1,128 GB) | 96 / 1,850 GiB | 121.26 | $88,523 | $32,014 | $48,564 | $44,075 |
| G4c | `Standard_ND96isr_H100_v5` | 8 H100 (640 GB) | 96 / 1,900 GiB | 140.60 | $102,637 | $37,118 | $65,687 | $45,057 |

Specifications: [NC RTX PRO 6000 BSE v6](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nc-rtxpro6000-bse-v6-series), [NCads H100 v5](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ncadsh100v5-series), [ND MI300X v5](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ndmi300xv5-series), [ND H200 v5](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nd-h200-v5-series), [ND H100 v5](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ndh100v5-series).

### Which model fits which GPU

A model's weights need about **2 bytes per parameter in FP16/BF16, 1 byte in FP8 and about half a byte in 4-bit formats**. vLLM uses the remaining GPU memory as KV cache: the more is left, the more concurrent requests and the longer the contexts it serves.

| Model class (examples) | Weights in memory | Smallest sensible option |
|---|---|---|
| 7–8B dense, FP16; embedding and reranking models | ≈ 16 GB | G1 (24 GB), little room for long contexts |
| 24–32B dense, FP8 | ≈ 24–32 GB | G2a or G2b (94–96 GB), plenty of KV cache |
| gpt-oss-120b (117B total, 5.1B active, MXFP4) | fits one 80 GB GPU ([model card](https://huggingface.co/openai/gpt-oss-120b)) | G2b |
| 70B dense, FP8 | ≈ 70 GB | G2a/G2b is tight; G3 (2 GPUs) is comfortable |
| 235B mixture-of-experts, FP8 | ≈ 235 GB | G4 (8 GPUs) |
| 671B mixture-of-experts (DeepSeek V3 class), FP8 | ≈ 671 GB+ | G4a or G4b; G4c only with 4-bit weights |

**H100 NVL or RTX PRO 6000?**
- **Memory:** both have about 95 GB per GPU.
- **Bandwidth:** the H100 NVL has 3.9 TB/s ([NVIDIA](https://www.nvidia.com/en-us/data-center/h100/)), against 1.6 TB/s for the RTX PRO 6000 Blackwell Server Edition ([NVIDIA](https://www.nvidia.com/en-us/data-center/rtx-pro-6000-blackwell-server-edition/)).
- **For chat models:** token generation is mostly limited by memory bandwidth. The H100 NVL should therefore give noticeably more throughput per dollar, despite costing 27% more.
- **For the rest:** the RTX PRO 6000 is the cheaper option for embeddings, smaller models and multimodal work.

**AMD MI300X** (G4a) is the cheapest way to get more than 1 TB of GPU memory. vLLM supports AMD ROCm ([vLLM docs](https://docs.vllm.ai/en/latest/getting_started/installation/gpu.html)), but test the chosen model on it before committing.

### Recommendation for a first production phase

- **Start with G2b** (`Standard_NC40ads_H100_v5`, 1 × H100 NVL 94 GB).
  - It serves a 24–32B FP8 model or gpt-oss-120b, with room for concurrent users.
  - It can also serve an embedding model, in a second vLLM process.
  - Two processes on one GPU each need an explicit `--gpu-memory-utilization` (for example 0.80 for the chat model and 0.10 for the embedding model). The default of 0.9 assumes one process per GPU.
- **Close the vLLM gap first** (see [Gaps to close](#gaps-to-close-before-go-live)). Until then, ABI agents cannot use the GPU.
- **Measure before scaling.** Run a load test on the chosen model in the first weeks, with realistic prompt and answer lengths. It tells how many concurrent users one node serves, and so whether to add a node.
- **Availability.** One GPU node is a single point of failure. Either add a second node (G2b × 2), or fall back to a per-token Azure model endpoint when the node is down.
- **Move to G3 or G4 only for a larger model.** Adding users is cheaper with more G2b nodes than with a bigger node.

## Levers on the bill

- **Schedule GPU nodes.** Running the GPU pool 264 business hours instead of 730 cuts the GPU line by 64%.
  - The cluster autoscaler removes a GPU node only once no vLLM pod is left on it. So the schedule must scale the vLLM deployment itself, for example with a [KEDA cron scaler](https://keda.sh/docs/latest/scalers/cron/); the autoscaler then scales the pool to zero.
  - The first request after a scale-up waits for the node to start and the model to load.
- **Reserve what runs 24×7.**
  - GPU nodes: 1-year reservations save about 25–45%, 3-year reservations 45–56%.
  - Platform VMs: 1-year saves about 38%.
  - PostgreSQL compute: 1-year saves about 40%.
  - With a business-hours GPU, the platform can still be reserved.
- **Use per-token endpoints for low or bursty volume.** Microsoft Foundry lists open-weights models in UAE North priced per token, for example gpt-oss-120b at $0.15 per million input tokens and $0.60 per million output tokens. Most of these list prices are for *Global* deployments, which can process data outside the region. Check that against data-residency requirements.
- **Right-size the platform after a month of metrics.** The node pools above are a starting point; Container insights shows actual CPU and memory use.

## Before ordering

- **Quota.** New subscriptions have little or no quota for GPU families. Request NC and ND quota in the target region early ([Microsoft docs](https://learn.microsoft.com/en-us/azure/quotas/per-vm-quota-requests)).
- **Capacity.** A size in the price list is not a guarantee of capacity. Check the region with the Microsoft account team and with:

  ```bash
  az vm list-skus --location uaenorth --size Standard_NC --output table
  az vm list-skus --location uaenorth --size Standard_ND --output table
  ```

- **NC RTX PRO 6000 BSE v6** was announced in public preview in November 2025 ([Microsoft Tech Community](https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/-/4472704)). Confirm it is generally available in the target region before relying on G1 or G2a. G1 is a quarter of a GPU: validate vLLM on that partition.
- **AKS and GPUs.** AKS installs and maintains the NVIDIA driver, device plugin and metrics exporter on managed GPU node pools ([Microsoft docs](https://learn.microsoft.com/en-us/azure/aks/use-nvidia-gpu)).

## Moving to ABI 3.0 (NATS)

ABI 3.0 replaces RabbitMQ with NATS and changes the serving model. Its cost is within a few dollars of the figures above:

- **Message bus:** NATS JetStream, 3 pods on the app node pool with a P10 ZRS volume each, replaces RabbitMQ. That is two more volumes, about +$65 a month.
- **Serving engine:**
  - There is exactly one serving engine per NATS account, holding a lease.
  - A second engine runs only as a standby during a rollout, then takes over the lease.
  - Other modules run as clients and open no database.
- **Shared backends for zero-downtime deploys.** The standby only works when every backend is shared rather than local to the engine:
  - PostgreSQL for documents, events and the dataset catalog
  - S3-compatible or Blob object storage
  - a network triple store
  - Moving the event log to PostgreSQL removes the event-log volume.
- **Dagster** is being retired, which frees its share of the app node pool.

## Assumptions behind the platform sizing

- 100 to 300 named users, up to about 30 working at the same time.
- A knowledge graph up to about 50 million triples and a vector store up to about 5 million vectors.
- Up to 1 TB of files and 256 GiB of relational data.
- One region, over three availability zones, with database HA, zone-redundant data disks and daily disk snapshots. No second region.

If the real figures are well above these, grow the data node pool and the database first.

## Refreshing the prices

The Azure Retail Prices API needs no authentication. For example, every GPU size in UAE North:

```bash
curl -s "https://prices.azure.com/api/retail/prices?\$filter=armRegionName%20eq%20'uaenorth'%20and%20serviceName%20eq%20'Virtual%20Machines'%20and%20startswith(armSkuName,'Standard_N')"
```

Follow `NextPageLink` to page through results. Skip Windows, Spot and Low Priority meters. Reservation rows (`"type": "Reservation"`) give the total for the term, not an hourly price.
