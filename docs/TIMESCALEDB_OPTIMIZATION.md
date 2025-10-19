# TimescaleDB Optimization Guide

## Overview

This guide covers comprehensive TimescaleDB enhancements including configuration, monitoring, stored procedures, and optimization techniques for the Wafer Monitor system.

## 📁 Files

- `ops/sql/timescaledb_enhancements.sql` - Advanced features and stored procedures
- `ops/sql/timescaledb_config.sql` - PostgreSQL/TimescaleDB configuration
- `ops/scripts/monitor_timescaledb.py` - Monitoring script
- `ops/scripts/maintenance.sh` - Automated maintenance script

## 🚀 Quick Start

### 1. Apply Enhancements

```bash
# Apply enhancements (continuous aggregates, procedures, etc.)
psql -U postgres -d monitor -f ops/sql/timescaledb_enhancements.sql

# Apply configuration (optional, can be done via postgresql.conf)
psql -U postgres -d monitor -f ops/sql/timescaledb_config.sql

# Reload configuration
sudo systemctl reload postgresql
# or
pg_ctl reload
```

### 2. Run Monitoring

```bash
# Check database health
python ops/scripts/monitor_timescaledb.py

# Run maintenance
./ops/scripts/maintenance.sh
```

### 3. Schedule Regular Maintenance

```bash
# Add to crontab
crontab -e

# Run maintenance daily at 2 AM
0 2 * * * /path/to/ops/scripts/maintenance.sh

# Run monitoring every hour
0 * * * * /path/to/ops/scripts/monitor_timescaledb.py
```

## 🔧 Features Implemented

### 1. Advanced Hypertable Configuration

#### Chunk Time Intervals
```sql
-- Optimized chunk sizes based on data volume
job: 1 day chunks
subjob: 1 day chunks
event: 6 hour chunks (high volume)
```

#### Compression
- **Automatic compression** for chunks older than 24 hours
- **Segmented by**: site_id, app_id, status
- **Ordered by**: timestamp descending
- **Compression ratio**: Typically 70-90% size reduction

#### Retention Policies
- **Hot storage**: 72 hours (configurable)
- **Automatic cleanup**: Old data removed automatically
- **Archival**: Use archiver service for S3 long-term storage

### 2. Continuous Aggregates

Pre-computed aggregations for fast queries:

#### `job_stats_hourly`
- Hourly job statistics
- Success rates, duration stats, resource usage
- Auto-refreshed every hour

#### `job_stats_daily`
- Daily aggregated statistics
- Success rates by app and site
- Auto-refreshed daily

#### `event_stats_hourly`
- Event counts by type and kind
- Auto-refreshed every 30 minutes

**Query continuous aggregates:**
```sql
-- Get hourly stats for last 24 hours
SELECT * FROM job_stats_hourly
WHERE hour > NOW() - INTERVAL '24 hours'
ORDER BY hour DESC;

-- Get daily stats for last 7 days
SELECT * FROM job_stats_daily
WHERE day > NOW() - INTERVAL '7 days'
ORDER BY day DESC;
```

### 3. Monitoring Views

#### `system_health`
Overall system health snapshot:
```sql
SELECT * FROM system_health;
```

Returns:
- Total sites and apps
- Jobs in last 5 minutes, 1 hour
- Currently running jobs
- Failed jobs in last hour
- Average duration and peak memory

#### `app_success_rates`
Success rates by application:
```sql
SELECT * FROM app_success_rates;
```

#### `recent_failures`
Recent job failures with error details:
```sql
SELECT * FROM recent_failures LIMIT 10;
```

#### `performance_outliers`
Jobs taking significantly longer than average:
```sql
SELECT * FROM performance_outliers;
```

#### `chunk_health`
TimescaleDB chunk compression status:
```sql
SELECT * FROM chunk_health;
```

#### `database_size_overview`
Table and index sizes:
```sql
SELECT * FROM database_size_overview;
```

### 4. Stored Procedures

#### Get Job Statistics
```sql
-- Get stats for fab1 in last 24 hours
SELECT * FROM get_job_stats(
    'fab1',
    NOW() - INTERVAL '24 hours',
    NOW()
);
```

#### Get Slowest Jobs
```sql
-- Get top 10 slowest jobs from fab1 in last 24 hours
SELECT * FROM get_slowest_jobs('fab1', 10, 24);
```

#### Failure Analysis
```sql
-- Analyze failures by error type
SELECT * FROM get_failure_analysis('fab1', 24);
```

#### Check High Failure Rates
```sql
-- Alert if failure rate > 10% in last hour
SELECT * FROM check_high_failure_rate(10, 1);
```

#### Check for No Activity
```sql
-- Alert if no activity for 30 minutes
SELECT * FROM check_no_activity(30);
```

#### Maintenance Operations
```sql
-- Run vacuum and analyze
SELECT * FROM maintenance_vacuum_analyze();

-- Reindex all tables
SELECT * FROM maintenance_reindex();
```

### 5. Performance Optimizations

#### Indexes Created

**Composite indexes** for common queries:
- `idx_job_site_app_status_time` - Site + app + status + time
- `idx_job_app_status_duration` - App + status + duration
- `idx_subjob_job_status` - Parent job + status
- `idx_event_entity_kind_time` - Entity + kind + time

**GIN indexes** for JSON queries:
- `idx_job_metadata_gin` - Job metadata
- `idx_event_payload_gin` - Event payload

**Partial indexes** for common filters:
- `idx_job_failed` - Failed jobs only
- `idx_job_running` - Running jobs only
- `idx_job_long_duration` - Long-running jobs (>5 min)

#### Query Optimization Tips

1. **Use continuous aggregates** for time-based statistics
2. **Leverage indexes** by including indexed columns in WHERE clauses
3. **Filter by time first** to use hypertable partitioning
4. **Use prepared statements** to cache query plans
5. **Monitor with pg_stat_statements** to find slow queries

### 6. Configuration Recommendations

#### Memory Settings (for 16GB RAM server)

```sql
shared_buffers = '4GB'              -- 25% of RAM
effective_cache_size = '12GB'       -- 75% of RAM
work_mem = '40MB'                   -- Per-operation memory
maintenance_work_mem = '1GB'        -- For maintenance ops
```

#### WAL Settings

```sql
wal_buffers = '16MB'
max_wal_size = '4GB'
min_wal_size = '1GB'
checkpoint_completion_target = 0.9
wal_compression = 'on'
```

#### Autovacuum Settings

```sql
autovacuum = 'on'
autovacuum_max_workers = 4
autovacuum_naptime = '10s'
autovacuum_vacuum_cost_delay = '2ms'
```

#### TimescaleDB Settings

```sql
timescaledb.max_background_workers = 8
timescaledb.max_parallel_workers_per_gather = 4
```

### 7. Monitoring & Alerting

#### Python Monitoring Script

```bash
# Run health check
python ops/scripts/monitor_timescaledb.py

# Output:
# ✅ System Health: OK
# ⚠️  High Failure Rate: WARNING
# ✅ Activity: OK
# ✅ Compression: OK
```

The script checks:
- System health metrics
- High failure rates (>10%)
- No activity alerts (>30 min)
- Chunk compression status
- Database size
- Slow queries
- Performance metrics

#### Maintenance Script

```bash
# Run maintenance tasks
./ops/scripts/maintenance.sh

# Tasks performed:
# - VACUUM ANALYZE all tables
# - Update statistics
# - Check compression status
# - Check for bloat
# - Check slow queries
# - Check long-running queries
# - Refresh continuous aggregates
```

## 📊 Performance Benchmarks

### Expected Performance

| Operation | Target | Optimized |
|-----------|--------|-----------|
| Single event insert | <10ms | <5ms |
| Batch insert (100) | <100ms | <50ms |
| Query jobs (1 day) | <200ms | <50ms |
| Aggregate query | <500ms | <100ms |
| Compression ratio | 50% | 70-90% |

### Compression Benefits

**Before compression:**
- job table (1M rows): 500 MB
- event table (10M rows): 2 GB
- Total: 2.5 GB

**After compression:**
- job table (compressed): 100 MB (80% reduction)
- event table (compressed): 400 MB (80% reduction)
- Total: 500 MB

## 🔍 Troubleshooting

### Slow Queries

```sql
-- Find slowest queries
SELECT * FROM get_slow_queries(1000);

-- Check query plan
EXPLAIN ANALYZE
SELECT * FROM job
WHERE site_id = 'fab1'
    AND inserted_at > NOW() - INTERVAL '1 day';
```

### High Memory Usage

```sql
-- Check work_mem usage
SELECT 
    query,
    calls,
    mean_exec_time,
    shared_blks_hit + shared_blks_read AS total_buffers
FROM pg_stat_statements
ORDER BY total_buffers DESC
LIMIT 10;
```

### Compression Issues

```sql
-- Find uncompressed old chunks
SELECT *
FROM timescaledb_information.chunks
WHERE NOT is_compressed
    AND range_end < NOW() - INTERVAL '48 hours';

-- Manually compress a chunk
SELECT compress_chunk(chunk_schema || '.' || chunk_name)
FROM timescaledb_information.chunks
WHERE NOT is_compressed
    AND range_end < NOW() - INTERVAL '48 hours'
LIMIT 1;
```

### Table Bloat

```sql
-- Check bloat
SELECT * FROM get_table_bloat();

-- Fix with VACUUM FULL (locks table!)
VACUUM FULL job;
-- Or use pg_repack (online)
pg_repack -d monitor -t job
```

## 📈 Monitoring Dashboard Queries

### Real-Time Metrics

```sql
-- Current activity
SELECT 
    COUNT(*) FILTER (WHERE state = 'active') AS active_queries,
    COUNT(*) FILTER (WHERE state = 'idle') AS idle_connections,
    COUNT(*) FILTER (WHERE wait_event_type IS NOT NULL) AS waiting_queries
FROM pg_stat_activity
WHERE datname = 'monitor';

-- Transactions per second
SELECT 
    xact_commit - LAG(xact_commit) OVER (ORDER BY stats_reset) AS tps
FROM pg_stat_database
WHERE datname = 'monitor';

-- Cache hit ratio
SELECT 
    ROUND(100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0), 2) AS cache_hit_ratio
FROM pg_stat_database
WHERE datname = 'monitor';
```

### Health Checks

```sql
-- Check if autovacuum is keeping up
SELECT 
    schemaname || '.' || tablename AS table,
    last_vacuum,
    last_autovacuum,
    now() - last_autovacuum AS time_since_autovacuum
FROM pg_stat_user_tables
WHERE last_autovacuum < NOW() - INTERVAL '1 day'
ORDER BY time_since_autovacuum DESC;

-- Check replication lag
SELECT 
    application_name,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes,
    now() - pg_last_xact_replay_timestamp() AS lag_time
FROM pg_stat_replication;
```

## 🎯 Best Practices

1. **Regular Maintenance**: Run maintenance script daily
2. **Monitor Continuously**: Use monitoring script hourly
3. **Compression**: Ensure compression policies are active
4. **Retention**: Adjust retention periods based on needs
5. **Indexes**: Add indexes for your specific query patterns
6. **Statistics**: Keep statistics updated with ANALYZE
7. **Backups**: Regular backups before major changes
8. **Testing**: Test optimizations in development first

## 📚 Additional Resources

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [pg_stat_statements Guide](https://www.postgresql.org/docs/current/pgstatstatements.html)

## 🔐 Security Notes

- Restrict access to monitoring functions
- Use read-only users for monitoring queries
- Secure database credentials
- Regular security updates
- Audit log access

---

**Note**: Adjust all settings based on your specific hardware and workload characteristics. Monitor performance after each change and iterate.

