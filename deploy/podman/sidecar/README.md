# Monitoring Sidecar - Podman Deployment

Complete deployment solution for the Monitoring Sidecar using Podman with shared volume configuration management.

## 🎯 Overview

This deployment provides:
- **Containerized Sidecar**: Running in Podman with health checks
- **Shared Volume Configuration**: Host-accessible config directory for runtime updates
- **Hot Reload**: Configuration changes without container restart
- **Management API**: HTTP API for status and configuration reload
- **Production-Ready**: Resource limits, health checks, and logging

## 📋 Prerequisites

### Required
- **Podman** v4.0 or higher
- **curl** (for health checks and API calls)
- **Python 3** (for JSON formatting in scripts)

### Optional
- **podman-compose** (recommended for easier management)

### Installation

#### macOS
```bash
brew install podman podman-compose
podman machine init
podman machine start
```

#### Linux (Fedora/RHEL/CentOS)
```bash
sudo dnf install podman podman-compose
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get install podman podman-compose
```

## 🚀 Quick Start

### 1. Deploy the Sidecar

```bash
cd deploy/podman/sidecar
chmod +x *.sh
./up.sh
```

This will:
- Create host directories (`config/`, `data/`, `logs/`)
- Generate default configuration
- Build the container image
- Start the sidecar container
- Wait for health check to pass

### 2. Verify Deployment

```bash
./status.sh
```

### 3. Test the Sidecar

```bash
# Check health endpoint
curl http://localhost:17001/health

# Expected response:
# {"status": "healthy", "version": "2.0.0", "uptime": 123}
```

## 📁 Directory Structure

```
deploy/podman/sidecar/
├── docker-compose.yml       # Podman Compose configuration
├── up.sh                    # Deploy script
├── down.sh                  # Stop script
├── status.sh                # Status check script
├── reload-config.sh         # Configuration reload script
├── README.md                # This file
├── config/                  # Configuration directory (host-accessible)
│   └── sidecar.yaml        # Sidecar configuration
├── data/                    # Data directory (buffering)
└── logs/                    # Logs directory
```

## ⚙️ Configuration Management

### Configuration File Location

**Host Path**: `deploy/podman/sidecar/config/sidecar.yaml`  
**Container Path**: `/app/config/sidecar.yaml`

The configuration file is mounted as a shared volume, making it directly accessible from the host.

### Default Configuration

```yaml
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

  filesystem:
    enabled: false
    priority: 2
    path: "/app/data/monitoring"

  s3:
    enabled: false
    priority: 3
    bucket: "monitoring-data"

# Routing Rules
routing:
  global:
    backends:
      - timescaledb
  services: {}

# Hot Reload Configuration
hot_reload:
  enabled: true
  watch_interval: 5
```

### Editing Configuration

#### Option 1: Direct Edit on Host

```bash
# Edit configuration file
vim config/sidecar.yaml

# Reload configuration (no restart needed!)
./reload-config.sh
```

#### Option 2: Edit Inside Container

```bash
# Access container shell
podman exec -it monitoring-sidecar /bin/bash

# Edit configuration
vi /app/config/sidecar.yaml

# Exit container
exit

# Reload from host
./reload-config.sh
```

#### Option 3: Programmatic Update

```bash
# Update configuration via script
cat > config/sidecar.yaml << 'EOF'
# Your updated configuration
EOF

# Reload
curl -X POST http://localhost:17001/reload
```

### Configuration Reload

The sidecar supports **hot reload** without container restart:

```bash
# Method 1: Use reload script
./reload-config.sh

# Method 2: Direct API call
curl -X POST http://localhost:17001/reload

# Method 3: Automatic (if hot_reload.enabled: true)
# Configuration is automatically reloaded every 5 seconds
```

## 🔧 Management Commands

### Deployment

```bash
# Deploy sidecar
./up.sh

# Stop sidecar
./down.sh

# Restart sidecar
podman restart monitoring-sidecar
```

### Monitoring

```bash
# Check status
./status.sh

# View logs (follow mode)
podman logs -f monitoring-sidecar

# View last 100 lines
podman logs --tail 100 monitoring-sidecar

# Check resource usage
podman stats monitoring-sidecar
```

### Configuration

```bash
# Reload configuration
./reload-config.sh

# Validate configuration
curl http://localhost:17001/config

# View current configuration
cat config/sidecar.yaml
```

### Health & Diagnostics

```bash
# Health check
curl http://localhost:17001/health

# Detailed status
curl http://localhost:17001/status

# Metrics (Prometheus format)
curl http://localhost:17001/metrics

# Container inspection
podman inspect monitoring-sidecar
```

## 🌐 Network Configuration

### Exposed Ports

| Port  | Protocol | Purpose           | Access     |
|-------|----------|-------------------|------------|
| 17000 | TCP      | SDK Connections   | SDKs       |
| 17001 | HTTP     | Management API    | Management |

### Firewall Configuration

If using a firewall, allow these ports:

```bash
# Firewalld (Fedora/RHEL/CentOS)
sudo firewall-cmd --permanent --add-port=17000/tcp
sudo firewall-cmd --permanent --add-port=17001/tcp
sudo firewall-cmd --reload

# UFW (Ubuntu/Debian)
sudo ufw allow 17000/tcp
sudo ufw allow 17001/tcp
```

## 💾 Volume Management

### Volume Mounts

| Host Path | Container Path | Purpose        | Mode |
|-----------|---------------|----------------|------|
| `config/` | `/app/config` | Configuration  | rw   |
| `data/`   | `/app/data`   | Data buffering | rw   |
| `logs/`   | `/app/logs`   | Log files      | rw   |

### Backup Configuration

```bash
# Backup configuration
tar -czf sidecar-config-$(date +%Y%m%d).tar.gz config/

# Restore configuration
tar -xzf sidecar-config-20241021.tar.gz
./reload-config.sh
```

### Clean Data and Logs

```bash
# Remove data and logs (preserves config)
rm -rf data/* logs/*

# Or use down script with cleanup option
./down.sh
# Select 'y' when prompted to remove volumes
```

## 🔒 Security

### Non-Root User

The container runs as a non-root user (`sidecar:1000`) for security.

### Security Options

```yaml
security_opt:
  - no-new-privileges:true
```

### Access Control

Restrict API access using firewall rules or network policies:

```bash
# Allow only localhost
sudo iptables -A INPUT -p tcp --dport 17001 -s 127.0.0.1 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 17001 -j DROP
```

## 📊 Resource Limits

### Default Limits

```yaml
resources:
  limits:
    cpus: '2.0'
    memory: 1G
  reservations:
    cpus: '0.5'
    memory: 256M
```

### Adjust Limits

Edit `docker-compose.yml` or pass to `podman run`:

```bash
podman update \
  --cpus 4 \
  --memory 2g \
  monitoring-sidecar
```

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check container logs
podman logs monitoring-sidecar

# Check configuration syntax
python3 -c "import yaml; yaml.safe_load(open('config/sidecar.yaml'))"

# Verify volume mounts
podman inspect monitoring-sidecar --format='{{.Mounts}}'
```

### Configuration Not Reloading

```bash
# Check hot reload is enabled
grep "hot_reload" config/sidecar.yaml

# Check API is responding
curl http://localhost:17001/health

# Check logs for reload messages
podman logs --tail 50 monitoring-sidecar | grep reload
```

### Connection Refused

```bash
# Check container is running
podman ps | grep monitoring-sidecar

# Check ports are mapped
podman port monitoring-sidecar

# Check firewall
sudo firewall-cmd --list-ports
```

### High Resource Usage

```bash
# Check resource usage
podman stats monitoring-sidecar

# Review configuration for buffering/batch sizes
grep -E "batch_size|buffer_size" config/sidecar.yaml

# Check for memory leaks
podman top monitoring-sidecar
```

## 🔄 Runtime Configuration Updates

### Example: Add New Backend

1. **Edit configuration**:
```bash
vim config/sidecar.yaml
```

2. **Add ELK backend**:
```yaml
backends:
  elk:
    enabled: true
    priority: 4
    elasticsearch:
      hosts: ["http://elk-server:9200"]
      index: "monitoring"
```

3. **Reload configuration**:
```bash
./reload-config.sh
```

4. **Verify**:
```bash
curl http://localhost:17001/config | jq '.backends.elk'
```

### Example: Update Routing Rules

```bash
# Edit routing rules
cat >> config/sidecar.yaml << 'EOF'
routing:
  services:
    critical-service:
      backends:
        - timescaledb
        - s3  # Add redundancy
    analytics-service:
      backends:
        - filesystem  # Use filesystem for analytics
EOF

# Reload
./reload-config.sh
```

## 📈 Performance Tuning

### High-Throughput Configuration

```yaml
listener:
  max_connections: 5000
  buffer_size: 50000

backends:
  timescaledb:
    batch_size: 500
    flush_interval: 10
    connection_pool_size: 20
```

### Low-Latency Configuration

```yaml
listener:
  max_connections: 1000
  buffer_size: 5000

backends:
  timescaledb:
    batch_size: 50
    flush_interval: 1
    connection_pool_size: 10
```

## 🚦 Health Checks

### Built-in Health Check

The container includes automatic health checks:

```bash
# View health status
podman inspect monitoring-sidecar --format='{{.State.Health.Status}}'

# View health log
podman inspect monitoring-sidecar --format='{{json .State.Health.Log}}' | jq
```

### Custom Health Checks

```bash
# TCP socket check
nc -zv localhost 17000

# API health check
curl -f http://localhost:17001/health

# Full status check
./status.sh
```

## 📚 Integration Examples

### Python SDK Connection

```python
from monitoring_sdk import MonitoringSDK

sdk = MonitoringSDK(
    source='my-service',
    tcp_host='localhost',  # Sidecar host
    tcp_port=17000         # Sidecar port
)

sdk.log_event('info', 'Service started')
```

### Perl SDK Connection

```perl
use MonitoringSDK;

my $mon = MonitoringSDK->new(
    source   => 'my-service',
    tcp_host => 'localhost',
    tcp_port => 17000
);

$mon->log_event('info', 'Service started');
```

## 🔗 Related Documentation

- [Monitoring V2 Architecture](../../../components/monitoring-v2/ARCHITECTURE_V2.md)
- [Job Analysis Feature](../../../components/monitoring-v2/JOB_ANALYSIS_FEATURE.md)
- [SDK Documentation](../../../components/monitoring-v2/SDK_DOCUMENTATION.md)

## 📞 Support

For issues or questions:
1. Check logs: `podman logs monitoring-sidecar`
2. Run status check: `./status.sh`
3. Review configuration: `cat config/sidecar.yaml`

---

**Monitoring Sidecar v2.0** - Production-ready containerized deployment with runtime configuration management

