#!/bin/bash
# Check Monitoring Sidecar Status
# Usage: ./status.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                                          ║${NC}"
echo -e "${BLUE}║           Monitoring Sidecar Status                                     ║${NC}"
echo -e "${BLUE}║                                                                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if container exists
if ! podman ps -a --format "{{.Names}}" | grep -q "monitoring-sidecar"; then
    echo -e "${RED}✗ Sidecar container not found${NC}"
    echo -e "${YELLOW}ℹ  Deploy with: ./up.sh${NC}"
    exit 1
fi

# Get container status
RUNNING=$(podman ps --format "{{.Names}}" | grep "monitoring-sidecar" || echo "")
STATUS=$(podman inspect monitoring-sidecar --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
HEALTH=$(podman inspect monitoring-sidecar --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
STARTED=$(podman inspect monitoring-sidecar --format='{{.State.StartedAt}}' 2>/dev/null || echo "unknown")

echo -e "${BLUE}📦 Container Information:${NC}"
echo -e "   Name: monitoring-sidecar"
echo -e "   Status: $STATUS"

if [ "$STATUS" = "running" ]; then
    echo -e "   Health: $HEALTH"
    echo -e "   Started: $STARTED"
    echo -e "   ${GREEN}✓ Running${NC}"
else
    echo -e "   ${RED}✗ Not running${NC}"
    exit 1
fi

echo ""

# Check ports
echo -e "${BLUE}🔌 Network Ports:${NC}"
PORTS=$(podman port monitoring-sidecar 2>/dev/null || echo "none")
if [ "$PORTS" != "none" ]; then
    echo "$PORTS" | while read -r line; do
        echo -e "   $line"
    done
else
    echo -e "   ${YELLOW}⚠  No ports mapped${NC}"
fi

echo ""

# Check health endpoint
echo -e "${BLUE}🏥 Health Check:${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:17001/health 2>/dev/null || echo "")
if [ -n "$HEALTH_RESPONSE" ]; then
    echo -e "   ${GREEN}✓ API responding${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null | sed 's/^/   /' || echo "   $HEALTH_RESPONSE"
else
    echo -e "   ${RED}✗ API not responding${NC}"
fi

echo ""

# Check volumes
echo -e "${BLUE}💾 Volume Mounts:${NC}"
CONFIG_PATH="$(pwd)/config"
DATA_PATH="$(pwd)/data"
LOGS_PATH="$(pwd)/logs"

if [ -d "$CONFIG_PATH" ]; then
    CONFIG_SIZE=$(du -sh "$CONFIG_PATH" 2>/dev/null | cut -f1)
    echo -e "   Config: $CONFIG_PATH (${CONFIG_SIZE})"
else
    echo -e "   ${RED}✗ Config directory not found${NC}"
fi

if [ -d "$DATA_PATH" ]; then
    DATA_SIZE=$(du -sh "$DATA_PATH" 2>/dev/null | cut -f1)
    echo -e "   Data:   $DATA_PATH (${DATA_SIZE})"
else
    echo -e "   ${YELLOW}⚠  Data directory not found${NC}"
fi

if [ -d "$LOGS_PATH" ]; then
    LOGS_SIZE=$(du -sh "$LOGS_PATH" 2>/dev/null | cut -f1)
    LOG_FILES=$(ls -1 "$LOGS_PATH" 2>/dev/null | wc -l)
    echo -e "   Logs:   $LOGS_PATH (${LOGS_SIZE}, ${LOG_FILES} files)"
else
    echo -e "   ${YELLOW}⚠  Logs directory not found${NC}"
fi

echo ""

# Check configuration file
echo -e "${BLUE}⚙️  Configuration:${NC}"
if [ -f "$CONFIG_PATH/sidecar.yaml" ]; then
    CONFIG_MTIME=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$CONFIG_PATH/sidecar.yaml" 2>/dev/null || stat -c "%y" "$CONFIG_PATH/sidecar.yaml" 2>/dev/null | cut -d. -f1)
    CONFIG_SIZE=$(ls -lh "$CONFIG_PATH/sidecar.yaml" | awk '{print $5}')
    echo -e "   File: sidecar.yaml"
    echo -e "   Size: $CONFIG_SIZE"
    echo -e "   Modified: $CONFIG_MTIME"
    echo -e "   ${GREEN}✓ Configuration file exists${NC}"
else
    echo -e "   ${RED}✗ Configuration file not found${NC}"
fi

echo ""

# Resource usage
echo -e "${BLUE}📊 Resource Usage:${NC}"
CPU=$(podman stats --no-stream --format "{{.CPUPerc}}" monitoring-sidecar 2>/dev/null || echo "N/A")
MEM=$(podman stats --no-stream --format "{{.MemUsage}}" monitoring-sidecar 2>/dev/null || echo "N/A")
echo -e "   CPU: $CPU"
echo -e "   Memory: $MEM"

echo ""

# Recent logs
echo -e "${BLUE}📝 Recent Logs (last 10 lines):${NC}"
podman logs --tail 10 monitoring-sidecar 2>/dev/null | sed 's/^/   /' || echo -e "   ${YELLOW}⚠  Unable to retrieve logs${NC}"

echo ""
echo -e "${GREEN}✓ Status check complete${NC}"
echo ""

# Useful commands
echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo -e "   View logs:      ${YELLOW}podman logs -f monitoring-sidecar${NC}"
echo -e "   Reload config:  ${YELLOW}./reload-config.sh${NC}"
echo -e "   Stop:           ${YELLOW}./down.sh${NC}"
echo -e "   Restart:        ${YELLOW}podman restart monitoring-sidecar${NC}"
echo ""

