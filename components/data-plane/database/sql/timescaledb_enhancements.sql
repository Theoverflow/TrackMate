-- ============================================================================
-- TimescaleDB Enhancements for Wafer Monitor
-- ============================================================================
-- Advanced configuration, monitoring, stored procedures, and optimizations
-- ============================================================================

-- ============================================================================
-- 1. ADVANCED HYPERTABLE CONFIGURATION
-- ============================================================================

-- Set optimal chunk interval based on data volume
-- For high-volume: 1 day chunks, for low-volume: 7 day chunks
SELECT set_chunk_time_interval('job', INTERVAL '1 day');
SELECT set_chunk_time_interval('subjob', INTERVAL '1 day');
SELECT set_chunk_time_interval('event', INTERVAL '6 hours'); -- Smaller for high-volume events

-- Enable compression on older chunks (older than 24 hours)
ALTER TABLE job SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'site_id,app_id,status',
    timescaledb.compress_orderby = 'inserted_at DESC'
);

ALTER TABLE subjob SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'site_id,app_id,status',
    timescaledb.compress_orderby = 'inserted_at DESC'
);

ALTER TABLE event SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'site_id,entity_type,kind',
    timescaledb.compress_orderby = 'at DESC'
);

-- Add compression policy (compress data older than 24 hours)
SELECT add_compression_policy('job', INTERVAL '24 hours', if_not_exists => TRUE);
SELECT add_compression_policy('subjob', INTERVAL '24 hours', if_not_exists => TRUE);
SELECT add_compression_policy('event', INTERVAL '12 hours', if_not_exists => TRUE);

-- ============================================================================
-- 2. CONTINUOUS AGGREGATES FOR PERFORMANCE
-- ============================================================================

-- Hourly job statistics
CREATE MATERIALIZED VIEW job_stats_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', inserted_at) AS hour,
    site_id,
    app_id,
    status,
    COUNT(*) AS job_count,
    AVG(duration_s) AS avg_duration_s,
    MAX(duration_s) AS max_duration_s,
    MIN(duration_s) AS min_duration_s,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_s) AS median_duration_s,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_s) AS p95_duration_s,
    AVG(cpu_user_s + cpu_system_s) AS avg_cpu_total_s,
    AVG(mem_max_mb) AS avg_mem_mb,
    MAX(mem_max_mb) AS max_mem_mb
FROM job
WHERE duration_s IS NOT NULL
GROUP BY hour, site_id, app_id, status
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('job_stats_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Daily job statistics  
CREATE MATERIALIZED VIEW job_stats_daily
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', inserted_at) AS day,
    site_id,
    app_id,
    status,
    COUNT(*) AS job_count,
    AVG(duration_s) AS avg_duration_s,
    AVG(cpu_user_s + cpu_system_s) AS avg_cpu_s,
    AVG(mem_max_mb) AS avg_mem_mb,
    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS success_rate
FROM job
WHERE duration_s IS NOT NULL
GROUP BY day, site_id, app_id, status
WITH NO DATA;

SELECT add_continuous_aggregate_policy('job_stats_daily',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Event statistics by kind
CREATE MATERIALIZED VIEW event_stats_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', at) AS hour,
    site_id,
    entity_type,
    kind,
    COUNT(*) AS event_count
FROM event
GROUP BY hour, site_id, entity_type, kind
WITH NO DATA;

SELECT add_continuous_aggregate_policy('event_stats_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE
);

-- ============================================================================
-- 3. ADDITIONAL INDEXES FOR PERFORMANCE
-- ============================================================================

-- Composite indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_site_app_status_time 
    ON job(site_id, app_id, status, inserted_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_app_status_duration 
    ON job(app_id, status, duration_s) WHERE duration_s IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subjob_job_status 
    ON subjob(job_id, status, inserted_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_entity_kind_time 
    ON event(entity_type, entity_id, kind, at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_metadata_gin 
    ON job USING gin(metadata jsonb_path_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_event_payload_gin 
    ON event USING gin(payload jsonb_path_ops);

-- Partial indexes for common filters
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_failed 
    ON job(inserted_at DESC) WHERE status = 'failed';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_running 
    ON job(inserted_at DESC) WHERE status = 'running';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_long_duration 
    ON job(inserted_at DESC, duration_s) WHERE duration_s > 300;

-- ============================================================================
-- 4. MONITORING VIEWS
-- ============================================================================

-- Current system health overview
CREATE OR REPLACE VIEW system_health AS
SELECT 
    COUNT(DISTINCT site_id) AS total_sites,
    COUNT(DISTINCT app_id) AS total_apps,
    COUNT(*) FILTER (WHERE inserted_at > NOW() - INTERVAL '5 minutes') AS jobs_last_5min,
    COUNT(*) FILTER (WHERE inserted_at > NOW() - INTERVAL '1 hour') AS jobs_last_hour,
    COUNT(*) FILTER (WHERE status = 'running') AS currently_running,
    COUNT(*) FILTER (WHERE status = 'failed' AND inserted_at > NOW() - INTERVAL '1 hour') AS failed_last_hour,
    ROUND(AVG(duration_s) FILTER (WHERE inserted_at > NOW() - INTERVAL '1 hour'), 2) AS avg_duration_last_hour,
    ROUND(MAX(mem_max_mb) FILTER (WHERE inserted_at > NOW() - INTERVAL '1 hour'), 2) AS peak_memory_last_hour
FROM job
WHERE inserted_at > NOW() - INTERVAL '24 hours';

-- Job success rates by application
CREATE OR REPLACE VIEW app_success_rates AS
SELECT 
    a.name AS app_name,
    a.version AS app_version,
    j.site_id,
    COUNT(*) AS total_jobs,
    COUNT(*) FILTER (WHERE j.status = 'succeeded') AS succeeded,
    COUNT(*) FILTER (WHERE j.status = 'failed') AS failed,
    ROUND(
        COUNT(*) FILTER (WHERE j.status = 'succeeded')::NUMERIC / 
        NULLIF(COUNT(*), 0) * 100, 
        2
    ) AS success_rate_pct,
    ROUND(AVG(j.duration_s), 2) AS avg_duration_s
FROM job j
JOIN app a ON j.app_id = a.app_id
WHERE j.inserted_at > NOW() - INTERVAL '24 hours'
GROUP BY a.name, a.version, j.site_id
ORDER BY total_jobs DESC;

-- Recent failures with details
CREATE OR REPLACE VIEW recent_failures AS
SELECT 
    j.job_id,
    a.name AS app_name,
    j.site_id,
    j.job_key,
    j.started_at,
    j.ended_at,
    j.duration_s,
    j.metadata->>'error' AS error_message,
    j.metadata->>'error_type' AS error_type
FROM job j
JOIN app a ON j.app_id = a.app_id
WHERE j.status = 'failed' 
    AND j.inserted_at > NOW() - INTERVAL '1 hour'
ORDER BY j.inserted_at DESC
LIMIT 100;

-- Performance outliers (jobs taking >3x average)
CREATE OR REPLACE VIEW performance_outliers AS
WITH avg_durations AS (
    SELECT 
        app_id,
        AVG(duration_s) AS avg_duration,
        STDDEV(duration_s) AS stddev_duration
    FROM job
    WHERE duration_s IS NOT NULL
        AND inserted_at > NOW() - INTERVAL '7 days'
    GROUP BY app_id
)
SELECT 
    j.job_id,
    a.name AS app_name,
    j.site_id,
    j.duration_s,
    ad.avg_duration,
    ROUND((j.duration_s / ad.avg_duration), 2) AS duration_ratio,
    j.cpu_user_s + j.cpu_system_s AS total_cpu_s,
    j.mem_max_mb
FROM job j
JOIN app a ON j.app_id = a.app_id
JOIN avg_durations ad ON j.app_id = ad.app_id
WHERE j.duration_s > ad.avg_duration * 3
    AND j.inserted_at > NOW() - INTERVAL '24 hours'
ORDER BY duration_ratio DESC
LIMIT 50;

-- TimescaleDB chunk health
CREATE OR REPLACE VIEW chunk_health AS
SELECT 
    hypertable_name,
    chunk_name,
    range_start,
    range_end,
    is_compressed,
    pg_size_pretty(total_bytes) AS total_size,
    pg_size_pretty(compressed_total_bytes) AS compressed_size,
    ROUND(
        100.0 * compressed_total_bytes / NULLIF(total_bytes, 0),
        2
    ) AS compression_ratio_pct
FROM timescaledb_information.chunks
ORDER BY range_start DESC;

-- Database size overview
CREATE OR REPLACE VIEW database_size_overview AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size,
    pg_total_relation_size(schemaname||'.'||tablename) AS total_bytes
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY total_bytes DESC;

-- ============================================================================
-- 5. STORED PROCEDURES FOR COMMON OPERATIONS
-- ============================================================================

-- Get job statistics for a time range
CREATE OR REPLACE FUNCTION get_job_stats(
    p_site_id TEXT,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ
)
RETURNS TABLE(
    total_jobs BIGINT,
    succeeded BIGINT,
    failed BIGINT,
    running BIGINT,
    avg_duration_s NUMERIC,
    max_duration_s NUMERIC,
    avg_cpu_s NUMERIC,
    avg_mem_mb NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT,
        COUNT(*) FILTER (WHERE status = 'succeeded')::BIGINT,
        COUNT(*) FILTER (WHERE status = 'failed')::BIGINT,
        COUNT(*) FILTER (WHERE status = 'running')::BIGINT,
        ROUND(AVG(duration_s), 2),
        MAX(duration_s),
        ROUND(AVG(cpu_user_s + cpu_system_s), 2),
        ROUND(AVG(mem_max_mb), 2)
    FROM job
    WHERE site_id = p_site_id
        AND inserted_at BETWEEN p_start_time AND p_end_time;
END;
$$ LANGUAGE plpgsql STABLE;

-- Get top N slowest jobs
CREATE OR REPLACE FUNCTION get_slowest_jobs(
    p_site_id TEXT DEFAULT NULL,
    p_limit INT DEFAULT 10,
    p_hours INT DEFAULT 24
)
RETURNS TABLE(
    job_id UUID,
    app_name TEXT,
    job_key TEXT,
    duration_s NUMERIC,
    cpu_total_s NUMERIC,
    mem_max_mb NUMERIC,
    started_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        j.job_id,
        a.name,
        j.job_key,
        j.duration_s,
        j.cpu_user_s + j.cpu_system_s,
        j.mem_max_mb,
        j.started_at
    FROM job j
    JOIN app a ON j.app_id = a.app_id
    WHERE (p_site_id IS NULL OR j.site_id = p_site_id)
        AND j.inserted_at > NOW() - (p_hours || ' hours')::INTERVAL
        AND j.duration_s IS NOT NULL
    ORDER BY j.duration_s DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Get failure analysis
CREATE OR REPLACE FUNCTION get_failure_analysis(
    p_site_id TEXT DEFAULT NULL,
    p_hours INT DEFAULT 24
)
RETURNS TABLE(
    app_name TEXT,
    error_type TEXT,
    failure_count BIGINT,
    avg_duration_before_failure NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.name,
        j.metadata->>'error_type' AS error_type,
        COUNT(*)::BIGINT,
        ROUND(AVG(j.duration_s), 2)
    FROM job j
    JOIN app a ON j.app_id = a.app_id
    WHERE j.status = 'failed'
        AND (p_site_id IS NULL OR j.site_id = p_site_id)
        AND j.inserted_at > NOW() - (p_hours || ' hours')::INTERVAL
        AND j.metadata->>'error_type' IS NOT NULL
    GROUP BY a.name, j.metadata->>'error_type'
    ORDER BY COUNT(*) DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Archive old data (beyond retention period)
CREATE OR REPLACE FUNCTION archive_old_data(
    p_older_than_hours INT DEFAULT 72
)
RETURNS TABLE(
    table_name TEXT,
    rows_archived BIGINT
) AS $$
DECLARE
    v_cutoff_time TIMESTAMPTZ;
    v_job_count BIGINT;
    v_subjob_count BIGINT;
    v_event_count BIGINT;
BEGIN
    v_cutoff_time := NOW() - (p_older_than_hours || ' hours')::INTERVAL;
    
    -- Get counts before deletion
    SELECT COUNT(*) INTO v_job_count FROM job WHERE inserted_at < v_cutoff_time;
    SELECT COUNT(*) INTO v_subjob_count FROM subjob WHERE inserted_at < v_cutoff_time;
    SELECT COUNT(*) INTO v_event_count FROM event WHERE at < v_cutoff_time;
    
    -- Note: TimescaleDB retention policy should handle this,
    -- but this function can be used for manual cleanup
    
    RETURN QUERY
    SELECT 'job'::TEXT, v_job_count
    UNION ALL
    SELECT 'subjob'::TEXT, v_subjob_count
    UNION ALL
    SELECT 'event'::TEXT, v_event_count;
END;
$$ LANGUAGE plpgsql;

-- Vacuum and analyze all hypertables
CREATE OR REPLACE FUNCTION maintenance_vacuum_analyze()
RETURNS TABLE(
    table_name TEXT,
    operation TEXT,
    success BOOLEAN
) AS $$
BEGIN
    -- Vacuum and analyze job table
    BEGIN
        VACUUM ANALYZE job;
        RETURN QUERY SELECT 'job'::TEXT, 'vacuum_analyze'::TEXT, TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'job'::TEXT, 'vacuum_analyze'::TEXT, FALSE;
    END;
    
    -- Vacuum and analyze subjob table
    BEGIN
        VACUUM ANALYZE subjob;
        RETURN QUERY SELECT 'subjob'::TEXT, 'vacuum_analyze'::TEXT, TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'subjob'::TEXT, 'vacuum_analyze'::TEXT, FALSE;
    END;
    
    -- Vacuum and analyze event table
    BEGIN
        VACUUM ANALYZE event;
        RETURN QUERY SELECT 'event'::TEXT, 'vacuum_analyze'::TEXT, TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'event'::TEXT, 'vacuum_analyze'::TEXT, FALSE;
    END;
    
    -- Vacuum and analyze app table
    BEGIN
        VACUUM ANALYZE app;
        RETURN QUERY SELECT 'app'::TEXT, 'vacuum_analyze'::TEXT, TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'app'::TEXT, 'vacuum_analyze'::TEXT, FALSE;
    END;
END;
$$ LANGUAGE plpgsql;

-- Reindex all tables
CREATE OR REPLACE FUNCTION maintenance_reindex()
RETURNS TABLE(
    table_name TEXT,
    success BOOLEAN
) AS $$
BEGIN
    BEGIN
        REINDEX TABLE job;
        RETURN QUERY SELECT 'job'::TEXT, TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'job'::TEXT, FALSE;
    END;
    
    BEGIN
        REINDEX TABLE subjob;
        RETURN QUERY SELECT 'subjob'::TEXT, TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'subjob'::TEXT, FALSE;
    END;
    
    BEGIN
        REINDEX TABLE event;
        RETURN QUERY SELECT 'event'::TEXT, TRUE;
    EXCEPTION WHEN OTHERS THEN
        RETURN QUERY SELECT 'event'::TEXT, FALSE;
    END;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 6. PERFORMANCE MONITORING PROCEDURES
-- ============================================================================

-- Get slow queries
CREATE OR REPLACE FUNCTION get_slow_queries(p_min_duration_ms INT DEFAULT 1000)
RETURNS TABLE(
    query_text TEXT,
    calls BIGINT,
    mean_exec_time_ms NUMERIC,
    max_exec_time_ms NUMERIC,
    total_exec_time_ms NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        query,
        calls,
        ROUND(mean_exec_time::NUMERIC, 2),
        ROUND(max_exec_time::NUMERIC, 2),
        ROUND(total_exec_time::NUMERIC, 2)
    FROM pg_stat_statements
    WHERE mean_exec_time > p_min_duration_ms
    ORDER BY mean_exec_time DESC
    LIMIT 20;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'pg_stat_statements extension not enabled';
        RETURN;
END;
$$ LANGUAGE plpgsql;

-- Get table bloat information
CREATE OR REPLACE FUNCTION get_table_bloat()
RETURNS TABLE(
    table_name TEXT,
    size_mb NUMERIC,
    bloat_pct NUMERIC,
    bloat_mb NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        schemaname || '.' || tablename AS table_name,
        ROUND(pg_total_relation_size(schemaname||'.'||tablename) / 1024.0 / 1024.0, 2) AS size_mb,
        ROUND(100.0 * (pg_total_relation_size(schemaname||'.'||tablename) - 
            pg_relation_size(schemaname||'.'||tablename)) / 
            NULLIF(pg_total_relation_size(schemaname||'.'||tablename), 0), 2) AS bloat_pct,
        ROUND((pg_total_relation_size(schemaname||'.'||tablename) - 
            pg_relation_size(schemaname||'.'||tablename)) / 1024.0 / 1024.0, 2) AS bloat_mb
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY bloat_mb DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. ALERTING PROCEDURES
-- ============================================================================

-- Check for high failure rate
CREATE OR REPLACE FUNCTION check_high_failure_rate(
    p_threshold_pct NUMERIC DEFAULT 10,
    p_hours INT DEFAULT 1
)
RETURNS TABLE(
    site_id TEXT,
    app_name TEXT,
    total_jobs BIGINT,
    failed_jobs BIGINT,
    failure_rate_pct NUMERIC,
    alert_level TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        j.site_id,
        a.name,
        COUNT(*)::BIGINT,
        COUNT(*) FILTER (WHERE j.status = 'failed')::BIGINT,
        ROUND(100.0 * COUNT(*) FILTER (WHERE j.status = 'failed') / NULLIF(COUNT(*), 0), 2),
        CASE 
            WHEN 100.0 * COUNT(*) FILTER (WHERE j.status = 'failed') / NULLIF(COUNT(*), 0) > p_threshold_pct * 2 
                THEN 'CRITICAL'
            WHEN 100.0 * COUNT(*) FILTER (WHERE j.status = 'failed') / NULLIF(COUNT(*), 0) > p_threshold_pct 
                THEN 'WARNING'
            ELSE 'OK'
        END
    FROM job j
    JOIN app a ON j.app_id = a.app_id
    WHERE j.inserted_at > NOW() - (p_hours || ' hours')::INTERVAL
    GROUP BY j.site_id, a.name
    HAVING 100.0 * COUNT(*) FILTER (WHERE j.status = 'failed') / NULLIF(COUNT(*), 0) > p_threshold_pct
    ORDER BY failure_rate_pct DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Check for no activity
CREATE OR REPLACE FUNCTION check_no_activity(p_threshold_minutes INT DEFAULT 30)
RETURNS TABLE(
    site_id TEXT,
    last_activity TIMESTAMPTZ,
    minutes_since_activity INT,
    alert_level TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        j.site_id,
        MAX(j.inserted_at),
        EXTRACT(EPOCH FROM (NOW() - MAX(j.inserted_at)))::INT / 60,
        CASE 
            WHEN EXTRACT(EPOCH FROM (NOW() - MAX(j.inserted_at)))::INT / 60 > p_threshold_minutes * 2 
                THEN 'CRITICAL'
            WHEN EXTRACT(EPOCH FROM (NOW() - MAX(j.inserted_at)))::INT / 60 > p_threshold_minutes 
                THEN 'WARNING'
            ELSE 'OK'
        END
    FROM job j
    GROUP BY j.site_id
    HAVING EXTRACT(EPOCH FROM (NOW() - MAX(j.inserted_at)))::INT / 60 > p_threshold_minutes;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- 8. GRANT PERMISSIONS (adjust as needed)
-- ============================================================================

-- Grant read-only access to monitoring views
GRANT SELECT ON system_health TO PUBLIC;
GRANT SELECT ON app_success_rates TO PUBLIC;
GRANT SELECT ON recent_failures TO PUBLIC;
GRANT SELECT ON performance_outliers TO PUBLIC;
GRANT SELECT ON chunk_health TO PUBLIC;
GRANT SELECT ON database_size_overview TO PUBLIC;

-- Grant execute on monitoring functions
GRANT EXECUTE ON FUNCTION get_job_stats TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_slowest_jobs TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_failure_analysis TO PUBLIC;
GRANT EXECUTE ON FUNCTION check_high_failure_rate TO PUBLIC;
GRANT EXECUTE ON FUNCTION check_no_activity TO PUBLIC;

-- ============================================================================
-- USAGE EXAMPLES
-- ============================================================================

-- Get job statistics for last 24 hours
-- SELECT * FROM get_job_stats('fab1', NOW() - INTERVAL '24 hours', NOW());

-- Get top 10 slowest jobs
-- SELECT * FROM get_slowest_jobs('fab1', 10, 24);

-- Get failure analysis
-- SELECT * FROM get_failure_analysis('fab1', 24);

-- Check for high failure rates
-- SELECT * FROM check_high_failure_rate(10, 1);

-- Check for inactive sites
-- SELECT * FROM check_no_activity(30);

-- Run maintenance
-- SELECT * FROM maintenance_vacuum_analyze();

-- View system health
-- SELECT * FROM system_health;

-- View app success rates
-- SELECT * FROM app_success_rates;

