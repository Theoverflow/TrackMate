#!/bin/bash
# Stop Monitoring Sidecar
# Usage: ./down.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║                                                                          ║${NC}"
echo -e "${YELLOW}║           Stopping Monitoring Sidecar                                   ║${NC}"
echo -e "${YELLOW}║                                                                          ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if podman-compose is available
if command -v podman-compose &> /dev/null && [ -f "docker-compose.yml" ]; then
    echo -e "${YELLOW}⏹  Stopping sidecar using podman-compose...${NC}"
    podman-compose down
else
    echo -e "${YELLOW}⏹  Stopping sidecar container...${NC}"
    podman stop monitoring-sidecar 2>/dev/null || true
    podman rm monitoring-sidecar 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}✓ Monitoring Sidecar stopped${NC}"
echo ""

# Optional: Remove volumes
read -p "Do you want to remove data volumes? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}⚠  Removing data and logs...${NC}"
    rm -rf data/* logs/*
    echo -e "${GREEN}✓ Data and logs removed${NC}"
    echo -e "${YELLOW}ℹ  Configuration preserved in config/${NC}"
fi

echo ""
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

