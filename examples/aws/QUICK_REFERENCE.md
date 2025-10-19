# AWS Integration Quick Reference Card

## 🚀 Quick Start (30 seconds)

```python
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.aws_helpers import create_aws_emitter, get_aws_metadata
from uuid import uuid4

app = AppRef(app_id=uuid4(), name="my-job", version="1.0.0")
emitter = create_aws_emitter()  # Auto-detects EC2/ECS/Lambda

with Monitored(site_id='site1', app=app, entity_type='job',
               business_key='key', emitter=emitter, metadata=get_aws_metadata()):
    # Your code here - monitored automatically!
    do_work()
```

## 📊 What Gets Sent to AWS

### CloudWatch Metrics
| Metric | Unit | When |
|--------|------|------|
| JobCompleted | Count | On finish |
| JobDuration | Seconds | On finish |
| CPUUserTime | Seconds | On finish |
| CPUSystemTime | Seconds | On finish |
| MemoryMaxMB | Megabytes | On finish |

**Namespace**: `WaferMonitor` (configurable)  
**Dimensions**: SiteId, AppName, EntityType, ComputePlatform, Status

### CloudWatch Logs
- **Log Group**: `/wafer-monitor/jobs` (configurable)
- **Format**: Structured JSON
- **Fields**: timestamp, level, site_id, app, entity_type, status, metrics, metadata

### X-Ray Traces
- **Service Name**: `wafer-monitor` (configurable)
- **Segments**: Start → Finish correlation
- **Annotations**: Indexed (site_id, app_name, status, entity_type)
- **Metadata**: Resource metrics, business keys

## 🔑 Required IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

## 🎯 Platform-Specific Usage

### Lambda (Decorator)
```python
from monitoring_sdk.aws_helpers import monitored_lambda_handler

@monitored_lambda_handler('site1', app_ref)
def lambda_handler(event, context):
    return {'statusCode': 200}
```

### EC2 (Auto-detect)
```python
from monitoring_sdk.aws_helpers import get_ec2_metadata
metadata = get_ec2_metadata()  # Returns instance_id, instance_type, etc.
```

### ECS (Auto-detect)
```python
from monitoring_sdk.aws_helpers import get_ecs_metadata
metadata = get_ecs_metadata()  # Returns task_arn, cluster, container_name, etc.
```

## ⚙️ Configuration

```json
[
  {
    "type": "aws_cloudwatch",
    "name": "cloudwatch",
    "enabled": true,
    "config": {
      "aws_region": "us-east-1",
      "log_group_name": "/wafer-monitor/jobs",
      "namespace": "WaferMonitor",
      "compute_platform": "auto"
    }
  },
  {
    "type": "aws_xray",
    "name": "xray",
    "enabled": true,
    "config": {
      "aws_region": "us-east-1",
      "service_name": "wafer-monitor"
    }
  }
]
```

## 🔍 Viewing Data

### CloudWatch Console
1. **Metrics**: CloudWatch → Metrics → Custom → WaferMonitor
2. **Logs**: CloudWatch → Log Groups → /wafer-monitor/*
3. **Alarms**: CloudWatch → Alarms (create on metrics)

### X-Ray Console
1. **Service Map**: X-Ray → Service Map
2. **Traces**: X-Ray → Traces (search/filter)
3. **Analytics**: X-Ray → Analytics

### CLI Commands
```bash
# List metrics
aws cloudwatch list-metrics --namespace WaferMonitor

# Get metric statistics
aws cloudwatch get-metric-statistics \
  --namespace WaferMonitor \
  --metric-name JobDuration \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Average

# Query logs
aws logs filter-log-events \
  --log-group-name /wafer-monitor/jobs \
  --filter-pattern '{ $.status = "failed" }'

# Get traces
aws xray get-trace-summaries \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --filter-expression 'annotation.status = "failed"'
```

## 🔧 CloudWatch Insights Queries

### Failed Jobs (Last Hour)
```sql
fields @timestamp, app, status, metrics.duration_s
| filter status = "failed"
| sort @timestamp desc
| limit 20
```

### Average Duration by App
```sql
stats avg(metrics.duration_s) as avg_duration by app
| sort avg_duration desc
```

### High Memory Usage
```sql
fields @timestamp, app, metrics.mem_max_mb
| filter metrics.mem_max_mb > 1000
| sort metrics.mem_max_mb desc
```

### Jobs by Platform
```sql
stats count() by compute_platform
```

## 🐛 Troubleshooting

| Issue | Check | Fix |
|-------|-------|-----|
| No metrics | IAM permissions | Add `cloudwatch:PutMetricData` |
| No logs | Log group exists | Create log group or enable auto-create |
| No traces | X-Ray daemon | Enable active tracing (Lambda) or start daemon (EC2/ECS) |
| Wrong region | Config file | Set correct `aws_region` |
| High costs | Retention policies | Set log retention to 7-30 days |

### Debug Commands
```bash
# Check IAM role
aws sts get-caller-identity
aws iam get-role-policy --role-name YourRole --policy-name YourPolicy

# Check CloudWatch limits
aws service-quotas list-service-quotas --service-code cloudwatch

# Test API access
aws cloudwatch put-metric-data --namespace Test --metric-name TestMetric --value 1

# Enable debug logging
export AWS_SDK_LOG_LEVEL=debug
```

## 💰 Cost Optimization

| Item | Default | Recommendation | Savings |
|------|---------|----------------|---------|
| Log Retention | Never expire | 7-30 days | ~70% |
| X-Ray Sampling | 100% | 10-20% | ~80% |
| Metric Resolution | 1 minute | 5 minutes | ~80% |
| Log Compression | Off | On | ~50% |

### Cost Estimates (Monthly)
- **CloudWatch Logs**: $0.50/GB ingested + $0.03/GB stored
- **CloudWatch Metrics**: $0.30 per metric (first 10,000 metrics)
- **X-Ray**: $5.00 per million traces recorded + $0.50 per million traces retrieved

**Example**: 1,000 jobs/day × 30 days = 30,000 events
- Metrics: ~$9/month (5 metrics × 30,000 events)
- Logs: ~$15/month (assuming 0.5KB per event)
- X-Ray: ~$0.15/month (30,000 traces)
- **Total**: ~$25/month

## 📚 References

- **Full Guide**: [AWS_INTEGRATION.md](../../docs/AWS_INTEGRATION.md)
- **Examples**: [examples/aws/](.)
- **IAM Policies**: [IAM-policies.json](IAM-policies.json)
- **Integration Docs**: [INTEGRATIONS.md](../../docs/INTEGRATIONS.md)

## 🎓 Best Practices

1. ✅ **Always use IAM roles** (never hardcode credentials)
2. ✅ **Tag resources** (enable cost allocation)
3. ✅ **Set retention policies** (avoid unbounded growth)
4. ✅ **Use VPC endpoints** (reduce data transfer)
5. ✅ **Enable encryption** (protect sensitive data)
6. ✅ **Batch operations** (reduce API calls)
7. ✅ **Monitor costs** (set up billing alerts)
8. ✅ **Test in dev** (before production)

## 🚀 Common Patterns

### Pattern 1: Lambda with Auto-Monitoring
```python
@monitored_lambda_handler('site1', app_ref)
def lambda_handler(event, context):
    return {'statusCode': 200}
```

### Pattern 2: EC2 Batch Job
```python
with Monitored(..., metadata=get_ec2_metadata()) as mon:
    for i, item in enumerate(items):
        process(item)
        mon.progress(current=i+1, total=len(items))
```

### Pattern 3: ECS Task with Progress
```python
with Monitored(..., metadata=get_ecs_metadata()) as mon:
    for msg in queue:
        process(msg)
        mon.progress(current=processed, total=total)
```

### Pattern 4: Multi-Integration (AWS + Local)
```json
[
  {"type": "local_api", "enabled": true, ...},
  {"type": "aws_cloudwatch", "enabled": true, ...},
  {"type": "aws_xray", "enabled": true, ...}
]
```

---

**Need Help?**
- 📖 Read [AWS_INTEGRATION.md](../../docs/AWS_INTEGRATION.md)
- 💬 Check troubleshooting section
- 🔍 Review CloudWatch/X-Ray consoles
- 🐛 Enable debug logging

