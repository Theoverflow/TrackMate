# AWS Integration Examples

This directory contains complete examples for monitoring jobs on AWS compute platforms (EC2, ECS, Lambda).

## Files

### Application Examples

- **`lambda_handler.py`** - AWS Lambda function with monitoring
  - Decorator-based approach (simplest)
  - Manual approach (more control)
  - Progress tracking
  
- **`ec2_job.py`** - EC2 batch job with monitoring
  - Auto-detection of EC2 metadata
  - Progress reporting
  - Batch processing example

- **`ecs_task.py`** - ECS/Fargate task with monitoring
  - Task metadata extraction
  - Message processing example
  - Progress updates

### Deployment Files

- **`Dockerfile.lambda`** - Lambda container image
- **`Dockerfile.ec2`** - EC2 deployment container
- **`Dockerfile.sidecar`** - Sidecar agent with AWS integrations
- **`task-definition.json`** - ECS task definition
- **`docker-compose.aws.yml`** - Local dev with AWS integrations

### Configuration

- **`IAM-policies.json`** - Required IAM permissions
- **`../integrations/aws-cloudwatch.json`** - CloudWatch config (EC2)
- **`../integrations/aws-ecs.json`** - Multi-integration config (ECS)
- **`../integrations/aws-lambda.json`** - Lambda-specific config

## Quick Start

### 1. Lambda Function

```python
from monitoring_sdk import AppRef
from monitoring_sdk.aws_helpers import monitored_lambda_handler
from uuid import uuid4

app = AppRef(app_id=uuid4(), name="my-lambda", version="1.0.0")

@monitored_lambda_handler('site1', app)
def lambda_handler(event, context):
    # Your logic here - automatically monitored!
    records = event['Records']
    process_records(records)
    return {'statusCode': 200, 'body': 'Success'}
```

**Deploy:**
```bash
# Build container
docker build -f Dockerfile.lambda -t my-lambda .

# Push to ECR
docker tag my-lambda:latest ACCOUNT.dkr.ecr.REGION.amazonaws.com/my-lambda:latest
docker push ACCOUNT.dkr.ecr.REGION.amazonaws.com/my-lambda:latest

# Create Lambda function
aws lambda create-function \
  --function-name my-lambda \
  --package-type Image \
  --code ImageUri=ACCOUNT.dkr.ecr.REGION.amazonaws.com/my-lambda:latest \
  --role arn:aws:iam::ACCOUNT:role/lambda-role
```

### 2. EC2 Batch Job

```python
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.aws_helpers import create_aws_emitter, get_ec2_metadata
from uuid import uuid4

app = AppRef(app_id=uuid4(), name="ec2-job", version="1.0.0")
emitter = create_aws_emitter()  # Auto-detects EC2
metadata = get_ec2_metadata()

with Monitored(
    site_id='site1',
    app=app,
    entity_type='batch-job',
    business_key='daily-process',
    emitter=emitter,
    metadata=metadata
) as mon:
    for i, item in enumerate(items):
        process(item)
        mon.progress(current=i+1, total=len(items))
```

**Deploy:**
```bash
# Build container
docker build -f Dockerfile.ec2 -t ec2-job .

# Run on EC2
docker run \
  -e SIDECAR_URL=http://localhost:17000 \
  -e SITE_ID=site1 \
  ec2-job
```

### 3. ECS Task

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

### 4. Local Development with AWS Integration

```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1

# Start services
docker-compose -f docker-compose.aws.yml up -d

# View logs
docker-compose -f docker-compose.aws.yml logs -f sidecar-agent

# Test the setup
curl http://localhost:17000/v1/health
```

## IAM Permissions

Create IAM roles/policies using `IAM-policies.json`:

```bash
# Create role for EC2/ECS
aws iam create-role --role-name WaferMonitorTaskRole --assume-role-policy-document file://trust-policy.json
aws iam put-role-policy --role-name WaferMonitorTaskRole --policy-name WaferMonitorPolicy --policy-document file://IAM-policies.json

# Attach role to EC2 instance
aws ec2 associate-iam-instance-profile --instance-id i-xxx --iam-instance-profile Name=WaferMonitorProfile

# For Lambda
aws lambda update-function-configuration --function-name my-lambda --role arn:aws:iam::ACCOUNT:role/WaferMonitorLambdaRole
```

## Viewing Data in AWS

### CloudWatch Metrics

1. Open AWS Console → CloudWatch → Metrics
2. Navigate to Custom Namespaces → **WaferMonitor**
3. View metrics:
   - JobCompleted (by Status)
   - JobDuration
   - CPUUserTime, CPUSystemTime
   - MemoryMaxMB

### CloudWatch Logs

1. Open AWS Console → CloudWatch → Log Groups
2. Find `/wafer-monitor/*` log groups
3. Use Log Insights for queries:

```sql
-- Failed jobs
fields @timestamp, app, status, metrics.duration_s
| filter status = "failed"
| sort @timestamp desc
```

### X-Ray Traces

1. Open AWS Console → X-Ray → Service Map
2. View end-to-end request flows
3. Navigate to Traces to search by:
   - Time range
   - Status (error/ok)
   - Annotations (site_id, app_name)

## Configuration

Edit the JSON config files in `../integrations/` to customize:

- AWS region
- CloudWatch namespace and log group
- Metric dimensions
- X-Ray service name
- Enable/disable integrations

## Troubleshooting

### No metrics appearing

1. Check IAM permissions: `aws iam get-role-policy --role-name WaferMonitorTaskRole --policy-name WaferMonitorPolicy`
2. Verify AWS credentials: `aws sts get-caller-identity`
3. Check CloudWatch service limits: `aws service-quotas get-service-quota --service-code cloudwatch --quota-code L-123...`
4. Enable debug logging: `export AWS_SDK_LOG_LEVEL=debug`

### Logs not visible

1. Verify log group exists: `aws logs describe-log-groups --log-group-name-prefix /wafer-monitor`
2. Check log retention: `aws logs describe-log-groups --query 'logGroups[*].[logGroupName,retentionInDays]'`
3. Review IAM permissions for `logs:PutLogEvents`

### X-Ray traces missing

1. Enable active tracing (Lambda): `aws lambda update-function-configuration --function-name my-lambda --tracing-config Mode=Active`
2. Check X-Ray daemon (EC2/ECS): `ps aux | grep xray`
3. Verify IAM permissions: `xray:PutTraceSegments`

## Cost Optimization

- **CloudWatch Logs**: Set retention to 7-30 days
- **Metrics**: Only send on job completion (not progress)
- **X-Ray**: Use sampling rules to reduce trace volume
- **VPC Endpoints**: Reduce data transfer costs

## Best Practices

1. ✅ Use IAM roles, not hardcoded credentials
2. ✅ Tag all resources for cost allocation
3. ✅ Set up CloudWatch Alarms for failures
4. ✅ Enable X-Ray encryption for sensitive data
5. ✅ Use regional endpoints to reduce latency
6. ✅ Batch CloudWatch API calls when possible
7. ✅ Monitor integration health with `/health` endpoint

## Next Steps

- Read [AWS_INTEGRATION.md](../../docs/AWS_INTEGRATION.md) for complete guide
- Review [INTEGRATIONS.md](../../docs/INTEGRATIONS.md) for other backends
- See [MULTI_INTEGRATION_GUIDE.md](../../docs/MULTI_INTEGRATION_GUIDE.md) for combining multiple targets

## Support

For issues or questions:
- Check logs: `docker-compose logs sidecar-agent`
- Test health: `curl http://localhost:17000/v1/health`
- Review CloudWatch metrics delivery
- Verify X-Ray service map

