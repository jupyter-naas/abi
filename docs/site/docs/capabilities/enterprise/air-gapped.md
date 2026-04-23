---
sidebar_position: 2
---

# Air-Gapped Deployment

Deploy Naas in completely isolated networks without internet connectivity while maintaining full AI and analytics capabilities. This guide covers offline installation, local model hosting, and secure data processing patterns.

:::info Professional Services Implementation
The enterprise capabilities described in this section represent our ability to implement these solutions through our professional services team. Each deployment is customized to your specific requirements and implemented with dedicated support. Contact our enterprise team at [support@naas.ai](mailto:support@naas.ai) to discuss your needs and implementation timeline.
:::

## Overview

Air-gapped deployment enables organizations with the highest security requirements to leverage Naas's AI capabilities while ensuring no data exfiltration or external dependencies. This includes government agencies, defense contractors, financial institutions, and any organization handling classified or highly sensitive information.

## Pre-Deployment Planning

### Network Architecture
- **Complete isolation**: No inbound or outbound internet connectivity
- **Internal DNS**: Local DNS resolution for service discovery
- **Certificate management**: Internal CA for TLS certificates
- **Time synchronization**: Local NTP servers for accurate timestamps

### Infrastructure Requirements
- **Container runtime**: Docker or Podman for containerized deployment
- **Orchestration**: Kubernetes cluster for production deployments
- **Storage**: High-availability storage for persistent data
- **Compute**: GPU nodes for local AI model inference

## Offline Installation Process

### 1. Dependency Preparation

Create an offline installation package containing all required components:

```bash
# Create offline package directory
mkdir naas-offline-package
cd naas-offline-package

# Download container images
docker pull jupyter/naas:latest
docker pull postgres:13
docker pull redis:6
docker pull nginx:1.21

# Save images as tar files
docker save jupyter/naas:latest > naas-core.tar
docker save postgres:13 > postgres.tar
docker save redis:6 > redis.tar
docker save nginx:1.21 > nginx.tar

# Download Python packages
pip download --dest ./python-packages naas naas-python
pip download --dest ./python-packages -r requirements.txt

# Package AI models
mkdir ai-models
# Download and package your selected models
```bash

### 2. Secure Transfer

Transfer the offline package to the air-gapped environment:

```bash
# Create checksums for integrity verification
sha256sum *.tar python-packages/* > checksums.txt

# Create encrypted archive
tar czf naas-offline.tar.gz *
gpg --symmetric --cipher-algo AES256 naas-offline.tar.gz

# Transfer via approved secure media
# Verify checksums after transfer
```bash

### 3. Environment Setup

Install Naas in the air-gapped environment:

```bash
# Load container images
docker load < naas-core.tar
docker load < postgres.tar
docker load < redis.tar
docker load < nginx.tar

# Set up local package repository
python -m http.server --directory python-packages 8080

# Install Naas with local packages
pip install --index-url http://localhost:8080 --trusted-host localhost naas
```bash

## Local AI Model Configuration

### Model Selection

Choose appropriate models for offline deployment:

#### Open-Source Models
- **Llama 2/3**: Meta's open-source models for general-purpose tasks
- **Code Llama**: Specialized for code generation and analysis
- **Mistral**: Efficient models for various text tasks
- **Sentence Transformers**: For embedding generation and semantic search

#### Model Hosting Infrastructure

Set up local model serving:

```yaml
# docker-compose.yml for model serving
version: '3.8'
services:
 ollama-service:
 image: ollama/ollama:latest
 volumes:
 - ./models:/root/.ollama
 ports:
 - "11434:11434"
 environment:
 - OLLAMA_HOST=0.0.0.0
 deploy:
 resources:
 reservations:
 devices:
 - driver: nvidia
 count: 1
 capabilities: [gpu]
```bash

### Model Configuration

Configure Naas to use local models:

```python
# .env configuration for air-gapped deployment
OPENAI_API_BASE=http://localhost:11434/v1
OPENAI_API_KEY=not-required-for-local
MODEL_PROVIDER=ollama

# Agent configuration for local models
from abi.services.agent.Agent import Agent

agent = Agent(
 name="Local Agent",
 chat_model=ChatOpenAI(
 base_url="http://localhost:11434/v1",
 api_key="not-required",
 model="llama2:7b"
 )
)
```bash

## Data Security and Isolation

### Storage Encryption

Implement comprehensive encryption for data at rest:

```yaml
# Storage configuration with encryption
apiVersion: v1
kind: StorageClass
metadata:
 name: encrypted-storage
provisioner: kubernetes.io/aws-ebs
parameters:
 type: gp3
 encrypted: "true"
 kmsKeyId: alias/k8s-storage-key
```bash

### Network Policies

Implement strict network segmentation:

```yaml
# Kubernetes NetworkPolicy for service isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
 name: naas-isolation
spec:
 podSelector:
 matchLabels:
 app: naas
 policyTypes:
 - Ingress
 - Egress
 ingress:
 - from:
 - podSelector:
 matchLabels:
 app: naas-frontend
 ports:
 - protocol: TCP
 port: 8000
 egress:
 - to:
 - podSelector:
 matchLabels:
 app: postgres
 ports:
 - protocol: TCP
 port: 5432
```bash

## Monitoring and Observability

### Offline Monitoring Stack

Deploy monitoring without external dependencies:

```yaml
# Prometheus configuration for air-gapped monitoring
global:
 scrape_interval: 15s
 external_labels:
 environment: 'airgap'

scrape_configs:
 - job_name: 'naas-services'
 static_configs:
 - targets: ['naas-api:8000', 'naas-worker:8001']
 metrics_path: /metrics
 scrape_interval: 30s

 - job_name: 'kubernetes-pods'
 kubernetes_sd_configs:
 - role: pod
 relabel_configs:
 - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
 action: keep
 regex: true
```bash

### Log Management

Centralized logging for audit and troubleshooting:

```yaml
# Fluentd configuration for log collection
apiVersion: v1
kind: ConfigMap
metadata:
 name: fluentd-config
data:
 fluent.conf: |
 <source>
 @type tail
 path /var/log/containers/naas-*.log
 pos_file /var/log/fluentd-naas.log.pos
 tag kubernetes.naas
 format json
 </source>

 <match kubernetes.naas>
 @type elasticsearch
 host elasticsearch.logging.svc.cluster.local
 port 9200
 index_name naas-logs
 </match>
```bash

## Update and Maintenance Procedures

### Offline Updates

Establish procedures for updating the air-gapped installation:

1. **Preparation Phase**
 - Download updates in connected environment
 - Test updates in isolated staging environment
 - Create update packages with integrity verification

2. **Transfer Phase**
 - Use approved secure media for transfer
 - Verify checksums and signatures
 - Document all transferred components

3. **Deployment Phase**
 - Schedule maintenance window
 - Create system backup before updates
 - Apply updates using rolling deployment
 - Verify functionality post-update

### Backup Strategies

Implement comprehensive backup for disaster recovery:

```bash
#!/bin/bash
# Air-gapped backup script

BACKUP_DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/secure-backup/naas-$BACKUP_DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database backup
kubectl exec postgres-0 -- pg_dump -U naas naas_db > "$BACKUP_DIR/database.sql"

# Configuration backup
kubectl get configmap naas-config -o yaml > "$BACKUP_DIR/config.yaml"
kubectl get secret naas-secrets -o yaml > "$BACKUP_DIR/secrets.yaml"

# Persistent volume backup
kubectl exec naas-worker-0 -- tar czf - /data > "$BACKUP_DIR/persistent-data.tar.gz"

# Encrypt backup
gpg --symmetric --cipher-algo AES256 --compress-algo 2 "$BACKUP_DIR.tar.gz"

# Store on secure media
mv "$BACKUP_DIR.tar.gz.gpg" /secure-media/
```bash

## Security Hardening

### Container Security

Implement container security best practices:

```dockerfile
# Hardened Naas container
FROM python:3.9-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash naas

# Install security updates only
RUN apt-get update && apt-get upgrade -y && \
 apt-get install --no-install-recommends -y \
 ca-certificates && \
 rm -rf /var/lib/apt/lists/*

# Set up application
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER naas
COPY --chown=naas:naas . .

# Security labels
LABEL security.no-new-privileges=true
LABEL security.read-only-root-filesystem=true

EXPOSE 8000
CMD ["python", "app.py"]
```bash

### Access Controls

Implement strict access controls:

```yaml
# RBAC configuration for Naas
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
 name: naas-operator
rules:
- apiGroups: [""]
 resources: ["pods", "configmaps", "secrets"]
 verbs: ["get", "list", "watch", "create", "update", "patch"]
- apiGroups: ["apps"]
 resources: ["deployments", "replicasets"]
 verbs: ["get", "list", "watch", "create", "update", "patch"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
 name: naas-operator-binding
subjects:
- kind: ServiceAccount
 name: naas-operator
 namespace: naas
roleRef:
 kind: Role
 name: naas-operator
 apiGroup: rbac.authorization.k8s.io
```bash

## Compliance and Auditing

### Audit Logging

Enable comprehensive audit logging:

```yaml
# Kubernetes audit policy
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: Metadata
 namespaces: ["naas"]
 resources:
 - group: ""
 resources: ["secrets", "configmaps"]
 - group: "apps"
 resources: ["deployments"]

- level: Request
 namespaces: ["naas"]
 verbs: ["create", "update", "patch", "delete"]
```bash

### Compliance Reporting

Generate compliance reports for audit purposes:

```python
# Compliance reporting script
import json
from datetime import datetime, timedelta

def generate_compliance_report(start_date, end_date):
 report = {
 "report_id": f"naas-compliance-{datetime.now().strftime('%Y%m%d')}",
 "period": {
 "start": start_date.isoformat(),
 "end": end_date.isoformat()
 },
 "security_events": [],
 "access_logs": [],
 "data_processing": [],
 "model_usage": []
 }

 # Collect security events
 security_events = query_security_logs(start_date, end_date)
 report["security_events"] = security_events

 # Collect access logs
 access_logs = query_access_logs(start_date, end_date)
 report["access_logs"] = access_logs

 return report
```bash

## Troubleshooting Common Issues

### Model Loading Problems

If local models fail to load:

```bash
# Check model availability
ollama list

# Verify model file integrity
sha256sum /models/llama2-7b.bin

# Check model server logs
docker logs ollama-service

# Test model endpoint
curl http://localhost:11434/api/generate \
 -d '{"model": "llama2:7b", "prompt": "test"}'
```bash

### Network Connectivity Issues

Debug internal network problems:

```bash
# Test internal DNS resolution
nslookup naas-api.naas.svc.cluster.local

# Check service connectivity
kubectl exec -it naas-worker-0 -- nc -zv naas-api 8000

# Verify network policies
kubectl describe networkpolicy naas-isolation
```bash

### Storage and Performance

Monitor and optimize storage performance:

```bash
# Check disk usage
df -h /data

# Monitor I/O performance
iostat -x 1

# Check database performance
kubectl exec postgres-0 -- psql -U naas -c "SELECT * FROM pg_stat_activity;"
```

This air-gapped deployment approach ensures that organizations can leverage Naas's full AI capabilities while maintaining the highest levels of security and data isolation.
