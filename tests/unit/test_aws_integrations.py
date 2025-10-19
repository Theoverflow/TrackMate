"""Unit tests for AWS integrations."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from apps.shared_utils.integrations import (
    IntegrationConfig,
    AWSCloudWatchIntegration,
    AWSXRayIntegration
)


@pytest.fixture
def cloudwatch_config():
    """CloudWatch integration config."""
    return IntegrationConfig(
        type='aws_cloudwatch',
        name='test-cloudwatch',
        enabled=True,
        config={
            'aws_region': 'us-east-1',
            'log_group_name': '/test/logs',
            'namespace': 'TestNamespace',
            'compute_platform': 'ec2'
        }
    )


@pytest.fixture
def xray_config():
    """X-Ray integration config."""
    return IntegrationConfig(
        type='aws_xray',
        name='test-xray',
        enabled=True,
        config={
            'aws_region': 'us-east-1',
            'service_name': 'test-service'
        }
    )


@pytest.fixture
def sample_event():
    """Sample monitoring event."""
    return {
        'site_id': 'site1',
        'app': {
            'name': 'test-app',
            'version': '1.0.0'
        },
        'entity': {
            'type': 'job',
            'id': 'test-job-123',
            'business_key': 'test-key'
        },
        'event': {
            'kind': 'finished',
            'status': 'succeeded',
            'at': '2024-01-15T10:30:00Z',
            'metrics': {
                'duration_s': 120.5,
                'cpu_user_s': 90.0,
                'cpu_system_s': 10.0,
                'mem_max_mb': 512
            },
            'metadata': {}
        }
    }


class TestAWSCloudWatchIntegration:
    """Test AWS CloudWatch integration."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, cloudwatch_config):
        """Test CloudWatch integration initialization."""
        integration = AWSCloudWatchIntegration(cloudwatch_config)
        
        with patch('boto3.Session') as mock_session:
            mock_cw = Mock()
            mock_logs = Mock()
            
            mock_session_instance = Mock()
            mock_session_instance.client.side_effect = [mock_cw, mock_logs]
            mock_session.return_value = mock_session_instance
            
            # Mock log group creation
            mock_logs.create_log_group = Mock()
            mock_logs.create_log_stream = Mock()
            
            await integration.initialize()
            
            assert integration._initialized
            assert integration.cloudwatch_client is not None
            assert integration.logs_client is not None
    
    def test_event_to_cloudwatch_metrics(self, cloudwatch_config, sample_event):
        """Test event to CloudWatch metrics conversion."""
        integration = AWSCloudWatchIntegration(cloudwatch_config)
        
        metrics = integration._event_to_cloudwatch_metrics(sample_event)
        
        assert len(metrics) > 0
        
        # Check job completed metric
        job_metric = next((m for m in metrics if m['MetricName'] == 'JobCompleted'), None)
        assert job_metric is not None
        assert job_metric['Unit'] == 'Count'
        assert job_metric['Value'] == 1
        
        # Check duration metric
        duration_metric = next((m for m in metrics if m['MetricName'] == 'JobDuration'), None)
        assert duration_metric is not None
        assert duration_metric['Unit'] == 'Seconds'
        assert duration_metric['Value'] == 120.5
        
        # Check memory metric
        mem_metric = next((m for m in metrics if m['MetricName'] == 'MemoryMaxMB'), None)
        assert mem_metric is not None
        assert mem_metric['Unit'] == 'Megabytes'
        assert mem_metric['Value'] == 512
    
    def test_event_to_log_message(self, cloudwatch_config, sample_event):
        """Test event to CloudWatch log message conversion."""
        integration = AWSCloudWatchIntegration(cloudwatch_config)
        
        log_event = integration._event_to_log_message(sample_event)
        
        assert 'timestamp' in log_event
        assert 'message' in log_event
        
        import json
        message = json.loads(log_event['message'])
        
        assert message['site_id'] == 'site1'
        assert message['app'] == 'test-app'
        assert message['status'] == 'succeeded'
        assert message['compute_platform'] == 'ec2'
    
    @pytest.mark.asyncio
    async def test_send_event(self, cloudwatch_config, sample_event):
        """Test sending event to CloudWatch."""
        integration = AWSCloudWatchIntegration(cloudwatch_config)
        
        # Mock AWS clients
        mock_cw = Mock()
        mock_logs = Mock()
        integration.cloudwatch_client = mock_cw
        integration.logs_client = mock_logs
        integration.log_stream_name = 'test-stream'
        integration._initialized = True
        
        result = await integration.send_event(sample_event)
        
        assert result is True
        mock_cw.put_metric_data.assert_called_once()
        mock_logs.put_log_events.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check(self, cloudwatch_config):
        """Test CloudWatch health check."""
        integration = AWSCloudWatchIntegration(cloudwatch_config)
        
        # Mock AWS clients
        mock_cw = Mock()
        mock_logs = Mock()
        
        mock_logs.describe_log_streams.return_value = {'logStreams': []}
        mock_cw.list_metrics.return_value = {'Metrics': [{'MetricName': 'TestMetric'}]}
        
        integration.cloudwatch_client = mock_cw
        integration.logs_client = mock_logs
        integration._initialized = True
        
        health = await integration.health_check()
        
        assert health['status'] == 'healthy'
        assert health['backend'] == 'aws_cloudwatch'
        assert health['region'] == 'us-east-1'


class TestAWSXRayIntegration:
    """Test AWS X-Ray integration."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, xray_config):
        """Test X-Ray integration initialization."""
        integration = AWSXRayIntegration(xray_config)
        
        with patch('boto3.Session') as mock_session:
            mock_xray = Mock()
            
            mock_session_instance = Mock()
            mock_session_instance.client.return_value = mock_xray
            mock_session.return_value = mock_session_instance
            
            await integration.initialize()
            
            assert integration._initialized
            assert integration.xray_client is not None
    
    def test_trace_id_generation(self, xray_config):
        """Test X-Ray trace ID generation."""
        integration = AWSXRayIntegration(xray_config)
        
        trace_id = integration._create_trace_id()
        
        assert trace_id.startswith('1-')
        parts = trace_id.split('-')
        assert len(parts) == 3
    
    def test_segment_id_generation(self, xray_config):
        """Test X-Ray segment ID generation."""
        integration = AWSXRayIntegration(xray_config)
        
        segment_id = integration._create_segment_id()
        
        assert len(segment_id) == 16  # 64 bits in hex
    
    def test_event_to_xray_segment_start(self, xray_config):
        """Test event to X-Ray segment conversion (start event)."""
        integration = AWSXRayIntegration(xray_config)
        
        start_event = {
            'site_id': 'site1',
            'app': {'name': 'test-app', 'version': '1.0.0'},
            'entity': {
                'type': 'job',
                'id': 'test-job-123',
                'business_key': 'test-key'
            },
            'event': {
                'kind': 'started',
                'at': '2024-01-15T10:30:00Z',
                'metadata': {}
            }
        }
        
        segment = integration._event_to_xray_segment(start_event)
        
        # Start event should store segment but not return it
        assert segment is None
        assert 'test-job-123' in integration.pending_segments
    
    def test_event_to_xray_segment_finish(self, xray_config):
        """Test event to X-Ray segment conversion (finish event)."""
        integration = AWSXRayIntegration(xray_config)
        
        # Create start event first
        start_event = {
            'site_id': 'site1',
            'app': {'name': 'test-app', 'version': '1.0.0'},
            'entity': {
                'type': 'job',
                'id': 'test-job-123',
                'business_key': 'test-key'
            },
            'event': {
                'kind': 'started',
                'at': '2024-01-15T10:30:00Z',
                'metadata': {}
            }
        }
        integration._event_to_xray_segment(start_event)
        
        # Now create finish event
        finish_event = {
            'site_id': 'site1',
            'app': {'name': 'test-app', 'version': '1.0.0'},
            'entity': {
                'type': 'job',
                'id': 'test-job-123',
                'business_key': 'test-key'
            },
            'event': {
                'kind': 'finished',
                'status': 'succeeded',
                'at': '2024-01-15T10:32:00Z',
                'metrics': {
                    'duration_s': 120.0,
                    'cpu_user_s': 90.0,
                    'mem_max_mb': 512
                },
                'metadata': {}
            }
        }
        
        segment = integration._event_to_xray_segment(finish_event)
        
        assert segment is not None
        assert segment['name'] == 'test-app.job'
        assert segment['in_progress'] is False
        assert 'annotations' in segment
        assert segment['annotations']['status'] == 'succeeded'
        assert 'test-job-123' not in integration.pending_segments
    
    @pytest.mark.asyncio
    async def test_send_event(self, xray_config):
        """Test sending event to X-Ray."""
        integration = AWSXRayIntegration(xray_config)
        
        # Mock X-Ray client
        mock_xray = Mock()
        integration.xray_client = mock_xray
        integration._initialized = True
        
        # Create complete trace (start + finish)
        start_event = {
            'site_id': 'site1',
            'app': {'name': 'test-app', 'version': '1.0.0'},
            'entity': {'type': 'job', 'id': 'test-job-123', 'business_key': 'test-key'},
            'event': {'kind': 'started', 'at': '2024-01-15T10:30:00Z', 'metadata': {}}
        }
        
        finish_event = {
            'site_id': 'site1',
            'app': {'name': 'test-app', 'version': '1.0.0'},
            'entity': {'type': 'job', 'id': 'test-job-123', 'business_key': 'test-key'},
            'event': {
                'kind': 'finished',
                'status': 'succeeded',
                'at': '2024-01-15T10:32:00Z',
                'metrics': {'duration_s': 120.0},
                'metadata': {}
            }
        }
        
        # Send start (should not call X-Ray)
        result1 = await integration.send_event(start_event)
        assert result1 is True
        mock_xray.put_trace_segments.assert_not_called()
        
        # Send finish (should call X-Ray)
        result2 = await integration.send_event(finish_event)
        assert result2 is True
        mock_xray.put_trace_segments.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check(self, xray_config):
        """Test X-Ray health check."""
        integration = AWSXRayIntegration(xray_config)
        
        # Mock X-Ray client
        mock_xray = Mock()
        mock_xray.get_service_graph.return_value = {'Services': [{'Name': 'test-service'}]}
        
        integration.xray_client = mock_xray
        integration._initialized = True
        
        health = await integration.health_check()
        
        assert health['status'] == 'healthy'
        assert health['backend'] == 'aws_xray'
        assert health['service'] == 'test-service'


def test_aws_helpers_platform_detection():
    """Test AWS platform detection."""
    from apps.monitoring_sdk.monitoring_sdk.aws_helpers import detect_compute_platform
    
    # Mock Lambda environment
    with patch.dict('os.environ', {'AWS_LAMBDA_FUNCTION_NAME': 'test-function'}):
        platform = detect_compute_platform()
        assert platform == 'lambda'
    
    # Mock ECS environment
    with patch.dict('os.environ', {'ECS_CONTAINER_METADATA_URI_V4': 'http://169.254.170.2/v4'}):
        platform = detect_compute_platform()
        assert platform == 'ecs'


def test_aws_helpers_metadata_collection():
    """Test AWS metadata collection."""
    from apps.monitoring_sdk.monitoring_sdk.aws_helpers import (
        get_ec2_metadata,
        get_ecs_metadata,
        get_lambda_metadata
    )
    
    # Test Lambda metadata
    with patch.dict('os.environ', {
        'AWS_LAMBDA_FUNCTION_NAME': 'test-function',
        'AWS_LAMBDA_FUNCTION_VERSION': '1',
        'AWS_REGION': 'us-east-1'
    }):
        metadata = get_lambda_metadata()
        assert metadata['function_name'] == 'test-function'
        assert metadata['compute_platform'] == 'lambda'
    
    # Test ECS metadata (fallback to env vars)
    with patch.dict('os.environ', {
        'ECS_TASK_ID': 'task-123',
        'ECS_CLUSTER': 'prod-cluster'
    }):
        metadata = get_ecs_metadata()
        assert metadata['task_id'] == 'task-123'
        assert metadata['compute_platform'] == 'ecs'
    
    # Test EC2 metadata (fallback to env vars)
    with patch.dict('os.environ', {
        'EC2_INSTANCE_ID': 'i-1234567890abcdef0',
        'EC2_INSTANCE_TYPE': 't3.medium'
    }):
        metadata = get_ec2_metadata()
        assert metadata['instance_id'] == 'i-1234567890abcdef0'
        assert metadata['compute_platform'] == 'ec2'

