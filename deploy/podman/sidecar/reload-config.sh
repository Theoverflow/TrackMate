#!/bin/bash
# Reload Sidecar Configuration at Runtime
# Usage: ./reload-config.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Reloading Sidecar Configuration...${NC}"
echo ""

# Check if container is running
if ! podman ps --format "{{.Names}}" | grep -q "monitoring-sidecar"; then
    echo -e "${RED}✗ Sidecar container is not running${NC}"
    exit 1
fi

# Trigger configuration reload via API
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:17001/reload 2>/dev/null || echo "000")
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Configuration reloaded successfully${NC}"
    echo ""
    echo -e "${GREEN}Response:${NC}"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
elif [ "$HTTP_CODE" = "000" ]; then
    echo -e "${RED}✗ Failed to connect to sidecar API${NC}"
    echo -e "${YELLOW}ℹ  Is the sidecar running? Check with: podman ps${NC}"
    exit 1
else
    echo -e "${RED}✗ Configuration reload failed (HTTP $HTTP_CODE)${NC}"
    echo ""
    echo -e "${RED}Response:${NC}"
    echo "$BODY"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Sidecar is now using the updated configuration${NC}"
echo ""

