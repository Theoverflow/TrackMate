# AWS Cloud Integration Guide

Monitor near-real-time compute jobs running on **AWS EC2**, **ECS**, and **Lambda** with comprehensive observability through CloudWatch, X-Ray, and custom metrics.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [EC2 Integration](#ec2-integration)
- [ECS Integration](#ecs-integration)
- [Lambda Integration](#lambda-integration)
- [Configuration](#configuration)
- [Metrics & Logging](#metrics--logging)
- [Distributed Tracing](#distributed-tracing)
- [IAM Permissions](#iam-permissions)
- [Best Practices](#best-practices)

## Overview

The AWS integration provides seamless monitoring for jobs running across AWS compute platforms, automatically detecting the environment and sending telemetry to CloudWatch and X-Ray.

### Supported Platforms

| Platform | Detection Method | Metrics | Logs | Traces |
|----------|-----------------|---------|------|--------|
| **EC2** | Instance metadata | ✅ | ✅ | ✅ |
| **ECS/Fargate** | Task metadata | ✅ | ✅ | ✅ |
| **Lambda** | Environment vars | ✅ | ✅ | ✅ |

## Features

### 🎯 **Auto-Detection**
- Automatically detects EC2, ECS, or Lambda environment
- Enriches events with platform-specific metadata
- No manual configuration required

### 📊 **CloudWatch Metrics**
- Job duration and status
- CPU utilization (user/system)
- Memory usage peaks
- Custom business metrics
- Multi-dimensional metrics with tags

### 📝 **CloudWatch Logs**
- Structured JSON logging
- Searchable log streams
- Log insights support
- Automatic log group creation

### 🔍 **X-Ray Distributed Tracing**
- End-to-end request tracing
- Service map visualization
- Performance bottleneck detection
- Error tracking and analysis

### ⚡ **Near-Real-Time**
- Sub-second metric delivery
- Immediate log availability
- Fast trace propagation

## Architecture

```
┌─────────────────────────────────────────────────┐
│              AWS Compute Platform               │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐    │
│  │   EC2   │  │  ECS/    │  │  Lambda    │    │
│  │Instance │  │ Fargate  │  │  Function  │    │
│  └────┬────┘  └─────┬────┘  └─────┬──────┘    │
│       │             │              │            │
│       └─────────────┴──────────────┘            │
│                     │                           │
│         ┌───────────▼──────────┐               │
│         │  Monitoring SDK      │               │
│         │  + AWS Helpers       │               │
│         └───────────┬──────────┘               │
│                     │                           │
└─────────────────────┼───────────────────────────┘
                      │
         ┌────────────┴─────────────┐
         │                          │
    ┌────▼────┐              ┌──────▼─────┐
    │CloudWatch│             │   X-Ray    │
    │ Metrics  │             │   Traces   │
    │ + Logs   │             │            │
    └─────────┘              └────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
pip install boto3 httpx tenacity structlog
```

### 2. Basic Usage

```python
from monitoring_sdk import AppRef
from monitoring_sdk.aws_helpers import create_aws_emitter, get_aws_metadata
from monitoring_sdk import Monitored
from uuid import uuid4

# Create app reference
app = AppRef(
    app_id=uuid4(),
    name="my-aws-job",
    version="1.0.0"
)

# Create emitter (auto-detects platform)
emitter = create_aws_emitter()

# Get platform metadata
metadata = get_aws_metadata()
print(f"Running on: {metadata['compute_platform']}")

# Monitor your job
with Monitored(
    site_id='site1',
    app=app,
    entity_type='job',
    business_key='daily-batch',
    emitter=emitter,
    metadata=metadata
):
    # Your job logic here
    process_data()
```

### 3. Configure Integrations

Create `integration-config.json`:

```json
[
  {
    "type": "aws_cloudwatch",
    "name": "cloudwatch",
    "enabled": true,
    "config": {
      "aws_region": "us-east-1",
      "log_group_name": "/wafer-monitor/jobs",
      "namespace": "WaferMonitor/Production",
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

## EC2 Integration

### Setup

```python
# examples/aws/ec2_job.py
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.aws_helpers import create_aws_emitter, get_ec2_metadata
from uuid import uuid4

app = AppRef(app_id=uuid4(), name="ec2-processor", version="1.0.0")
emitter = create_aws_emitter()
ec2_meta = get_ec2_metadata()

with Monitored(
    site_id='site1',
    app=app,
    entity_type='batch-job',
    business_key='daily-process',
    emitter=emitter,
    metadata=ec2_meta
) as mon:
    # Process data with progress tracking
    for i, item in enumerate(items):
        process(item)
        mon.progress(current=i+1, total=len(items))
```

### EC2 Metadata Collected

- Instance ID
- Instance Type
- Availability Zone
- Region (from zone)

### Deployment

```bash
# Build container
docker build -f examples/aws/Dockerfile.ec2 -t wafer-ec2 .

# Run on EC2
docker run \
  -e SIDECAR_URL=http://localhost:17000 \
  -e SITE_ID=site1 \
  wafer-ec2
```

### EC2 Best Practices

1. **Use IAM Instance Profiles**: Don't hardcode AWS credentials
2. **Enable CloudWatch Agent**: For system-level metrics
3. **Configure Auto Scaling**: Based on job queue depth
4. **Use EBS-optimized instances**: For I/O intensive jobs

## ECS Integration

### Task Definition

See `examples/aws/task-definition.json` for a complete ECS task definition with:
- Main application container
- Sidecar agent container
- Shared configuration volume
- CloudWatch logging

### Application Code

```python
# examples/aws/ecs_task.py
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.aws_helpers import create_aws_emitter, get_ecs_metadata
from uuid import uuid4

app = AppRef(app_id=uuid4(), name="ecs-processor", version="1.0.0")
emitter = create_aws_emitter()
ecs_meta = get_ecs_metadata()

print(f"Task ID: {ecs_meta['task_id']}")
print(f"Cluster: {ecs_meta['cluster']}")

with Monitored(
    site_id='site1',
    app=app,
    entity_type='ecs-task',
    business_key=ecs_meta['task_id'],
    emitter=emitter,
    metadata=ecs_meta
):
    # Process messages/data
    for message in queue:
        process(message)
```

### ECS Metadata Collected

- Task ARN & ID
- Cluster Name
- Container Name & ID
- Availability Zone

### Deployment

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Run task
aws ecs run-task \
  --cluster production \
  --task-definition wafer-monitor-ecs-task \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"
```

### ECS Best Practices

1. **Use Fargate**: For simplified operations
2. **Sidecar Pattern**: Deploy agent in same task
3. **Service Discovery**: For multi-service architectures
4. **Task IAM Roles**: Least-privilege permissions
5. **EFS Volumes**: For persistent log storage

## Lambda Integration

### Decorator Approach (Simplest)

```python
# examples/aws/lambda_handler.py
from monitoring_sdk import AppRef
from monitoring_sdk.aws_helpers import monitored_lambda_handler
from uuid import uuid4

app = AppRef(app_id=uuid4(), name="lambda-processor", version="1.0.0")

@monitored_lambda_handler('site1', app)
def lambda_handler(event, context):
    """Automatically monitored Lambda function."""
    # Your logic here
    records = event.get('Records', [])
    
    # Process records
    results = [process(r) for r in records]
    
    return {
        'statusCode': 200,
        'body': {'processed': len(results)}
    }
```

### Manual Approach (More Control)

```python
from monitoring_sdk import Monitored, AppRef
from monitoring_sdk.aws_helpers import create_aws_emitter, get_lambda_metadata
from uuid import uuid4

def lambda_handler(event, context):
    app = AppRef(app_id=uuid4(), name="lambda-proc", version="1.0.0")
    emitter = create_aws_emitter()
    metadata = get_lambda_metadata()
    
    with Monitored(
        site_id='site1',
        app=app,
        entity_type='lambda',
        business_key=context.request_id,
        emitter=emitter,
        metadata=metadata
    ) as mon:
        # Processing with progress tracking
        records = event['Records']
        for i, record in enumerate(records):
            process(record)
            mon.progress(current=i+1, total=len(records))
        
        return {'statusCode': 200}
```

### Lambda Metadata Collected

- Function Name & Version
- Function Memory
- Log Group & Stream
- Request ID
- Region

### Deployment

#### Docker Image

```bash
# Build Lambda container
docker build -f examples/aws/Dockerfile.lambda -t wafer-lambda .

# Push to ECR
docker tag wafer-lambda:latest ACCOUNT.dkr.ecr.REGION.amazonaws.com/wafer-lambda:latest
docker push ACCOUNT.dkr.ecr.REGION.amazonaws.com/wafer-lambda:latest

# Create function
aws lambda create-function \
  --function-name wafer-processor \
  --package-type Image \
  --code ImageUri=ACCOUNT.dkr.ecr.REGION.amazonaws.com/wafer-lambda:latest \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --environment Variables={SITE_ID=site1}
```

#### Layer Deployment

```bash
# Package SDK as layer
cd apps/monitoring_sdk
mkdir -p python/lib/python3.11/site-packages
cp -r monitoring_sdk python/lib/python3.11/site-packages/
zip -r monitoring-sdk-layer.zip python/

# Publish layer
aws lambda publish-layer-version \
  --layer-name wafer-monitoring-sdk \
  --zip-file fileb://monitoring-sdk-layer.zip \
  --compatible-runtimes python3.11
```

### Lambda Best Practices

1. **Use Layers**: Share SDK across multiple functions
2. **Environment Variables**: For configuration
3. **Async Invocation**: For non-critical paths
4. **Reserved Concurrency**: For cost control
5. **X-Ray Integration**: Enable active tracing
6. **CloudWatch Insights**: For log analysis

## Configuration

### CloudWatch Integration

```json
{
  "type": "aws_cloudwatch",
  "name": "cloudwatch-prod",
  "enabled": true,
  "config": {
    "aws_region": "us-east-1",
    "log_group_name": "/wafer-monitor/production",
    "namespace": "WaferMonitor/Production",
    "compute_platform": "auto",
    "aws_access_key_id": null,
    "aws_secret_access_key": null
  }
}
```

**Configuration Options:**

- `aws_region`: AWS region (default: us-east-1)
- `log_group_name`: CloudWatch Logs group (default: /wafer-monitor/jobs)
- `namespace`: CloudWatch metrics namespace (default: WaferMonitor)
- `compute_platform`: Platform type or "auto" for detection
- `instance_id`: Optional instance/task ID override
- `aws_access_key_id`: Optional AWS access key (uses IAM role if null)
- `aws_secret_access_key`: Optional AWS secret key

### X-Ray Integration

```json
{
  "type": "aws_xray",
  "name": "xray-prod",
  "enabled": true,
  "config": {
    "aws_region": "us-east-1",
    "service_name": "wafer-monitor-production",
    "aws_access_key_id": null,
    "aws_secret_access_key": null
  }
}
```

**Configuration Options:**

- `aws_region`: AWS region
- `service_name`: Service name for traces
- `aws_access_key_id`: Optional AWS access key
- `aws_secret_access_key`: Optional AWS secret key

## Metrics & Logging

### CloudWatch Metrics

The integration automatically sends these metrics:

| Metric Name | Unit | Description | Dimensions |
|-------------|------|-------------|------------|
| `JobCompleted` | Count | Job completion count | Status, SiteId, AppName, Platform |
| `JobDuration` | Seconds | Total job duration | SiteId, AppName, Platform |
| `CPUUserTime` | Seconds | CPU user time | SiteId, AppName, Platform |
| `CPUSystemTime` | Seconds | CPU system time | SiteId, AppName, Platform |
| `MemoryMaxMB` | Megabytes | Peak memory usage | SiteId, AppName, Platform |

### CloudWatch Logs

Structured JSON logs with fields:

```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "level": "INFO",
  "site_id": "site1",
  "app": "wafer-processor",
  "entity_type": "job",
  "entity_id": "uuid",
  "event_kind": "finished",
  "status": "succeeded",
  "metrics": {
    "duration_s": 125.3,
    "cpu_user_s": 98.2,
    "mem_max_mb": 512
  },
  "compute_platform": "ec2",
  "instance_id": "i-1234567890abcdef0"
}
```

### CloudWatch Insights Queries

**Failed Jobs:**
```
fields @timestamp, app, status, metrics.duration_s
| filter status = "failed"
| sort @timestamp desc
```

**Average Duration by App:**
```
stats avg(metrics.duration_s) as avg_duration by app
| sort avg_duration desc
```

**High Memory Usage:**
```
fields @timestamp, app, metrics.mem_max_mb
| filter metrics.mem_max_mb > 1000
| sort metrics.mem_max_mb desc
```

## Distributed Tracing

### X-Ray Traces

The integration creates trace segments with:

- **Trace ID**: Unique identifier for end-to-end request
- **Segment ID**: ID for this specific service operation
- **Start/End Times**: Precise timing information
- **Status**: Success/error indicators
- **Annotations**: Indexed fields for filtering
  - `site_id`
  - `app_name`
  - `status`
  - `entity_type`
- **Metadata**: Additional context
  - Resource metrics (CPU, memory)
  - Business keys
  - Custom metadata

### Viewing Traces

1. Open AWS X-Ray Console
2. Navigate to **Service Map** to see architecture
3. Go to **Traces** to search by:
   - Time range
   - Status (error/ok)
   - Annotations (site_id, app_name)
   - Duration

### Example Trace

```
Trace ID: 1-67890abc-def123456789abcd
├─ wafer-processor.job (125.3s)
   ├─ Start: 10:30:45.123
   ├─ End: 10:33:10.456
   ├─ Status: OK
   ├─ Annotations:
   │  ├─ site_id: site1
   │  ├─ app_name: wafer-processor
   │  └─ status: succeeded
   └─ Metadata:
      ├─ duration_s: 125.3
      ├─ cpu_user_s: 98.2
      └─ mem_max_mb: 512
```

## IAM Permissions

### EC2/ECS Task Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "WaferMonitor"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/wafer-monitor/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

### Lambda Execution Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords"
      ],
      "Resource": "*"
    }
  ]
}
```

## Best Practices

### 1. **Use IAM Roles, Not Access Keys**
- EC2: Instance profiles
- ECS: Task roles
- Lambda: Execution roles
- **Never** hardcode credentials

### 2. **Optimize Costs**
- Use log retention policies (7-90 days)
- Enable CloudWatch Logs compression
- Filter metrics before sending
- Use metric filters for alarms

### 3. **Security**
- Encrypt logs at rest (KMS)
- Use VPC endpoints for AWS API calls
- Apply resource-based policies
- Enable X-Ray encryption

### 4. **Performance**
- Batch CloudWatch metric puts (up to 20)
- Use async logging
- Enable connection pooling
- Cache IAM role credentials

### 5. **Monitoring the Monitor**
- Set CloudWatch alarms on metric delivery failures
- Monitor X-Ray service health
- Track integration health checks
- Alert on missing expected metrics

### 6. **Multi-Region**
- Deploy monitoring in each region
- Use regional CloudWatch/X-Ray endpoints
- Aggregate cross-region with central dashboard
- Consider latency for cross-region calls

### 7. **Tagging Strategy**
```python
metadata = {
    'environment': 'production',
    'team': 'data-processing',
    'cost_center': 'engineering',
    'application': 'wafer-monitor'
}
```

### 8. **Troubleshooting**
- Enable SDK debug logging
- Check IAM permissions
- Verify network connectivity to AWS endpoints
- Review CloudWatch/X-Ray service limits
- Use X-Ray service map to identify issues

## Examples

See `examples/aws/` directory for complete examples:

- **`lambda_handler.py`**: Lambda function with monitoring
- **`ec2_job.py`**: EC2 batch job
- **`ecs_task.py`**: ECS task processing
- **`Dockerfile.lambda`**: Lambda container image
- **`Dockerfile.ec2`**: EC2 deployment image
- **`task-definition.json`**: ECS task definition

## Support & Resources

- [CloudWatch Metrics Documentation](https://docs.aws.amazon.com/cloudwatch/latest/monitoring/)
- [CloudWatch Logs Insights](https://docs.aws.amazon.com/cloudwatch/latest/logs/AnalyzingLogData.html)
- [AWS X-Ray Developer Guide](https://docs.aws.amazon.com/xray/latest/devguide/)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)

---

**Next Steps:**
1. Review [INTEGRATIONS.md](./INTEGRATIONS.md) for other integration options
2. Check [MULTI_INTEGRATION_GUIDE.md](./MULTI_INTEGRATION_GUIDE.md) for combining multiple backends
3. See [TIMESCALEDB_OPTIMIZATION.md](./TIMESCALEDB_OPTIMIZATION.md) for on-premises analytics

