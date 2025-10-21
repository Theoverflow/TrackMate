# Multi-stage build for Monitoring Sidecar
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash sidecar

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/sidecar/.local

# Copy application files
COPY main.py .
COPY listener/ ./listener/
COPY router/ ./router/
COPY backends/ ./backends/
COPY protocol/ ./protocol/

# Create directories
RUN mkdir -p /app/config /app/data /app/logs && \
    chown -R sidecar:sidecar /app

# Switch to non-root user
USER sidecar

# Update PATH
ENV PATH=/home/sidecar/.local/bin:$PATH

# Expose ports
EXPOSE 17000 17001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:17001/health || exit 1

# Start sidecar
CMD ["python", "-u", "main.py"]

