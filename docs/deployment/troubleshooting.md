# Troubleshooting

This guide provides solutions for common issues you might encounter when running the ABI framework in production environments.

## Diagnostic Tools

Before diving into specific problems, familiarize yourself with these diagnostic tools:

1. **Health Check Endpoints**: Use the `/health` and `/health/detailed` endpoints to check component status
2. **Logs**: Check application logs in `/var/log/abi/` (default location)
3. **Monitoring Dashboards**: Review Grafana dashboards for anomalies
4. **Database Command-Line**: Use `psql` to connect directly to the PostgreSQL database
5. **Ontology Store Query Interface**: Use the SPARQL endpoint to query the triple store directly
6. **API Testing Tools**: Use tools like `curl` or Postman to test API endpoints

## Common Issues and Solutions

### API Service Issues

#### API Service Not Starting

**Symptoms**:
- The ABI API service fails to start
- Error messages in the logs about configuration or dependencies

**Potential Causes and Solutions**:

1. **Missing Environment Variables**
   - Check if all required environment variables are set
   - Verify values are correct in your `.env` file or environment
   ```bash
   cat /etc/abi/api.env
   ```

2. **Database Connection Issues**
   - Verify the database server is running
   - Check database credentials and connection string
   - Test connection manually:
   ```bash
   psql -h $DB_HOST -U $DB_USER -d $DB_NAME
   ```

3. **Port Conflicts**
   - Check if another service is using the same port
   ```bash
   sudo lsof -i :8000
   ```

4. **Permission Issues**
   - Verify the service has proper permissions to its files and directories
   ```bash
   ls -la /var/log/abi/
   sudo chown -R abi:abi /var/log/abi/
   ```

#### API Slow Response Times

**Symptoms**:
- API endpoints respond slowly
- Increasing latency over time

**Potential Causes and Solutions**:

1. **Database Performance Issues**
   - Check database metrics for slow queries
   - Optimize indexes for frequently used queries
   - Review the query plan:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM workflows WHERE status = 'ACTIVE';
   ```

2. **High System Load**
   - Check CPU, memory, and disk usage
   - Consider scaling up or out if resources are consistently high
   ```bash
   top
   free -m
   df -h
   ```

3. **Connection Pool Exhaustion**
   - Increase database connection pool size
   - Check for connection leaks in the code
   ```bash
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'abi_db';
   ```

4. **Memory Leaks**
   - Monitor memory usage over time
   - Restart the service temporarily while investigating
   ```bash
   ps aux | grep abi
   ```

### Worker Service Issues

#### Tasks Getting Stuck

**Symptoms**:
- Tasks remain in "RUNNING" state indefinitely
- No progress in task execution logs

**Potential Causes and Solutions**:

1. **Worker Process Crashes**
   - Check worker logs for exceptions
   - Ensure worker processes have sufficient resources
   ```bash
   tail -f /var/log/abi/worker.log
   ```

2. **Task Queue Issues**
   - Verify Redis or RabbitMQ is running properly
   - Check queue status:
   ```bash
   # For Redis
   redis-cli -h $REDIS_HOST
   > LLEN abi_task_queue
   
   # For RabbitMQ
   rabbitmqctl list_queues
   ```

3. **Deadlocks or Race Conditions**
   - Check for locks in the database:
   ```sql
   SELECT relation::regclass, mode, granted 
   FROM pg_locks l JOIN pg_stat_activity s ON l.pid = s.pid;
   ```

4. **External Service Timeouts**
   - Check connectivity to external services
   - Adjust timeout settings in the configuration
   ```bash
   curl -v --max-time 5 https://external-service.example.com/api/health
   ```

#### Worker High Memory Usage

**Symptoms**:
- Worker processes consuming excessive memory
- OOM (Out of Memory) killer terminating processes

**Potential Causes and Solutions**:

1. **Memory Leaks in Integration Code**
   - Check which integrations are being used in problematic workflows
   - Update or fix integration code
   ```bash
   ps -o pid,rss,command | grep worker
   ```

2. **Large Dataset Processing**
   - Implement batch processing for large datasets
   - Set memory limits for worker processes
   ```bash
   # In your worker configuration
   ABI_WORKER_MEMORY_LIMIT=512m
   ```

3. **Inefficient Code**
   - Profile code to identify memory-intensive sections
   - Optimize algorithms and data structures
   ```python
   # Example of using memory_profiler
   @profile
   def memory_intensive_function():
       # ...
   ```

### Ontology Store Issues

#### Query Performance Problems

**Symptoms**:
- SPARQL queries taking a long time to complete
- Timeouts when accessing ontology data

**Potential Causes and Solutions**:

1. **Inefficient SPARQL Queries**
   - Optimize SPARQL queries by adding proper filters
   - Limit result sets when possible
   ```sparql
   # Before
   SELECT ?s ?p ?o WHERE { ?s ?p ?o }
   
   # After
   SELECT ?s ?p ?o WHERE { 
     ?s a <http://example.org/Company> .
     ?s ?p ?o .
   } LIMIT 100
   ```

2. **Missing Indexes**
   - Add indexes to frequently queried predicates
   - Consult the triple store documentation for indexing options
   ```bash
   # Example for Fuseki
   fuseki-cmd --add-index pred-obj
   ```

3. **Large Ontology Size**
   - Consider partitioning the ontology into separate stores
   - Implement data lifecycle policies to archive older data
   ```bash
   # Check store size
   du -sh /var/lib/abi/ontology/
   ```

4. **Connection Pool Issues**
   - Increase the connection pool for the triple store
   - Set appropriate timeouts
   ```python
   # In your ontology store configuration
   {
     "pool_size": 20,
     "timeout": 30
   }
   ```

#### Data Consistency Issues

**Symptoms**:
- Missing or incomplete data in the ontology
- Unexpected query results

**Potential Causes and Solutions**:

1. **Failed Pipeline Executions**
   - Check pipeline execution logs for errors
   - Rerun failed pipelines
   ```bash
   tail -f /var/log/abi/pipeline.log
   ```

2. **Transaction Issues**
   - Ensure proper transaction handling in pipeline code
   - Add validation checks for data consistency
   ```python
   with ontology_store.transaction() as tx:
       # Add data with validation
   ```

3. **Schema Validation Failures**
   - Verify that data conforms to the ontology schema
   - Update schema if necessary
   ```bash
   # Validate a graph against schema
   abi validate-graph --schema=/path/to/schema.ttl --graph=/path/to/data.ttl
   ```

4. **Data Import/Export Issues**
   - Check for encoding or format issues when importing data
   - Verify data transformation logic
   ```bash
   # Examine a sample of the data
   head -n 20 /path/to/import/data.ttl
   ```

### Integration Issues

#### Authentication Failures

**Symptoms**:
- 401 or 403 errors in integration logs
- "Unauthorized" messages when accessing external APIs

**Potential Causes and Solutions**:

1. **Expired Credentials**
   - Check token expiration dates
   - Implement token refresh logic
   ```bash
   # Check when token was last updated
   stat /etc/abi/secrets/integration_token.json
   ```

2. **Incorrect API Keys**
   - Verify API keys and secrets are correctly set
   - Regenerate keys if necessary
   ```bash
   # Test credential validity (example for GitHub)
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
   ```

3. **IP Restrictions**
   - Check if the external service has IP-based access controls
   - Whitelist your server IPs if necessary
   ```bash
   curl ifconfig.me
   ```

4. **Changed API Requirements**
   - Check if the external API has updated their authentication methods
   - Update integration code to match new requirements
   ```bash
   # Check API documentation for changes
   curl -v https://api.example.com
   ```

#### Rate Limiting Issues

**Symptoms**:
- 429 "Too Many Requests" errors
- Sudden failures after a period of normal operation

**Potential Causes and Solutions**:

1. **Exceeding API Rate Limits**
   - Implement rate limiting in your integration code
   - Add exponential backoff for retries
   ```python
   def retry_with_backoff(func, max_retries=5):
       retries = 0
       while retries < max_retries:
           try:
               return func()
           except RateLimitException:
               wait_time = 2 ** retries
               logger.info(f"Rate limited. Waiting {wait_time} seconds.")
               time.sleep(wait_time)
               retries += 1
       raise Exception("Max retries exceeded")
   ```

2. **Inefficient API Usage**
   - Batch API requests where possible
   - Cache results that don't change frequently
   ```python
   # Use bulk operations
   api.create_many(items) instead of for item in items: api.create(item)
   ```

3. **Multiple Instances Sharing Quota**
   - Implement a central rate limiter for distributed systems
   - Use Redis to track API call counts across instances
   ```python
   def check_rate_limit(key, limit, period):
       current = redis_client.get(key) or 0
       if int(current) >= limit:
           return False
       pipeline = redis_client.pipeline()
       pipeline.incr(key)
       pipeline.expire(key, period)
       pipeline.execute()
       return True
   ```

### Pipeline and Workflow Issues

#### Pipeline Execution Failures

**Symptoms**:
- Pipelines fail to complete
- Error messages in pipeline execution logs

**Potential Causes and Solutions**:

1. **Invalid Pipeline Configuration**
   - Check pipeline configuration parameters
   - Validate input parameters against expected schema
   ```bash
   abi validate-pipeline --config=/path/to/pipeline_config.json
   ```

2. **Data Format Changes**
   - Verify that input data matches expected format
   - Update pipeline code to handle format changes
   ```bash
   # Sample the input data
   head -n 20 /path/to/input.json | jq
   ```

3. **Integration Errors**
   - Check if integrations used in the pipeline are working
   - Test integrations independently
   ```bash
   abi test-integration --name=github
   ```

4. **Resource Constraints**
   - Check if the pipeline has sufficient resources
   - Increase memory/CPU limits for resource-intensive pipelines
   ```bash
   # Adjust resource limits
   ABI_PIPELINE_MEMORY_LIMIT=1024m
   ```

#### Workflow Scheduling Issues

**Symptoms**:
- Scheduled workflows not executing at expected times
- Gaps in workflow execution history

**Potential Causes and Solutions**:

1. **Scheduler Service Issues**
   - Check if the scheduler service is running
   - Verify cron expressions for scheduled workflows
   ```bash
   # Check scheduler status
   systemctl status abi-scheduler
   
   # Verify cron expression
   abi validate-cron "0 */2 * * *"
   ```

2. **Timezone Misconfigurations**
   - Check timezone settings for the scheduler
   - Ensure scheduled times are specified correctly
   ```bash
   # Check system timezone
   timedatectl
   
   # Set explicit timezone in workflow schedule
   "schedule": "0 2 * * *",
   "timezone": "UTC"
   ```

3. **Locked Workflows**
   - Check for stale workflow locks
   - Clear locks if necessary
   ```sql
   SELECT * FROM workflow_locks WHERE locked_at < NOW() - INTERVAL '1 hour';
   UPDATE workflow_locks SET locked_by = NULL WHERE locked_at < NOW() - INTERVAL '1 hour';
   ```

4. **Missing Dependencies**
   - Verify that all workflow dependencies are available
   - Check if dependent workflows completed successfully
   ```bash
   abi list-workflow-dependencies --name=data_processing_workflow
   ```

## Database Issues

### Connection Pool Exhaustion

**Symptoms**:
- "Too many connections" errors
- Services unable to connect to the database

**Solutions**:

1. **Increase Maximum Connections**
   ```sql
   ALTER SYSTEM SET max_connections = '200';
   SELECT pg_reload_conf();
   ```

2. **Optimize Connection Pool Settings**
   ```python
   # In your database configuration
   {
     "pool_size": 20,
     "max_overflow": 10,
     "pool_timeout": 30
   }
   ```

3. **Find Connection Leaks**
   ```sql
   SELECT pid, usename, application_name, state, query_start
   FROM pg_stat_activity
   WHERE datname = 'abi_db'
   ORDER BY query_start;
   ```

### Database Locks

**Symptoms**:
- Queries hang indefinitely
- Timeouts on database operations

**Solutions**:

1. **Identify Blocking Queries**
   ```sql
   SELECT blocked_locks.pid AS blocked_pid,
          blocking_locks.pid AS blocking_pid,
          blocked_activity.usename AS blocked_user,
          blocking_activity.usename AS blocking_user,
          blocked_activity.query AS blocked_statement,
          blocking_activity.query AS blocking_statement
   FROM pg_catalog.pg_locks blocked_locks
   JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
   JOIN pg_catalog.pg_locks blocking_locks 
       ON blocking_locks.locktype = blocked_locks.locktype
       AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
       AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
       AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
       AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
       AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
       AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
       AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
       AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
       AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
       AND blocking_locks.pid != blocked_locks.pid
   JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
   WHERE NOT blocked_locks.granted;
   ```

2. **Kill Blocking Sessions**
   ```sql
   SELECT pg_terminate_backend(PID);
   ```

3. **Optimize Transaction Usage**
   - Reduce transaction duration
   - Split long-running transactions into smaller ones

## System Issues

### High CPU Usage

**Symptoms**:
- System load average is consistently high
- Slow response times across all services

**Solutions**:

1. **Identify CPU-Intensive Processes**
   ```bash
   top -c
   pidstat -u 1 10
   ```

2. **Profile Python Code**
   ```bash
   # Install profiler
   pip install py-spy
   
   # Generate CPU flame graph
   py-spy record -o profile.svg --pid $PID
   ```

3. **Optimize Resource Usage**
   - Implement caching for expensive operations
   - Optimize database queries
   - Consider horizontal scaling

### Memory Leaks

**Symptoms**:
- Steadily increasing memory usage
- Services restarting due to OOM (Out of Memory)

**Solutions**:

1. **Monitor Memory Usage**
   ```bash
   watch -n 1 "ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -10"
   ```

2. **Analyze Memory Usage**
   ```bash
   # Install memory profiler
   pip install memory_profiler
   
   # Profile memory usage
   mprof run --python python_script.py
   mprof plot
   ```

3. **Restart Services Periodically**
   - As a temporary workaround, implement service restarts
   ```bash
   # Add to crontab for nightly restart
   0 2 * * * systemctl restart abi-api
   ```

## Security Issues

### Unusual Access Patterns

**Symptoms**:
- Unexpected API calls from unknown sources
- Unusual login attempts or authentication failures

**Solutions**:

1. **Review Access Logs**
   ```bash
   grep "authentication failed" /var/log/abi/api.log
   ```

2. **Implement Rate Limiting**
   ```python
   # Using Flask-Limiter
   limiter = Limiter(
       app,
       key_func=get_remote_address,
       default_limits=["200 per day", "50 per hour"]
   )
   
   @app.route("/login")
   @limiter.limit("10 per minute")
   def login():
       # login logic
   ```

3. **Configure IP Allowlists**
   ```bash
   # Update firewall rules
   ufw allow from 192.168.1.0/24 to any port 8000
   ```

### Data Access Issues

**Symptoms**:
- Users unable to access resources they should have permission for
- "Permission denied" errors in logs

**Solutions**:

1. **Check User Permissions**
   ```sql
   SELECT * FROM user_permissions WHERE user_id = 123;
   ```

2. **Verify Role Assignments**
   ```sql
   SELECT u.username, r.role_name 
   FROM users u 
   JOIN user_roles ur ON u.id = ur.user_id 
   JOIN roles r ON ur.role_id = r.id
   WHERE u.username = 'john.doe';
   ```

3. **Audit Permission Changes**
   ```sql
   SELECT * FROM audit_log 
   WHERE action = 'PERMISSION_CHANGE' 
   ORDER BY timestamp DESC LIMIT 20;
   ```

## Troubleshooting Checklists

### API Service Checklist

- [ ] Verify service is running (`systemctl status abi-api`)
- [ ] Check logs for errors (`tail -f /var/log/abi/api.log`)
- [ ] Verify database connectivity
- [ ] Check environment variables
- [ ] Test API endpoints manually
- [ ] Verify network/firewall settings
- [ ] Check for resource constraints

### Worker Service Checklist

- [ ] Verify worker services are running
- [ ] Check worker logs for errors
- [ ] Verify task queue is operational
- [ ] Check for stalled tasks
- [ ] Verify external service connectivity
- [ ] Check for resource constraints
- [ ] Test worker functions independently

### Ontology Store Checklist

- [ ] Verify triple store service is running
- [ ] Check triple store logs
- [ ] Test SPARQL endpoint connectivity
- [ ] Verify schema configuration
- [ ] Check index status
- [ ] Run sample queries to test performance
- [ ] Check disk space for the triple store

### Integration Checklist

- [ ] Verify API credentials
- [ ] Check for rate limiting issues
- [ ] Test external service connectivity
- [ ] Check integration configuration
- [ ] Verify network/firewall settings
- [ ] Review integration logs
- [ ] Test with API testing tools

## Debugging Production Issues

When debugging issues in production:

1. **Gather Information**
   - Collect logs from all relevant components
   - Capture environment variables and configurations
   - Document the exact steps to reproduce

2. **Minimize Impact**
   - Use read-only operations when possible
   - Test fixes in staging environment first
   - Schedule maintenance windows for risky operations

3. **Implement Fixes Methodically**
   - Make one change at a time
   - Document all changes made
   - Verify each change resolves the issue
   - Create regression tests for the issue

4. **Follow Up**
   - Update documentation with the solution
   - Share lessons learned with the team
   - Implement monitoring for the specific issue
   - Consider preventive measures for similar issues

## Getting Help

If you need additional assistance:

1. **Internal Resources**
   - Check the internal knowledge base
   - Review past incident reports for similar issues
   - Consult the developer documentation

2. **Community Support**
   - Post questions on the ABI discussion forum
   - Check GitHub issues for known problems
   - Join the ABI Slack community

3. **Commercial Support**
   - Contact the ABI support team at support@abiframework.org
   - For premium support subscriptions, use the dedicated support portal
   - Schedule a consultation with the ABI professional services team 