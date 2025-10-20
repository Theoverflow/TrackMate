# Python Integration Test Environment
FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy monitoring SDK
COPY components/monitoring/sdk/monitoring_sdk /workspace/monitoring_sdk

# Copy shared utilities
COPY shared /workspace/shared

# Copy business app
COPY examples/business_apps/python_multiprocess_job.py /workspace/

# Install Python dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    httpx \
    pydantic \
    psutil

# Install monitoring SDK
RUN cd /workspace/monitoring_sdk && pip install -e .

# Copy tests
COPY components/tests/integration/python/test_python_integration.py /workspace/tests/

# Set Python path
ENV PYTHONPATH=/workspace

# Run tests by default
CMD ["pytest", "/workspace/tests/", "-v", "--cov=/workspace", "--cov-report=term-missing"]

