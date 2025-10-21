#!/bin/bash

# Demo Script for Monitoring V2
# Runs the sidecar and example Perl applications

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║          Monitoring V2 - TCP-Based Demo                       ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check dependencies
echo "Checking dependencies..."

# Python dependencies
if ! python3 -c "import asyncio, yaml, aiofiles" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip3 install pyyaml aiofiles
fi

# Perl dependencies
if ! perl -MJSON::PP -e 1 2>/dev/null; then
    echo "Installing Perl dependencies..."
    cpan JSON::PP
fi

if ! perl -MIO::Socket::INET -e 1 2>/dev/null; then
    echo "IO::Socket::INET not found. Please install: cpan IO::Socket::INET"
    exit 1
fi

echo "✓ Dependencies OK"
echo ""

# Create log directory
mkdir -p /tmp/monitoring-logs
echo "✓ Log directory created: /tmp/monitoring-logs"
echo ""

# Start sidecar in background
echo "Starting sidecar..."
cd "$SCRIPT_DIR/.."
python3 -m sidecar.main "$SCRIPT_DIR/sidecar-config.yaml" > /tmp/sidecar.log 2>&1 &
SIDECAR_PID=$!
echo "✓ Sidecar started (PID: $SIDECAR_PID)"
echo "  Logs: /tmp/sidecar.log"
echo ""

# Wait for sidecar to start
echo "Waiting for sidecar to initialize..."
sleep 2

# Check if sidecar is running
if ! kill -0 $SIDECAR_PID 2>/dev/null; then
    echo "✗ Sidecar failed to start! Check /tmp/sidecar.log"
    exit 1
fi

echo "✓ Sidecar ready"
echo ""

# Run Perl applications
cd "$SCRIPT_DIR/perl-app"

echo "════════════════════════════════════════════════════════════════"
echo "Running Service 1: Config Parser"
echo "════════════════════════════════════════════════════════════════"
chmod +x service1_config_parser.pl
perl service1_config_parser.pl
echo ""

sleep 1

echo "════════════════════════════════════════════════════════════════"
echo "Running Service 2: File Receiver"
echo "════════════════════════════════════════════════════════════════"
chmod +x service2_file_receiver.pl
perl service2_file_receiver.pl
echo ""

sleep 1

echo "════════════════════════════════════════════════════════════════"
echo "Running Service 3: Queue Manager (calls DB Loader)"
echo "════════════════════════════════════════════════════════════════"
chmod +x service3_queue_manager.pl script_db_loader.pl
perl service3_queue_manager.pl
echo ""

# Wait a bit for final message flush
echo "Waiting for final message flush..."
sleep 3

# Stop sidecar
echo "Stopping sidecar..."
kill $SIDECAR_PID 2>/dev/null || true
wait $SIDECAR_PID 2>/dev/null || true
echo "✓ Sidecar stopped"
echo ""

# Show results
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║                      DEMO COMPLETE!                            ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "📊 Results:"
echo ""
echo "1. Sidecar log:"
echo "   tail /tmp/sidecar.log"
echo ""
echo "2. Monitoring events (JSONL files):"
echo "   ls -lh /tmp/monitoring-logs/"
echo ""

# Show event files
if [ -d "/tmp/monitoring-logs" ]; then
    echo "   Event files created:"
    ls -1 /tmp/monitoring-logs/ 2>/dev/null | while read file; do
        count=$(wc -l < "/tmp/monitoring-logs/$file" 2>/dev/null || echo 0)
        echo "     • $file ($count events)"
    done
fi

echo ""
echo "3. View events:"
echo "   cat /tmp/monitoring-logs/config-service-*.jsonl | jq"
echo "   cat /tmp/monitoring-logs/file-receiver-*.jsonl | jq"
echo "   cat /tmp/monitoring-logs/queue-service-*.jsonl | jq"
echo "   cat /tmp/monitoring-logs/db-loader-*.jsonl | jq"
echo ""

echo "✅ Demo finished successfully!"
echo ""

