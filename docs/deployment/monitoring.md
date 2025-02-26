# Monitoring

This guide outlines how to set up monitoring, logging, and alerting for the ABI framework in production environments.

## Monitoring Strategy

A comprehensive monitoring strategy for ABI includes:

1. **System Monitoring**: Track server health, resource usage, and infrastructure metrics
2. **Application Monitoring**: Monitor API performance, errors, and business metrics
3. **Database Monitoring**: Track database performance, connections, and query efficiency
4. **Ontology Store Monitoring**: Monitor the triple store's performance and health
5. **Log Management**: Centralize and analyze logs from all components
6. **Alerting**: Configure notifications for issues requiring attention
7. **Dashboarding**: Visualize system and application metrics

## Monitoring Stack

The recommended monitoring stack for ABI includes:

- **Prometheus**: For metrics collection and storage
- **Grafana**: For metrics visualization and dashboarding
- **Elasticsearch, Logstash, Kibana (ELK)**: For log aggregation and analysis
- **Alertmanager**: For alert routing and notifications
- **Node Exporter**: For system-level metrics
- **PostgreSQL Exporter**: For database metrics
- **Redis Exporter**: For Redis metrics
- **Blackbox Exporter**: For endpoint monitoring
- **Jaeger or Zipkin**: For distributed tracing

## Setting Up Prometheus

### 1. Install Prometheus

**Using Docker:**

```bash
docker run -d --name prometheus \
  -p 9090:9090 \
  -v /path/to/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

**Using Kubernetes:**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |-
    global:
      scrape_interval: 15s
    scrape_configs:
      - job_name: 'abi-api'
        metrics_path: '/metrics'
        static_configs:
          - targets: ['abi-api:9090']
      - job_name: 'abi-worker'
        metrics_path: '/metrics'
        static_configs:
          - targets: ['abi-worker:9090']
      # Additional scrape configs...

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config-volume
          mountPath: /etc/prometheus
      volumes:
      - name: config-volume
        configMap:
          name: prometheus-config
```

### 2. Configure Prometheus

Create a `prometheus.yml` configuration file:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

# Alertmanager configuration
alerting:
  alertmanagers:
  - static_configs:
    - targets:
      - alertmanager:9093

# Load rules once and periodically evaluate them
rule_files:
  - "rules/alert_rules.yml"

scrape_configs:
  # API servers
  - job_name: 'abi-api'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['api1:9090', 'api2:9090', 'api3:9090']
    
  # Worker nodes
  - job_name: 'abi-worker'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['worker1:9090', 'worker2:9090']
    
  # Node exporter for system metrics
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    
  # PostgreSQL exporter
  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']
    
  # Redis exporter
  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']
    
  # Triple store metrics
  - job_name: 'triplestore'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['triplestore:9090']
    
  # Blackbox exporter for endpoint monitoring
  - job_name: 'blackbox'
    metrics_path: '/probe'
    params:
      module: [http_2xx]
    static_configs:
      - targets:
        - https://api.example.com/health
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

### 3. Configure Alert Rules

Create alert rules in `rules/alert_rules.yml`:

```yaml
groups:
- name: abi_alerts
  rules:
  
  # API availability
  - alert: APIHighErrorRate
    expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High API error rate"
      description: "Error rate is above 5% ({{ $value | humanizePercentage }})"

  # System resources
  - alert: HighCPULoad
    expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU load"
      description: "CPU load is above 80% on {{ $labels.instance }}"
      
  - alert: HighMemoryUsage
    expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100 > 85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage"
      description: "Memory usage is above 85% on {{ $labels.instance }}"
      
  - alert: HighDiskUsage
    expr: (node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100 > 85
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High disk usage"
      description: "Disk usage is above 85% on {{ $labels.instance }} mount {{ $labels.mountpoint }}"

  # Database alerts
  - alert: DatabaseHighConnections
    expr: sum(pg_stat_activity_count) > 100
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High number of database connections"
      description: "There are over 100 active PostgreSQL connections"
      
  - alert: DatabaseSlowQueries
    expr: pg_stat_activity_max_tx_duration{datname="abi"} > 120
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Slow database queries detected"
      description: "Database has queries running for more than 2 minutes"
```

## Setting Up Grafana

### 1. Install Grafana

**Using Docker:**

```bash
docker run -d --name grafana \
  -p 3000:3000 \
  -v grafana-storage:/var/lib/grafana \
  grafana/grafana
```

**Using Kubernetes:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
      - name: grafana
        image: grafana/grafana:latest
        ports:
        - containerPort: 3000
        volumeMounts:
        - name: grafana-storage
          mountPath: /var/lib/grafana
      volumes:
      - name: grafana-storage
        persistentVolumeClaim:
          claimName: grafana-pvc
```

### 2. Configure Grafana

1. Login to Grafana (default: admin/admin)
2. Add Prometheus as a data source:
   - Name: Prometheus
   - Type: Prometheus
   - URL: http://prometheus:9090
   - Access: Server

### 3. Import Dashboards

Import these recommended dashboards:

1. **Node Exporter Dashboard** (ID: 1860)
2. **PostgreSQL Dashboard** (ID: 9628)
3. **Redis Dashboard** (ID: 763)
4. **API Server Dashboard** (custom)

Create a custom ABI API Dashboard with these panels:

1. **Request Rate**: `sum(rate(http_requests_total[5m])) by (status)`
2. **Response Time**: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`
3. **Error Rate**: `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`
4. **Pipeline Executions**: `sum(rate(pipeline_executions_total[5m])) by (pipeline, status)`
5. **Workflow Executions**: `sum(rate(workflow_executions_total[5m])) by (workflow, status)`
6. **Ontology Store Queries**: `sum(rate(ontology_queries_total[5m])) by (store)`
7. **Integration Calls**: `sum(rate(integration_calls_total[5m])) by (integration, status)`

## Log Management with ELK Stack

### 1. Set Up Elasticsearch

**Using Docker Compose:**

```yaml
version: '3'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.15.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - 9200:9200
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
```

### 2. Set Up Logstash

Create a Logstash configuration file:

```
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][component] == "api" {
    grok {
      match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:log_level} \[%{DATA:service}\] \[%{DATA:trace_id}\] %{GREEDYDATA:log_message}" }
    }
  }
  
  if [fields][component] == "worker" {
    grok {
      match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} %{LOGLEVEL:log_level} \[%{DATA:service}\] \[%{DATA:task_id}\] %{GREEDYDATA:log_message}" }
    }
  }
  
  if [log_level] == "ERROR" or [log_level] == "CRITICAL" {
    mutate {
      add_tag => ["error"]
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "abi-%{fields.component}-%{+YYYY.MM.dd}"
  }
}
```

### 3. Set Up Filebeat

Create a Filebeat configuration file:

```yaml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/abi/api/*.log
  fields:
    component: api

- type: log
  enabled: true
  paths:
    - /var/log/abi/worker/*.log
  fields:
    component: worker

- type: log
  enabled: true
  paths:
    - /var/log/abi/ontology/*.log
  fields:
    component: ontology

output.logstash:
  hosts: ["logstash:5044"]
```

### 4. Set Up Kibana

**Using Docker Compose:**

```yaml
kibana:
  image: docker.elastic.co/kibana/kibana:7.15.0
  ports:
    - 5601:5601
  environment:
    ELASTICSEARCH_HOSTS: http://elasticsearch:9200
```

### 5. Configure Index Patterns in Kibana

1. Open Kibana at http://localhost:5601
2. Go to Management > Stack Management > Index Patterns
3. Create index pattern `abi-*`
4. Set the Time Filter field to `@timestamp`

## Distributed Tracing with Jaeger

### 1. Install Jaeger

**Using Docker:**

```bash
docker run -d --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 5775:5775/udp \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 14268:14268 \
  -p 14250:14250 \
  -p 9411:9411 \
  jaegertracing/all-in-one:latest
```

### 2. Configure ABI for Tracing

Set these environment variables:

```
ABI_TRACE_ENABLED=true
ABI_TRACE_SAMPLE_RATE=0.1
ABI_TRACE_JAEGER_ENDPOINT=http://jaeger:14268/api/traces
```

### 3. Access Jaeger UI

Open Jaeger UI at http://localhost:16686

## Instrumenting ABI

### 1. Enable Prometheus Metrics in ABI

Set these environment variables:

```
ABI_ENABLE_METRICS=true
ABI_METRICS_PORT=9090
```

### 2. Expose Metrics in API Code

```python
from prometheus_client import Counter, Histogram, start_http_server
import time

# Initialize metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
PIPELINE_EXECUTIONS = Counter('pipeline_executions_total', 'Pipeline executions', ['pipeline', 'status'])
WORKFLOW_EXECUTIONS = Counter('workflow_executions_total', 'Workflow executions', ['workflow', 'status'])
ONTOLOGY_QUERIES = Counter('ontology_queries_total', 'Ontology queries', ['store'])
INTEGRATION_CALLS = Counter('integration_calls_total', 'Integration API calls', ['integration', 'status'])

# Start metrics server
start_http_server(9090)

# Use metrics in request handler
@app.route('/api/v1/resource')
def get_resource():
    start_time = time.time()
    try:
        # Process request
        status_code = 200
        return jsonify({"status": "success"})
    except Exception as e:
        status_code = 500
        raise e
    finally:
        REQUEST_COUNT.labels('GET', '/api/v1/resource', status_code).inc()
        REQUEST_LATENCY.labels('GET', '/api/v1/resource').observe(time.time() - start_time)
```

### 3. Configure Logging

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "service": "abi-api",
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if hasattr(record, 'trace_id'):
            log_record["trace_id"] = record.trace_id
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging():
    logger = logging.getLogger("abi")
    handler = logging.StreamHandler()
    
    if os.environ.get("ABI_LOG_FORMAT") == "json":
        handler.setFormatter(JSONFormatter())
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [%(trace_id)s] %(message)s")
        handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("ABI_LOG_LEVEL", "INFO"))
    
    return logger
```

## Setting Up Alerting

### 1. Install Alertmanager

**Using Docker:**

```bash
docker run -d --name alertmanager \
  -p 9093:9093 \
  -v /path/to/alertmanager.yml:/etc/alertmanager/alertmanager.yml \
  prom/alertmanager
```

### 2. Configure Alertmanager

Create an `alertmanager.yml` configuration file:

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'

route:
  group_by: ['alertname', 'instance']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'slack-notifications'
  routes:
  - match:
      severity: critical
    receiver: 'pagerduty-critical'
  - match:
      severity: warning
    receiver: 'slack-notifications'

receivers:
- name: 'slack-notifications'
  slack_configs:
  - channel: '#abi-alerts'
    send_resolved: true
    title: '[{{ .Status | toUpper }}] {{ .CommonLabels.alertname }}'
    text: >-
      {{ range .Alerts }}
        *Alert:* {{ .Annotations.summary }}
        *Description:* {{ .Annotations.description }}
        *Severity:* {{ .Labels.severity }}
        *Instance:* {{ .Labels.instance }}
      {{ end }}

- name: 'pagerduty-critical'
  pagerduty_configs:
  - service_key: YOUR_PAGERDUTY_SERVICE_KEY
    send_resolved: true
```

## Health Checks

### 1. Implement Health Check Endpoints

```python
@app.route('/health')
def basic_health_check():
    return jsonify({
        "status": "healthy",
        "version": "1.0.0"
    })

@app.route('/health/detailed')
def detailed_health_check():
    db_status = check_database_connection()
    redis_status = check_redis_connection()
    ontology_status = check_ontology_store()
    
    all_healthy = all([
        db_status["healthy"],
        redis_status["healthy"], 
        ontology_status["healthy"]
    ])
    
    return jsonify({
        "status": "healthy" if all_healthy else "unhealthy",
        "version": "1.0.0",
        "components": {
            "database": db_status,
            "redis": redis_status,
            "ontology": ontology_status
        }
    })
```

### 2. Set Up Blackbox Monitoring

Configure Blackbox Exporter for endpoint monitoring:

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      preferred_ip_protocol: "ip4"
      valid_status_codes: [200]
      method: GET
  
  http_json:
    prober: http
    timeout: 5s
    http:
      preferred_ip_protocol: "ip4"
      valid_status_codes: [200]
      method: GET
      fail_if_body_not_matches_regexp:
        - '"status":"healthy"'
```

## Monitoring Checklist

Use this checklist to ensure your monitoring setup is complete:

- [ ] **System Monitoring**
  - [ ] CPU, memory, disk usage monitoring
  - [ ] Network I/O monitoring
  - [ ] Host-level alerts configured

- [ ] **Application Monitoring**
  - [ ] API endpoints instrumented with metrics
  - [ ] Request counts, error rates, latencies tracked
  - [ ] Custom business metrics defined
  - [ ] Application-level alerts configured

- [ ] **Database Monitoring**
  - [ ] Connection pool metrics
  - [ ] Query performance metrics
  - [ ] PostgreSQL specific metrics
  - [ ] Database alerts configured

- [ ] **Ontology Store Monitoring**
  - [ ] Query metrics configured
  - [ ] Performance metrics tracked
  - [ ] Storage metrics monitored
  - [ ] Ontology-specific alerts configured

- [ ] **Log Management**
  - [ ] Centralized logging set up
  - [ ] Log parsing and analysis configured
  - [ ] Log retention policy defined
  - [ ] Log-based alerts configured

- [ ] **Alerting**
  - [ ] Notification channels configured
  - [ ] Escalation policies defined
  - [ ] On-call rotations established
  - [ ] Alert documentation created

- [ ] **Dashboards**
  - [ ] System dashboard
  - [ ] Application dashboard
  - [ ] Database dashboard
  - [ ] Business metrics dashboard

## Best Practices

1. **Monitor What Matters**: Focus on metrics that indicate user experience and business value
2. **Set Meaningful Thresholds**: Configure alert thresholds based on business impact
3. **Reduce Alert Noise**: Only alert on actionable issues to prevent alert fatigue
4. **Document Everything**: Maintain runbooks for each alert with troubleshooting steps
5. **Use Anomaly Detection**: Implement trend-based alerting when possible
6. **Test Your Monitoring**: Regularly verify that alerts work correctly
7. **Monitor the Monitors**: Set up meta-monitoring to ensure your monitoring system is operational
8. **Correlate Metrics**: Build dashboards that show related metrics together for better context
9. **Keep History**: Retain enough metric history to understand trends
10. **Continuous Improvement**: Regularly review and refine your monitoring setup

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/introduction/overview/)
- [Grafana Documentation](https://grafana.com/docs/)
- [ELK Stack Documentation](https://www.elastic.co/guide/index.html)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/) 