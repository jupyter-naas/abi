---
sidebar_position: 5
---

# Azure Sizing and Cost Reference

This page sizes a production ABI deployment on Microsoft Azure and estimates its monthly cost. It covers compute, databases, storage, networking, operations and self-hosted model inference with vLLM on GPUs.

- **Prices:** Azure list prices for the **UAE North** region in USD, read from the [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) on **2026-10-15**. They exclude taxes and any enterprise agreement or commitment discount. Other regions differ; refresh them as described in [Refreshing the prices](#refreshing-the-prices).
- **Month:** 730 hours. "Business hours" means 12 hours a day, 22 days a month (264 hours).
- **Status:** these are planning estimates. Confirm them in the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/) before committing a budget.

## Bottom line

| Scenario | What runs | Pay-as-you-go | With 1-year reservations |
|---|---|---|---|
| **Platform only** (inference bought per token, or none) | Everything except GPUs | **≈ $4,100 / month** | ≈ $3,200 / month |
| **Recommended start** | Platform + 1 × H100 NVL GPU node, 24×7 | **≈ $11,400 / month** | ≈ $8,700 / month |
| Same, GPU in business hours only | Platform + 1 × H100 NVL, 264 h | ≈ $6,700 / month | n/a (reservations are 24×7) |
| Same, with a standby GPU node | Platform + 2 × H100 NVL, 24×7 | ≈ $18,600 / month | ≈ $14,100 / month |
| **Large open-weights models** | Platform + 1 × 8-GPU node (H200), 24×7 | ≈ $92,600 / month | ≈ $51,800 / month |
| Non-production environment (optional) | Small copy of the platform, no GPU | ≈ $1,400 / month | |

**GPU inference dominates the bill.** The platform is about $4,100 a month. A single GPU node adds $1,200 to $103,000 a month, depending on the model it must serve (see [GPU options](#gpu-options-for-vllm)). That matches the $1 to $100+ per hour range usually quoted for GPU inference: the hourly prices in UAE North run from $1.62 (a quarter of an RTX PRO 6000) to $140.60 (eight H100 GPUs).

**The model decides the GPU, not the number of users.** Pick the model first, then the smallest GPU it fits on, then add nodes for concurrency or availability.

## Reference architecture

ABI runs on Azure Kubernetes Service (AKS) with managed Azure services for the database, object storage, ingress and monitoring.

| ABI component | Azure resource | Sizing basis |
|---|---|---|
| Serving engine (core services, agents), Nexus API, Nexus web, NATS JetStream, Redis | AKS **app node pool**: 3 × `Standard_D8s_v5` (8 vCPU, 32 GiB) across 3 availability zones | 2 replicas each for the engine, Nexus API and web; 3-node NATS cluster; Redis as an in-cluster cache |
| Knowledge graph (Apache Jena Fuseki, TDB2) and vector store (Qdrant) | AKS **data node pool**: 2 × `Standard_E8s_v5` (8 vCPU, 64 GiB) | Memory-heavy stateful services. The development compose file caps Fuseki at 4 GB with a 2 GB heap; production gets 16 GB or more. |
| Kubernetes system services | AKS **system node pool**: 2 × `Standard_D4s_v5` (4 vCPU, 16 GiB) | Keeps Kubernetes system pods apart from the workload |
| Relational data (Nexus, document service, dataset catalog) | **Azure Database for PostgreSQL – Flexible Server**, General Purpose, 4 vCores, 256 GiB, zone-redundant high availability | Zone-redundant HA keeps a standby with the same compute and storage in another zone ([Microsoft docs](https://learn.microsoft.com/en-us/azure/postgresql/high-availability/concepts-high-availability)), so it roughly doubles this line |
| Files and documents | **Azure Blob Storage**, Hot, zone-redundant, 1 TB | See the object-storage note below |
| Persistent volumes | Premium SSD managed disks: 2 × 512 GiB (graph, vectors), 3 × 128 GiB (NATS) | Plus incremental snapshots for backup |
| Ingress, TLS, web application firewall | **Application Gateway WAF v2** | One gateway, about 2 capacity units on average |
| Logs and metrics | **Log Analytics** (Container insights), about 50 GB a month | The first 5 GB a month are free |
| Images, secrets | Container Registry Standard, Key Vault | |
| Model inference | AKS **GPU node pool** running vLLM | See [GPU options](#gpu-options-for-vllm) |

ABI talks to vLLM through vLLM's OpenAI-compatible API: Nexus already registers inference servers of type `vllm` and probes `/health` and `/v1/models` on them.

**Object storage.** ABI's object storage adapters today are filesystem, S3-compatible, Cloudflare R2 and Naas; there is no native Azure Blob adapter yet. Two ways to run on Azure:

- **Add an Azure Blob adapter** (a few person-days of work). This is what the table prices: 1 TB of Hot ZRS Blob costs about $26 a month.
- **Run an S3-compatible store in the cluster** on a 1 TiB Premium SSD (about $150 a month more) with no code change.

## Platform cost (production, no GPU)

| Line item | Specification | Monthly (pay-as-you-go) |
|---|---|---|
| AKS control plane, Standard tier | Uptime SLA | $73 |
| System node pool | 2 × D4s_v5 at $0.235/h | $343 |
| App node pool | 3 × D8s_v5 at $0.471/h | $1,031 |
| Data node pool | 2 × E8s_v5 at $0.620/h | $905 |
| Node OS disks | 7 × P10 (128 GiB) | $151 |
| Graph and vector volumes | 2 × P20 (512 GiB) | $160 |
| NATS JetStream volumes | 3 × P10 (128 GiB) | $65 |
| Disk snapshots | about 500 GB, ZRS | $25 |
| Blob storage | 1 TB Hot ZRS, plus operations | $36 |
| PostgreSQL Flexible Server | D4ds_v5, 4 vCores, zone-redundant HA ($0.1085 per vCore-hour, ×2) | $634 |
| PostgreSQL storage | 256 GiB, ×2 for HA ($0.138 per GiB-month) | $71 |
| Application Gateway WAF v2 | Fixed $0.475/h plus about 2 capacity units | $374 |
| Public IPs, internet egress | 2 static IPs; 200 GB out, first 100 GB free | $25 |
| Log Analytics | 50 GB ingested, first 5 GB free ($3.29/GB) | $148 |
| Container Registry, Key Vault | Standard registry; Key Vault operations | $25 |
| **Total** | | **≈ $4,066** |

- **Reservations:** 1-year reserved instances on the seven platform VMs bring compute from $2,280 to $1,407 a month, so the platform drops to **≈ $3,193**. Reservations can be paid monthly at no extra cost ([Microsoft docs](https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/prepare-buy-reservation)).
- **Database backups** fit in the free backup allowance, which equals the provisioned storage ([Microsoft docs](https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore)).
- **Not included:** Azure Bastion for administrator access (from about $139 a month), Microsoft Defender for Cloud, Azure Firewall, and private DNS zones. Add them if the landing zone requires them.

### If the database must be SQL Server

Azure SQL Database, General Purpose, 4 vCores with zone redundancy and 256 GB costs **≈ $1,017 a month**, against ≈ $704 for PostgreSQL Flexible Server. ABI does not run on SQL Server today; porting it is a separate engineering project.

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

**H100 NVL or RTX PRO 6000?** Both have about 95 GB per GPU. The H100 NVL has 3.9 TB/s of memory bandwidth ([NVIDIA](https://www.nvidia.com/en-us/data-center/h100/)) against 1.6 TB/s for the RTX PRO 6000 Blackwell Server Edition ([NVIDIA](https://www.nvidia.com/en-us/data-center/rtx-pro-6000-blackwell-server-edition/)). Token generation is mostly bound by memory bandwidth, so for chat models the H100 NVL should give noticeably more throughput per dollar despite its 27% higher price. The RTX PRO 6000 is the cheaper option for embeddings, smaller models and multimodal work.

**AMD MI300X** (G4a) is the cheapest way to get more than 1 TB of GPU memory. vLLM supports AMD ROCm ([vLLM docs](https://docs.vllm.ai/en/latest/getting_started/installation/gpu.html)), but test the chosen model on it before committing.

### Recommendation for a first production phase

- **Start with G2b** (`Standard_NC40ads_H100_v5`, 1 × H100 NVL 94 GB). It serves a 24–32B FP8 model or gpt-oss-120b with room for concurrent users, and an embedding model alongside it in a second vLLM process.
- **Measure before scaling.** Run a load test on the chosen model, with realistic prompt and answer lengths, in the first weeks. It tells how many concurrent users one node serves, and so whether to add a node.
- **Availability.** One GPU node is a single point of failure. Either add a second node (G2b × 2) or fall back to a per-token Azure model endpoint when the node is down.
- **Move to G3 or G4 only for a larger model.** Adding users is cheaper with more G2b nodes than with a bigger node.

## Levers on the bill

- **Schedule GPU nodes.** The AKS cluster autoscaler can scale a GPU pool to zero; running it 264 business hours instead of 730 cuts the GPU line by 64%. The first request after a scale-up waits for the node to start and the model to load.
- **Reserve what runs 24×7.** 1-year reservations save about 25–45% on GPU nodes and about 38% on the platform VMs; 3-year reservations save 45–56% on GPUs.
- **Use per-token endpoints for low or bursty volume.** Microsoft Foundry lists open-weights models in UAE North priced per token, for example gpt-oss-120b at $0.15 per million input tokens and $0.60 per million output tokens. Most of these list prices are for *Global* deployments, which can process data outside the region. Check that against data-residency requirements.
- **Right-size the platform after a month of metrics.** The node pools above are a starting point; Container insights shows actual CPU and memory use.

## Before ordering

- **Quota.** New subscriptions have little or no quota for GPU families. Request NC and ND quota in the target region early ([Microsoft docs](https://learn.microsoft.com/en-us/azure/quotas/per-vm-quota-requests)).
- **Capacity.** A size in the price list is not a guarantee of capacity. Check with `az vm list-skus --location uaenorth --size Standard_NC --output table` and with the Microsoft account team.
- **NC RTX PRO 6000 BSE v6** was announced in public preview in November 2025 ([Microsoft Tech Community](https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/-/4472704)). Confirm it is generally available in the target region before relying on G1 or G2a. G1 is a quarter of a GPU: validate vLLM on that partition.
- **AKS and GPUs.** AKS installs and maintains the NVIDIA driver, device plugin and metrics exporter on managed GPU node pools ([Microsoft docs](https://learn.microsoft.com/en-us/azure/aks/use-nvidia-gpu)).

## Assumptions behind the platform sizing

- 100 to 300 named users, up to about 30 working at the same time.
- A knowledge graph up to about 50 million triples and a vector store up to about 5 million vectors.
- Up to 1 TB of files and 256 GiB of relational data.
- One region, spread over three availability zones, with database HA and daily disk snapshots. No second region.

If the real figures are well above these, grow the data node pool and the database first.

## Refreshing the prices

The Azure Retail Prices API needs no authentication. For example, every GPU size in UAE North:

```bash
curl -s "https://prices.azure.com/api/retail/prices?\$filter=armRegionName%20eq%20'uaenorth'%20and%20serviceName%20eq%20'Virtual%20Machines'%20and%20startswith(armSkuName,'Standard_N')"
```

Follow `NextPageLink` to page through results. Skip Windows, Spot and Low Priority meters. Reservation rows (`"type": "Reservation"`) give the total for the term, not an hourly price.
