---
sidebar_position: 5
title: "Deployment models"
---

# Deployment models

ABI's production stack is Docker Compose: every service is a standard container, with no proprietary Kubernetes substrate and no managed infrastructure required. For development, `abi dev up` runs the same engine as native processes. You operate it with tools you already know.

This is an intentional design choice. Abstracting infrastructure into a managed runtime delivers security and availability guarantees but removes operator visibility and control. ABI makes the opposite tradeoff: the infrastructure is yours to inspect, modify, extend, and replace. You own operations; in return, there are no accreditation dependencies, no vendor upgrade cycles, and no egress charges.

The same project runs on a developer laptop and in a production data center. The only differences between environments are the config files that select service backends, the model provider, and the LLM routing configuration.

Since 3.0 every deployment runs on a [NATS broker](/developer-guide/architecture/nats): the engine serves its kernel services over it, the bus and the [module jobs](/user-guide/build/modules/module-jobs) use JetStream, and remote modules run in their own containers next to the engine.

| Model | For | How |
|---|---|---|
| Local development | One developer | `abi dev up`, or [Docker](/user-guide/deploy/local-docker) |
| One server | A team, a client, a staging environment | [Docker](/user-guide/deploy/local-docker) or [Dokploy](/user-guide/deploy/dokploy) |
| Self-hosted production | Your cluster or data center | [Production and remote deployments](/user-guide/deploy/production) |
| Air-gapped | No outbound network | [Air-gapped deployment](/user-guide/deploy/air-gapped) |
| Managed | naas.ai runs it | [naas.ai/enterprise](https://naas.ai/enterprise) |

---

## Local development

Two ways to run a project on your machine:

- **Native, no Docker:** `abi dev up` starts `nats-server`, an Oxigraph server, the API, Nexus web and the remote modules listed under `dev.modules`, as native processes with file-based backends (SQLite, the file system). Each git worktree gets its own ports. It needs `nats-server` 2.14 or later on `PATH`, and `jaeger` for `--with-tracing`.
- **Docker Compose:** `abi deploy local` writes the project's stack, and `docker compose up -d` (or `abi stack start`) starts it: NATS, PostgreSQL, Fuseki, Qdrant, MinIO, Redis, the API, Nexus web, the MCP server and Caddy. Remote modules each get a service in `docker-compose.override.yml`.

Step by step: [Quickstart](/user-guide/get-started/quickstart) and [Deploy with Docker](/user-guide/deploy/local-docker).

---

## Self-hosted (on-premises)

The production configuration. All services run in your infrastructure, nothing leaves your network.

- Your Kubernetes cluster or bare-metal Docker Compose
- Your NATS server (2.14 or later, JetStream on), PostgreSQL, MinIO or S3, Redis, Fuseki and Qdrant
- Your LLM infrastructure (Ollama cluster or private API endpoints)
- Your SSL/TLS termination

Things to plan for:

- **One serving engine.** One engine serves the kernel services per NATS account. For deploys without downtime, set `ABI_ROLLOUT_ID` per deploy and use shared backends (no SQLite or local files): the new engine stands by and takes over when the old one stops. See [one serving engine](/developer-guide/architecture/nats#one-serving-engine).
- **A supervisor.** The API and remote modules exit when the broker is unreachable for about two minutes; Docker (`restart: unless-stopped`) or Kubernetes restarts them.
- **The broker stays private.** Traffic to NATS is not encrypted, and its monitoring port has no authentication. See [Security model](/developer-guide/architecture/security).
- **Remote modules** scale on their own: several replicas of a module share its agent runs and its jobs.

This is the configuration naas.ai deploys for enterprise customers who require data residency compliance. How to set it up: [Production and remote deployments](/user-guide/deploy/production); on one server with a domain, [Dokploy](/user-guide/deploy/dokploy).

---

## Air-gapped

Full offline operation with locally-run models:

- Ollama serves LLM inference from a local model library; the `ai.ollama` module registers Qwen2.5 3B and `nomic-embed-text`, and the marketplace has modules for Qwen3 8B, DeepSeek R1 8B and Gemma3 4B
- No calls to OpenAI, Anthropic, OpenRouter or any external API: disable the cloud provider modules
- `ai_mode: "local"` (or `"airgap"`) in `config.yaml`, with the model registry defaults pointed at the local models
- Images, Python packages and models are brought in beforehand

The steps are in [Air-gapped deployment](/user-guide/deploy/air-gapped).

---

## Managed (naas.ai)

naas.ai provides enterprise-managed ABI deployments. The open-source core is MIT-licensed; the managed tier adds:

- Deployment and maintenance on your premises or naas.ai infrastructure
- 24/7 support and SLA
- Security compliance assistance (SOC 2, ISO 42001)
- Upgrade management

See [naas.ai/enterprise](https://naas.ai/enterprise) for details.

---

## Configuration per environment

A project made by `abi new project` keeps one config file per environment:

```bash
config.yaml          # Default: what `abi dev up` and the CLI read
config.local.yaml    # The Docker Compose stack (its `abi` service sets ENV=local)
config.remote.yaml   # A remote deployment
```

The engine reads `config.<ENV>.yaml` when the `ENV` environment variable names one that exists, else `config.yaml`. `ABI_CONFIG_OVERLAY` merges a YAML file over it (`abi dev up` uses it for its broker settings). See [Configuration Reference](/user-guide/get-started/configuration).

---

## Enterprise reference architectures

:::info Professional services implementation
The architectures below are reference material for enterprise deployments that naas.ai's professional services team designs and implements with you. The YAML is illustrative, not a template ABI ships. Contact [support@naas.ai](mailto:support@naas.ai) to discuss your needs and timeline.
:::

Whatever the platform, the rules of [self-hosted production](#self-hosted-on-premises) hold: one NATS broker with JetStream on a private network, one serving engine per NATS account, shared backends for deploys without downtime, and a supervisor that restarts what exits when the broker is gone.

### Cloud-Native Deployment

#### Kubernetes-Native Architecture

Naas is built from the ground up as a cloud-native application, leveraging Kubernetes for container orchestration and management.

**Core Components**:
- **Control Plane**: Manages platform configuration, user management, and orchestration
- **Agent Runtime**: Executes AI agents with auto-scaling based on demand
- **Data Layer**: Distributed storage with automatic replication and backup
- **API Gateway**: Secure API access with rate limiting and authentication

**Kubernetes Resources**:
```yaml
# Example deployment
apiVersion: apps/v1
kind: Deployment
metadata:
 name: my-ai-engine
spec:
 replicas: 3
 selector:
 matchLabels:
 app: naas-platform
 template:
 spec:
 containers:
 - name: naas-api
 image: registry.example.com/my-ai:latest
 resources:
 requests:
 memory: "2Gi"
 cpu: "1000m"
 limits:
 memory: "4Gi"
 cpu: "2000m"
```

#### Multi-Region Deployment

**Global Distribution Strategy**:
- **Primary Region**: Main deployment with full functionality
- **Secondary Regions**: Read replicas with failover capability
- **Edge Locations**: Cached responses for improved performance
- **Data Residency**: Configurable data storage locations for compliance

**Regional Architecture**:
```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor': '#f8fafc', 'primaryTextColor': '#1e293b', 'primaryBorderColor': '#e2e8f0', 'lineColor': '#64748b'}}}%%
graph TD
 subgraph "Primary Region (US-East)"
 A[Control Plane]
 B[Agent Runtime]
 C[Database Primary]
 end

 subgraph "Secondary Region (EU-West)"
 D[Control Plane Replica]
 E[Agent Runtime]
 F[Database Replica]
 end

 subgraph "Edge Locations"
 G[CDN Cache]
 H[API Cache]
 end

 A --> D
 C --> F
 G --> A
 H --> A

 class A,B,C,D,E,F platform
 class G,H infrastructure
```

#### Auto-Scaling Configuration

**Horizontal Pod Autoscaler (HPA)**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
 name: naas-agent-hpa
spec:
 scaleTargetRef:
 apiVersion: apps/v1
 kind: Deployment
 name: naas-agent-runtime
 minReplicas: 2
 maxReplicas: 50
 metrics:
 - type: Resource
 resource:
 name: cpu
 target:
 type: Utilization
 averageUtilization: 70
 - type: Resource
 resource:
 name: memory
 target:
 type: Utilization
 averageUtilization: 80
```

**Vertical Pod Autoscaler (VPA)**:
- Automatic resource request optimization
- Memory and CPU usage analysis
- Recommendation-based scaling
- Cost optimization through right-sizing

#### Managed Service Options

**AWS Deployment**:
- **EKS**: Managed Kubernetes with AWS integration
- **RDS**: Managed database with automatic backups
- **ElastiCache**: Redis caching for improved performance
- **ALB**: Application load balancer with SSL termination

**Google Cloud Deployment**:
- **GKE**: Google Kubernetes Engine with autopilot mode
- **Cloud SQL**: Managed PostgreSQL with high availability
- **Memorystore**: Managed Redis for caching
- **Cloud Load Balancing**: Global load balancing with CDN

**Azure Deployment**:
- **AKS**: Azure Kubernetes Service with Azure integration
- **Azure Database**: Managed PostgreSQL with geo-replication
- **Azure Cache**: Redis cache with clustering support
- **Application Gateway**: Layer 7 load balancing with WAF

### On-Premises Installation

#### Air-Gapped Environment Setup

**Complete Offline Operation**:
- No external internet connectivity required
- Local container registry for all images
- Offline model hosting and inference
- Local documentation and support resources

**Infrastructure Requirements**:
```yaml
# Minimum hardware specifications
control_plane:
 nodes: 3
 cpu_per_node: 8 cores
 memory_per_node: 32 GB
 storage_per_node: 500 GB SSD

worker_nodes:
 nodes: 5
 cpu_per_node: 16 cores
 memory_per_node: 64 GB
 storage_per_node: 1 TB SSD
 gpu_optional: NVIDIA A100 or equivalent

storage:
 distributed_storage: 10 TB minimum
 backup_storage: 20 TB minimum
 replication_factor: 3
```

**Local Model Hosting**:
- **Ollama Integration**: Local LLM hosting with GPU acceleration
- **Model Registry**: Private model repository with version control
- **Inference Scaling**: Automatic model loading and unloading
- **Custom Models**: Support for fine-tuned and domain-specific models

#### Hybrid Connectivity

**Secure External Connections**:
- **VPN Tunnels**: Site-to-site VPN for secure data access
- **API Gateways**: Controlled external API access with monitoring
- **Data Sync**: Scheduled synchronization with external data sources
- **Audit Logging**: Complete logging of all external communications

**Network Architecture**:
```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor': '#f8fafc', 'primaryTextColor': '#1e293b', 'primaryBorderColor': '#e2e8f0', 'lineColor': '#64748b'}}}%%
graph TD
 subgraph "On-Premises Network"
 A[Naas Platform]
 B[Local Data Sources]
 C[Enterprise Systems]
 end

 subgraph "DMZ"
 D[VPN Gateway]
 E[API Gateway]
 F[Firewall]
 end

 subgraph "External"
 G[Cloud APIs]
 H[Partner Systems]
 I[Public Data]
 end

 A --> D
 A --> E
 D --> G
 E --> H
 F --> I

 class A,B,C platform
 class D,E,F infrastructure
 class G,H,I external
```

#### Custom Infrastructure Integration

**Enterprise System Integration**:
- **Active Directory**: LDAP/SAML integration for authentication
- **Database Connections**: Direct connections to enterprise databases
- **Message Queues**: Integration with existing messaging systems
- **Monitoring Systems**: Integration with enterprise monitoring tools

**Hardware Optimization**:
- **GPU Clusters**: NVIDIA DGX or equivalent for AI workloads
- **High-Performance Storage**: NVMe SSD arrays for fast data access
- **Network Optimization**: 10GbE or higher for inter-node communication
- **Backup Systems**: Integration with enterprise backup solutions

### Government and Defense Deployments

#### FedRAMP Compliance

**FedRAMP Moderate Requirements**:
- **Security Controls**: Implementation of NIST SP 800-53 controls
- **Continuous Monitoring**: Real-time security monitoring and reporting
- **Incident Response**: Automated incident detection and response procedures
- **Documentation**: Complete system security documentation

**FedRAMP High Requirements**:
- **Enhanced Controls**: Additional security controls for high-impact systems
- **Cryptographic Standards**: FIPS 140-2 Level 3 or higher
- **Personnel Security**: Background check requirements for system access
- **Physical Security**: Enhanced physical security controls

#### DoD Compliance

**Security Requirements Guide (SRG) Compliance**:
- **STIG Implementation**: Security Technical Implementation Guides
- **Risk Management Framework**: NIST RMF implementation
- **Continuous Monitoring**: Real-time security posture assessment
- **Vulnerability Management**: Automated vulnerability scanning and remediation

**Classification Level Support**:
- **Unclassified**: Standard security controls
- **Controlled Unclassified Information (CUI)**: Enhanced data protection
- **Classified**: Support for classified data processing (with appropriate accreditation)

#### GovCloud Deployment

**AWS GovCloud Integration**:
- **Isolated Regions**: Physically and logically separated infrastructure
- **Compliance**: FedRAMP High and DoD SRG compliance
- **Personnel**: US persons-only access to infrastructure
- **Audit**: Enhanced audit logging and compliance reporting

**Azure Government Integration**:
- **Government Regions**: Dedicated government cloud regions
- **Compliance Certifications**: FedRAMP, DoD SRG, and other government standards
- **Data Residency**: Guaranteed US data residency
- **Support**: Government-cleared support personnel

#### SCIF Compatibility

**Sensitive Compartmented Information Facility Requirements**:
- **Physical Security**: Compliance with ICD/ICS 705 standards
- **Electromagnetic Security**: TEMPEST compliance for classified processing
- **Access Control**: Biometric and multi-factor authentication
- **Audit Trail**: Complete audit trail for all system access and operations

**Deployment Patterns**:
```yaml
# SCIF deployment configuration
scif_deployment:
 physical_security:
 - tempest_compliance: true
 - acoustic_protection: true
 - visual_protection: true

 network_security:
 - air_gapped: true
 - encrypted_storage: "AES-256"
 - secure_communications: "Suite B cryptography"

 access_control:
 - biometric_authentication: true
 - multi_factor_authentication: true
 - continuous_monitoring: true
```

### Deployment Planning

#### Requirements Assessment

**Security Requirements**:
- Compliance frameworks (FedRAMP, SOC 2, ISO 27001)
- Data classification and handling requirements
- Network security and segmentation needs
- Authentication and authorization requirements

**Performance Requirements**:
- Expected user load and concurrent sessions
- Data processing and storage requirements
- Response time and availability targets
- Disaster recovery and business continuity needs

**Integration Requirements**:
- Existing system integration points
- Data source connections and formats
- API requirements and rate limits
- Monitoring and logging integration

#### Architecture Design

**Reference Architectures**:
- **Small Deployment**: Single region, 100-500 users
- **Medium Deployment**: Multi-region, 500-5000 users
- **Large Deployment**: Global, 5000+ users with high availability
- **Government Deployment**: Air-gapped or GovCloud with enhanced security

**Capacity Planning**:
```yaml
# Capacity planning template
deployment_size: medium
expected_users: 2000
concurrent_users: 400
data_volume: 10TB
growth_rate: 20% annually

infrastructure:
 kubernetes_nodes: 12
 cpu_cores: 192
 memory_gb: 768
 storage_tb: 50
 network_bandwidth: "10 Gbps"
```

#### Implementation Timeline

**Phase 1: Foundation (Weeks 1-4)**:
- Infrastructure provisioning
- Network configuration and security setup
- Basic platform installation and configuration
- Initial testing and validation

**Phase 2: Integration (Weeks 5-8)**:
- Enterprise system integration
- Data source connections
- Authentication and authorization setup
- Security hardening and compliance validation

**Phase 3: Deployment (Weeks 9-12)**:
- Production deployment and cutover
- User onboarding and training
- Performance optimization and tuning
- Go-live support and monitoring setup

**Phase 4: Optimization (Weeks 13-16)**:
- Performance monitoring and optimization
- User feedback incorporation
- Additional feature enablement
- Long-term support transition

For detailed deployment planning assistance, contact our enterprise team at [enterprise@naas.ai](mailto:enterprise@naas.ai).
