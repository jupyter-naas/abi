# Production Setup

This document provides instructions for deploying ABI to a production environment, including infrastructure requirements, installation steps, and best practices for a secure and scalable deployment.

## Infrastructure Requirements

### Hardware Requirements

- **API Servers**:
  - Minimum: 4 vCPUs, 8 GB RAM
  - Recommended: 8 vCPUs, 16 GB RAM
  - Storage: 100 GB SSD

- **Database Server**:
  - Minimum: 4 vCPUs, 16 GB RAM
  - Recommended: 8 vCPUs, 32 GB RAM
  - Storage: 500 GB SSD

- **Triple Store (for Ontology)**:
  - Minimum: 4 vCPUs, 16 GB RAM
  - Recommended: 8 vCPUs, 32 GB RAM
  - Storage: 1 TB SSD

- **Worker Nodes** (for background tasks):
  - Minimum: 4 vCPUs, 8 GB RAM
  - Recommended: 8 vCPUs, 16 GB RAM
  - Storage: 100 GB SSD

### Cloud Provider Recommendations

ABI can be deployed on any major cloud provider:

- **AWS**:
  - EC2 instances for API servers
  - RDS for PostgreSQL database
  - Neptune for graph database
  - ElastiCache for Redis
  - S3 for storage
  - ELB for load balancing

- **Azure**:
  - Virtual Machines for API servers
  - Azure Database for PostgreSQL
  - Azure Cosmos DB for graph database
  - Azure Cache for Redis
  - Azure Blob Storage
  - Azure Load Balancer

- **Google Cloud**:
  - Compute Engine VMs for API servers
  - Cloud SQL for PostgreSQL
  - Cloud Memorystore for Redis
  - Cloud Storage
  - Cloud Load Balancing

### Network Requirements

- **Load Balancer**: To distribute traffic across API servers
- **CDN**: For static content delivery
- **VPC**: Private network for internal communication
- **NAT Gateway**: For outbound internet access from private subnets
- **Firewall Rules**:
  - Allow inbound traffic on ports 80/443 to load balancer
  - Allow internal communication on required ports
  - Restrict database access to application servers

## Deployment Architecture

Here's a recommended architecture for production deployments:

```
                                 ┌─────────────┐
                                 │    CDN      │
                                 └──────┬──────┘
                                        │
                                        ▼
                ┌─────────────┐   ┌──────────────┐   ┌─────────────┐
                │  WAF/DDOS   │◄──┤Load Balancer │──►│ SSL Termination │
                │ Protection  │   └──────┬───────┘   └─────────────┘
                └─────────────┘          │
                                         │
                                         ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│                │  │                │  │                │
│  API Server 1  │  │  API Server 2  │  │  API Server 3  │
│                │  │                │  │                │
└───────┬────────┘  └────────┬───────┘  └────────┬───────┘
        │                    │                    │
        └───────────┬────────┴──────────┬────────┘
                    │                   │
     ┌──────────────▼─────┐    ┌────────▼────────────┐
     │                    │    │                     │
     │  PostgreSQL DB     │    │  Triple Store       │
     │  (Primary/Replica) │    │  (Ontology Store)   │
     │                    │    │                     │
     └────────────────────┘    └─────────────────────┘
                │                       │
     ┌──────────▼─────────┐   ┌─────────▼────────┐
     │                    │   │                  │
     │   Redis Cache      │   │   Object         │
     │                    │   │   Storage        │
     └────────────────────┘   └──────────────────┘
                │
     ┌──────────▼─────────┐   ┌──────────────────┐
     │                    │   │                  │
     │   Worker Nodes     │◄──┤  Message Queue   │
     │                    │   │                  │
     └────────────────────┘   └──────────────────┘
```

## Deployment Methods

### 1. Docker Containers (Recommended)

#### Prerequisites

- Docker and Docker Compose
- Container orchestration platform (Kubernetes, ECS, etc.)

#### Deployment Steps

1. **Build Docker Images**:

   ```bash
   # Build API image
   docker build -t abi-api:${VERSION} -f docker/api/Dockerfile .
   
   # Build worker image
   docker build -t abi-worker:${VERSION} -f docker/worker/Dockerfile .
   ```

2. **Push Images to Container Registry**:

   ```bash
   # Tag images
   docker tag abi-api:${VERSION} your-registry/abi-api:${VERSION}
   docker tag abi-worker:${VERSION} your-registry/abi-worker:${VERSION}
   
   # Push images
   docker push your-registry/abi-api:${VERSION}
   docker push your-registry/abi-worker:${VERSION}
   ```

3. **Deploy with Kubernetes**:

   Create Kubernetes manifests in `k8s/` directory:

   ```yaml
   # api-deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: abi-api
   spec:
     replicas: 3
     selector:
       matchLabels:
         app: abi-api
     template:
       metadata:
         labels:
           app: abi-api
       spec:
         containers:
         - name: abi-api
           image: your-registry/abi-api:${VERSION}
           ports:
           - containerPort: 8000
           env:
           - name: DATABASE_URL
             valueFrom:
               secretKeyRef:
                 name: abi-secrets
                 key: database-url
           # Add more environment variables
           resources:
             requests:
               memory: "8Gi"
               cpu: "2"
             limits:
               memory: "16Gi"
               cpu: "4"
           readinessProbe:
             httpGet:
               path: /health
               port: 8000
             initialDelaySeconds: 5
             periodSeconds: 10
   ```

   Apply the manifests:

   ```bash
   kubectl apply -f k8s/
   ```

### 2. Virtual Machines

#### Prerequisites

- Linux servers (Ubuntu 20.04 LTS recommended)
- Python 3.8 or higher
- PostgreSQL 13+
- Redis 6+
- Nginx

#### Deployment Steps

1. **Prepare the Server**:

   ```bash
   # Update system packages
   sudo apt update
   sudo apt upgrade -y
   
   # Install dependencies
   sudo apt install -y python3-pip python3-venv nginx postgresql redis-server
   ```

2. **Create a Service User**:

   ```bash
   sudo useradd -m -s /bin/bash abi
   sudo mkdir -p /opt/abi
   sudo chown abi:abi /opt/abi
   ```

3. **Deploy the Application**:

   ```bash
   # As abi user
   sudo su - abi
   cd /opt/abi
   
   # Clone the repository
   git clone https://github.com/yourusername/abi.git .
   git checkout v1.2.3  # Use specific version tag
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install --no-cache-dir -r requirements.txt
   
   # Create configuration
   cp config/production.yaml.example config/production.yaml
   # Edit the config file with your settings
   
   # Run database migrations
   python manage.py migrate
   
   # Collect static files
   python manage.py collectstatic --noinput
   ```

4. **Configure Systemd Services**:

   Create service files for API and worker processes:

   ```
   # /etc/systemd/system/abi-api.service
   [Unit]
   Description=ABI API Service
   After=network.target
   
   [Service]
   User=abi
   Group=abi
   WorkingDirectory=/opt/abi
   ExecStart=/opt/abi/venv/bin/gunicorn -c gunicorn_config.py abi.wsgi:application
   Restart=on-failure
   
   [Install]
   WantedBy=multi-user.target
   ```

   ```
   # /etc/systemd/system/abi-worker.service
   [Unit]
   Description=ABI Worker Service
   After=network.target
   
   [Service]
   User=abi
   Group=abi
   WorkingDirectory=/opt/abi
   ExecStart=/opt/abi/venv/bin/celery -A abi worker --loglevel=info
   Restart=on-failure
   
   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start the services:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable abi-api abi-worker
   sudo systemctl start abi-api abi-worker
   ```

5. **Configure Nginx**:

   Create Nginx configuration:

   ```
   # /etc/nginx/sites-available/abi
   server {
       listen 80;
       server_name api.example.com;
   
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   
       location /static/ {
           alias /opt/abi/static/;
       }
   }
   ```

   Enable the site:

   ```bash
   sudo ln -s /etc/nginx/sites-available/abi /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

6. **Set Up SSL with Let's Encrypt**:

   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d api.example.com
   ```

## Database Setup

### PostgreSQL Setup

1. **Create Database and User**:

   ```sql
   CREATE DATABASE abi;
   CREATE USER abi_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE abi TO abi_user;
   ```

2. **Configure PostgreSQL**:

   Edit `postgresql.conf` for production settings:

   ```
   # Memory settings
   shared_buffers = 4GB
   effective_cache_size = 12GB
   maintenance_work_mem = 1GB
   work_mem = 64MB
   
   # Write-ahead log
   wal_level = replica
   max_wal_senders = 10
   wal_keep_segments = 64
   
   # Query optimization
   random_page_cost = 1.1
   effective_io_concurrency = 200
   
   # Checkpoints
   checkpoint_timeout = 15min
   checkpoint_completion_target = 0.9
   ```

3. **Setup Replication** (recommended for production):

   Configure a primary-replica setup for high availability.

### Triple Store Setup

1. **Install Apache Jena Fuseki** (or your chosen triple store):

   ```bash
   wget https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-4.7.0.tar.gz
   tar -xzf apache-jena-fuseki-4.7.0.tar.gz
   cd apache-jena-fuseki-4.7.0
   ```

2. **Configure Triple Store**:

   Create a configuration file:

   ```
   # config.ttl
   @prefix fuseki:  <http://jena.apache.org/fuseki#> .
   @prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
   @prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
   @prefix tdb2:    <http://jena.apache.org/2016/tdb#> .
   @prefix ja:      <http://jena.hpl.hp.com/2005/11/Assembler#> .
   
   fuseki:service a fuseki:Service ;
     rdfs:label "ABI Ontology Store" ;
     fuseki:name "abi" ;
     fuseki:endpoint [ fuseki:operation fuseki:query ; ] ;
     fuseki:endpoint [ fuseki:operation fuseki:update ; ] ;
     fuseki:endpoint [ fuseki:operation fuseki:gsp-r ; ] ;
     fuseki:endpoint [ fuseki:operation fuseki:gsp-rw ; ] ;
     fuseki:dataset <#dataset> ;
     .
   
   <#dataset> a tdb2:DatasetTDB2 ;
     tdb2:location "DB2" ;
     .
   ```

3. **Start the Triple Store**:

   ```bash
   ./fuseki-server --config=config.ttl
   ```

## Security Best Practices

### Application Security

1. **Secure Configuration**:
   - Use environment variables for secrets
   - Implement strong encryption for sensitive data
   - Never commit secrets to version control

2. **Authentication**:
   - Implement strong password policies
   - Use multi-factor authentication for admin access
   - Set up proper session management

3. **API Security**:
   - Implement rate limiting
   - Use API keys with appropriate scopes
   - Validate all input data

### Network Security

1. **Firewall Configuration**:
   - Restrict access to only necessary ports
   - Implement network ACLs
   - Use security groups in cloud environments

2. **SSL/TLS**:
   - Use strong TLS protocols (TLS 1.2+)
   - Configure secure cipher suites
   - Implement HSTS

3. **DDoS Protection**:
   - Use a CDN or DDoS protection service
   - Implement rate limiting at the load balancer
   - Configure auto-scaling for traffic spikes

### Data Security

1. **Database Security**:
   - Use strong passwords
   - Restrict network access to database servers
   - Encrypt sensitive data
   - Regularly backup data

2. **Data Encryption**:
   - Encrypt data in transit
   - Encrypt sensitive data at rest
   - Manage encryption keys securely

## Monitoring and Logging

### Monitoring Stack

1. **System Monitoring**:
   - Set up Prometheus for metrics collection
   - Use Grafana for visualization
   - Configure alerts for critical metrics

2. **Application Monitoring**:
   - Implement health check endpoints
   - Set up API endpoint monitoring
   - Track application performance metrics

3. **Log Management**:
   - Centralize logs with ELK stack or similar
   - Set up log rotation
   - Monitor for error patterns

### Key Metrics to Monitor

- **System Metrics**:
  - CPU, memory, disk usage
  - Network I/O
  - Disk I/O

- **Application Metrics**:
  - Request rate
  - Error rate
  - Response time
  - Queue depth for background tasks

- **Database Metrics**:
  - Query performance
  - Connection count
  - Transaction rate
  - Cache hit ratio

## Backup and Disaster Recovery

### Backup Strategy

1. **Database Backups**:
   - Daily full backups
   - Hourly incremental backups
   - Regular backup testing

2. **File Backups**:
   - Daily configuration backups
   - Media and uploaded files backup

3. **Application State**:
   - Version-controlled configuration
   - Infrastructure as Code templates

### Disaster Recovery Plan

1. **Recovery Time Objectives** (RTO):
   - Define maximum acceptable downtime
   - Create procedures for different failure scenarios

2. **Recovery Point Objectives** (RPO):
   - Define acceptable data loss
   - Align backup strategy with RPO

3. **Disaster Recovery Procedures**:
   - Document step-by-step recovery procedures
   - Regularly test recovery procedures
   - Update documentation after tests

## Scaling Strategies

### Horizontal Scaling

- Add more API servers behind load balancer
- Implement auto-scaling based on metrics
- Use container orchestration for dynamic scaling

### Vertical Scaling

- Increase resources (CPU, RAM) for existing servers
- Optimize database performance
- Upgrade to higher-performance instances

### Caching Strategies

- Implement Redis for caching
- Use CDN for static assets
- Consider database query caching

## Maintenance Procedures

### Regular Maintenance

1. **Updates and Patches**:
   - Establish a regular update schedule
   - Test updates in staging environment
   - Document update procedures

2. **Database Maintenance**:
   - Regular vacuuming and optimization
   - Index maintenance
   - Query optimization

3. **Log Rotation**:
   - Configure automated log rotation
   - Archive old logs
   - Monitor log storage

### Deployment Process

1. **Deployment Checklist**:
   - Pre-deployment validation
   - Deployment steps
   - Post-deployment verification

2. **Rollback Procedures**:
   - Document rollback steps
   - Test rollback procedures
   - Define rollback triggers

## Troubleshooting Common Issues

### Application Issues

1. **API Server Not Responding**:
   - Check server logs
   - Verify network connectivity
   - Check resource utilization

2. **Slow Response Times**:
   - Monitor database performance
   - Check for resource exhaustion
   - Analyze API endpoint performance

### Database Issues

1. **Connection Issues**:
   - Check connection pool settings
   - Verify network connectivity
   - Check authentication configuration

2. **Performance Problems**:
   - Analyze slow queries
   - Check for missing indexes
   - Monitor resource utilization

## Production Checklist

Before going live, ensure you've completed this checklist:

- [ ] All environment variables are properly set
- [ ] Database is properly configured with replication
- [ ] Monitoring and alerting is set up
- [ ] Backup processes are in place and tested
- [ ] SSL certificates are installed and valid
- [ ] Security hardening is complete
- [ ] Load testing has been performed
- [ ] Documentation is up to date
- [ ] Deployment and rollback procedures are documented
- [ ] Support and escalation procedures are in place

## Additional Resources

- [AWS Deployment Guide](https://docs.aws.amazon.com/)
- [Azure Deployment Guide](https://docs.microsoft.com/azure/)
- [Google Cloud Deployment Guide](https://cloud.google.com/docs/)
- [PostgreSQL Production Checklist](https://wiki.postgresql.org/wiki/Don't_Do_This)
- [OWASP Security Best Practices](https://owasp.org/www-project-top-ten/) 