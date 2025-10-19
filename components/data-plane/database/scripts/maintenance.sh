#!/bin/bash
# ============================================================================
# TimescaleDB Maintenance Script
# ============================================================================
# Regular maintenance tasks for optimal performance
# ============================================================================

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-monitor}"
DB_USER="${DB_USER:-postgres}"
LOG_DIR="${LOG_DIR:-/var/log/wafer-monitor}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create log directory
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/maintenance_$TIMESTAMP.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}✗${NC} $1" | tee -a "$LOG_FILE"
}

# PostgreSQL connection string
export PGPASSWORD="${DB_PASSWORD}"
PSQL="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"

# ============================================================================
# Main maintenance tasks
# ============================================================================

log "=================================================="
log "Starting TimescaleDB Maintenance"
log "=================================================="

# 1. Vacuum and Analyze
log "Running VACUUM ANALYZE..."
if $PSQL -c "SELECT * FROM maintenance_vacuum_analyze();" >> "$LOG_FILE" 2>&1; then
    log_success "VACUUM ANALYZE completed"
else
    log_error "VACUUM ANALYZE failed"
fi

# 2. Update statistics
log "Updating table statistics..."
if $PSQL -c "ANALYZE;" >> "$LOG_FILE" 2>&1; then
    log_success "Statistics updated"
else
    log_error "Statistics update failed"
fi

# 3. Check chunk compression status
log "Checking chunk compression..."
$PSQL -c "
SELECT 
    hypertable_name,
    COUNT(*) AS total_chunks,
    COUNT(*) FILTER (WHERE is_compressed) AS compressed_chunks,
    pg_size_pretty(SUM(total_bytes)) AS total_size,
    pg_size_pretty(SUM(compressed_total_bytes)) AS compressed_size
FROM timescaledb_information.chunks
GROUP BY hypertable_name;
" | tee -a "$LOG_FILE"

# 4. Check for old uncompressed chunks
log "Checking for old uncompressed chunks..."
OLD_CHUNKS=$($PSQL -t -c "
SELECT COUNT(*)
FROM timescaledb_information.chunks
WHERE NOT is_compressed
    AND range_end < NOW() - INTERVAL '48 hours';
")

if [ "$OLD_CHUNKS" -gt 0 ]; then
    log_warning "Found $OLD_CHUNKS old uncompressed chunks"
    log "Running manual compression..."
    $PSQL -c "CALL timescaledb.compress_chunk(
        (SELECT chunk_schema || '.' || chunk_name 
         FROM timescaledb_information.chunks 
         WHERE NOT is_compressed 
            AND range_end < NOW() - INTERVAL '48 hours' 
         LIMIT 1)
    );" >> "$LOG_FILE" 2>&1 || log_warning "Manual compression failed"
else
    log_success "No old uncompressed chunks found"
fi

# 5. Check database size
log "Checking database size..."
$PSQL -c "
SELECT 
    schemaname || '.' || tablename AS table,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
" | tee -a "$LOG_FILE"

# 6. Check for bloat
log "Checking for table bloat..."
$PSQL -c "SELECT * FROM get_table_bloat();" | tee -a "$LOG_FILE"

# 7. Check slow queries
log "Checking for slow queries..."
$PSQL -c "SELECT * FROM get_slow_queries(1000) LIMIT 5;" | tee -a "$LOG_FILE"

# 8. Check replication lag (if applicable)
if $PSQL -c "\x" -c "SELECT * FROM pg_stat_replication;" | grep -q "slot_name"; then
    log "Checking replication lag..."
    $PSQL -x -c "
    SELECT 
        application_name,
        state,
        sync_state,
        pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn)) AS send_lag,
        pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) AS replay_lag
    FROM pg_stat_replication;
    " | tee -a "$LOG_FILE"
else
    log "No replication configured"
fi

# 9. Check connection count
log "Checking active connections..."
$PSQL -c "
SELECT 
    state,
    COUNT(*) AS count
FROM pg_stat_activity
WHERE datname = current_database()
GROUP BY state;
" | tee -a "$LOG_FILE"

# 10. Check long-running queries
log "Checking for long-running queries..."
LONG_QUERIES=$($PSQL -t -c "
SELECT COUNT(*)
FROM pg_stat_activity
WHERE state = 'active'
    AND now() - query_start > interval '5 minutes'
    AND datname = current_database();
")

if [ "$LONG_QUERIES" -gt 0 ]; then
    log_warning "Found $LONG_QUERIES long-running queries (>5 minutes)"
    $PSQL -c "
    SELECT 
        pid,
        now() - query_start AS duration,
        state,
        LEFT(query, 100) AS query
    FROM pg_stat_activity
    WHERE state = 'active'
        AND now() - query_start > interval '5 minutes'
        AND datname = current_database();
    " | tee -a "$LOG_FILE"
else
    log_success "No long-running queries"
fi

# 11. Update continuous aggregates
log "Refreshing continuous aggregates..."
$PSQL -c "CALL refresh_continuous_aggregate('job_stats_hourly', NULL, NULL);" >> "$LOG_FILE" 2>&1 || log_warning "Failed to refresh job_stats_hourly"
$PSQL -c "CALL refresh_continuous_aggregate('event_stats_hourly', NULL, NULL);" >> "$LOG_FILE" 2>&1 || log_warning "Failed to refresh event_stats_hourly"

# 12. Backup recent configuration
log "Backing up PostgreSQL configuration..."
$PSQL -c "
SELECT name, setting, unit
FROM pg_settings
WHERE name IN (
    'shared_buffers', 'effective_cache_size', 'work_mem',
    'maintenance_work_mem', 'max_connections', 'wal_buffers'
);
" > "$LOG_DIR/pg_config_$TIMESTAMP.txt"
log_success "Configuration backed up to $LOG_DIR/pg_config_$TIMESTAMP.txt"

# ============================================================================
# Summary
# ============================================================================

log "=================================================="
log "Maintenance Summary"
log "=================================================="

# Get overall database health
$PSQL -c "SELECT * FROM system_health;" | tee -a "$LOG_FILE"

log "=================================================="
log "Maintenance completed"
log "Full log: $LOG_FILE"
log "=================================================="

# Clean up old logs (keep last 30 days)
find "$LOG_DIR" -name "maintenance_*.log" -mtime +30 -delete 2>/dev/null || true

exit 0

