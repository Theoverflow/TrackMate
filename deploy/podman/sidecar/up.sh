#!/bin/bash
# Deploy Monitoring Sidecar with Podman
# Usage: ./up.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                          ║${NC}"
echo -e "${GREEN}║           Monitoring Sidecar - Podman Deployment                        ║${NC}"
echo -e "${GREEN}║                                                                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if Podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}✗ Podman is not installed. Please install Podman first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Podman found: $(podman --version)${NC}"

# Check if podman-compose is installed
if ! command -v podman-compose &> /dev/null; then
    echo -e "${YELLOW}⚠ podman-compose not found. Using podman directly...${NC}"
    USE_COMPOSE=false
else
    echo -e "${GREEN}✓ podman-compose found: $(podman-compose --version)${NC}"
    USE_COMPOSE=true
fi

echo ""
echo -e "${YELLOW}📦 Step 1: Creating host directories${NC}"

# Create host directories for volumes
mkdir -p config data logs

echo -e "${GREEN}✓ Created directories: config/, data/, logs/${NC}"

# Create default configuration if it doesn't exist
if [ ! -f "config/sidecar.yaml" ]; then
    echo -e "${YELLOW}⚠ Configuration file not found. Creating default configuration...${NC}"
    cat > config/sidecar.yaml << 'EOF'
# Monitoring Sidecar Configuration
version: "1.0"

# TCP Listener Configuration
listener:
  host: "0.0.0.0"
  port: 17000
  max_connections: 1000
  buffer_size: 10000

# Management API Configuration
api:
  host: "0.0.0.0"
  port: 17001
  enabled: true

# Backend Configuration
backends:
  # TimescaleDB Backend
  timescaledb:
    enabled: true
    priority: 1
    connection:
      host: "localhost"
      port: 5432
      database: "monitoring"
      user: "monitoring_user"
      password: "monitoring_password"
    batch_size: 100
    flush_interval: 5

  # Filesystem Backend
  filesystem:
    enabled: false
    priority: 2
    path: "/app/data/monitoring"
    rotation:
      max_size_mb: 100
      max_files: 10

  # S3 Backend
  s3:
    enabled: false
    priority: 3
    bucket: "monitoring-data"
    region: "us-east-1"
    prefix: "sidecar/"

  # ELK Backend
  elk:
    enabled: false
    priority: 4
    elasticsearch:
      hosts: ["http://localhost:9200"]
      index: "monitoring"

# Correlation Engine Configuration
correlation:
  enabled: true
  trace_timeout: 300  # seconds
  max_traces: 10000

# Routing Rules
routing:
  # Global rules (apply to all sources)
  global:
    backends:
      - timescaledb
  
  # Per-service rules
  services: {}
    # Example:
    # my-service:
    #   backends:
    #     - timescaledb
    #     - filesystem

# Hot Reload Configuration
hot_reload:
  enabled: true
  watch_interval: 5  # seconds

# Logging Configuration
logging:
  level: "info"
  format: "json"
  file: "/app/logs/sidecar.log"
EOF
    echo -e "${GREEN}✓ Created default configuration: config/sidecar.yaml${NC}"
fi

echo ""
echo -e "${YELLOW}📦 Step 2: Building container image${NC}"

# Build the image
podman build -t monitoring-sidecar:latest -f ../../../components/monitoring-v2/sidecar/Dockerfile ../../../components/monitoring-v2/sidecar/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Container image built successfully${NC}"
else
    echo -e "${RED}✗ Failed to build container image${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}📦 Step 3: Starting sidecar container${NC}"

# Stop and remove existing container if it exists
if podman ps -a --format "{{.Names}}" | grep -q "monitoring-sidecar"; then
    echo -e "${YELLOW}⚠ Stopping existing container...${NC}"
    podman stop monitoring-sidecar 2>/dev/null || true
    podman rm monitoring-sidecar 2>/dev/null || true
fi

if [ "$USE_COMPOSE" = true ]; then
    # Use podman-compose
    podman-compose up -d
else
    # Use podman directly
    podman run -d \
        --name monitoring-sidecar \
        --restart unless-stopped \
        -p 17000:17000 \
        -p 17001:17001 \
        -v "$(pwd)/config:/app/config:rw" \
        -v "$(pwd)/data:/app/data:rw" \
        -v "$(pwd)/logs:/app/logs:rw" \
        -e SIDECAR_CONFIG_FILE=/app/config/sidecar.yaml \
        -e SIDECAR_HOT_RELOAD=true \
        -e LOG_LEVEL=info \
        --health-cmd="curl -f http://localhost:17001/health || exit 1" \
        --health-interval=30s \
        --health-timeout=10s \
        --health-retries=3 \
        --health-start-period=10s \
        monitoring-sidecar:latest
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Sidecar container started${NC}"
else
    echo -e "${RED}✗ Failed to start sidecar container${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}📦 Step 4: Waiting for sidecar to be healthy...${NC}"

# Wait for container to be healthy
MAX_WAIT=60
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    HEALTH=$(podman inspect monitoring-sidecar --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")
    
    if [ "$HEALTH" = "healthy" ]; then
        echo -e "${GREEN}✓ Sidecar is healthy!${NC}"
        break
    fi
    
    echo -n "."
    sleep 2
    WAITED=$((WAITED + 2))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ Timeout waiting for sidecar to become healthy${NC}"
    echo -e "${YELLOW}Check logs with: podman logs monitoring-sidecar${NC}"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                          ║${NC}"
echo -e "${GREEN}║           ✅ Monitoring Sidecar Deployment Complete! ✅                ║${NC}"
echo -e "${GREEN}║                                                                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}📊 Service Information:${NC}"
echo -e "   • Container: monitoring-sidecar"
echo -e "   • TCP Socket: localhost:17000"
echo -e "   • Management API: http://localhost:17001"
echo -e "   • Health Check: http://localhost:17001/health"
echo ""

echo -e "${GREEN}📁 Volume Mounts (Host-Accessible):${NC}"
echo -e "   • Configuration: $(pwd)/config/"
echo -e "   • Data: $(pwd)/data/"
echo -e "   • Logs: $(pwd)/logs/"
echo ""

echo -e "${GREEN}🔧 Useful Commands:${NC}"
echo -e "   • View logs:      ${YELLOW}podman logs -f monitoring-sidecar${NC}"
echo -e "   • Check status:   ${YELLOW}podman ps${NC}"
echo -e "   • Stop:           ${YELLOW}./down.sh${NC}"
echo -e "   • Edit config:    ${YELLOW}vim config/sidecar.yaml${NC}"
echo -e "   • Reload config:  ${YELLOW}curl -X POST http://localhost:17001/reload${NC}"
echo ""

echo -e "${GREEN}✓ Ready to receive monitoring data!${NC}"
echo ""

