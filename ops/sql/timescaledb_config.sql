-- ============================================================================
-- TimescaleDB PostgreSQL Configuration Recommendations
-- ============================================================================
-- Optimal settings for wafer monitoring workload
-- Apply these settings in postgresql.conf or via ALTER SYSTEM
-- ============================================================================

-- ============================================================================
-- MEMORY SETTINGS
-- ============================================================================

-- Shared buffers: 25% of total RAM (for dedicated server)
-- For 16GB RAM: 4GB
-- For 32GB RAM: 8GB
ALTER SYSTEM SET shared_buffers = '4GB';

-- Effective cache size: 50-75% of total RAM
-- This tells PostgreSQL how much memory is available for caching
ALTER SYSTEM SET effective_cache_size = '12GB';

-- Work memory: For sorts and hash tables
-- Calculate as: (Total RAM - shared_buffers) / (max_connections * 3)
-- For 16GB RAM, 100 connections: (12GB) / (100 * 3) ≈ 40MB
ALTER SYSTEM SET work_mem = '40MB';

-- Maintenance work memory: For VACUUM, CREATE INDEX, etc.
-- Set to 5-10% of RAM
ALTER SYSTEM SET maintenance_work_mem = '1GB';

-- ============================================================================
-- QUERY PLANNER SETTINGS
-- ============================================================================

-- Random page cost: Lower for SSD storage
ALTER SYSTEM SET random_page_cost = 1.1;

-- Effective IO concurrency: Number of concurrent disk I/O operations
-- For SSD: 200, for HDD: 2
ALTER SYSTEM SET effective_io_concurrency = 200;

-- Default statistics target: Higher = better query plans
ALTER SYSTEM SET default_statistics_target = 100;

-- ============================================================================
-- WRITE-AHEAD LOG (WAL) SETTINGS
-- ============================================================================

-- WAL level: replica (needed for replication and TimescaleDB)
ALTER SYSTEM SET wal_level = 'replica';

-- WAL buffers: Typically 16MB is good
ALTER SYSTEM SET wal_buffers = '16MB';

-- Checkpoint settings for better write performance
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;

-- WAL compression
ALTER SYSTEM SET wal_compression = 'on';

-- ============================================================================
-- CONNECTION SETTINGS
-- ============================================================================

-- Maximum connections
ALTER SYSTEM SET max_connections = 100;

-- Connection timeout
ALTER SYSTEM SET statement_timeout = '30s';
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';

-- ============================================================================
-- AUTOVACUUM SETTINGS
-- ============================================================================

-- Enable autovacuum
ALTER SYSTEM SET autovacuum = 'on';

-- More aggressive autovacuum for high-write workloads
ALTER SYSTEM SET autovacuum_max_workers = 4;
ALTER SYSTEM SET autovacuum_naptime = '10s';

-- Vacuum cost settings (lower = more aggressive)
ALTER SYSTEM SET autovacuum_vacuum_cost_delay = '2ms';
ALTER SYSTEM SET autovacuum_vacuum_cost_limit = 1000;

-- Thresholds for triggering autovacuum
ALTER SYSTEM SET autovacuum_vacuum_threshold = 50;
ALTER SYSTEM SET autovacuum_vacuum_scale_factor = 0.1;
ALTER SYSTEM SET autovacuum_analyze_threshold = 50;
ALTER SYSTEM SET autovacuum_analyze_scale_factor = 0.05;

-- ============================================================================
-- LOGGING SETTINGS
-- ============================================================================

-- What to log
ALTER SYSTEM SET log_min_duration_statement = '1000ms'; -- Log slow queries
ALTER SYSTEM SET log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h ';
ALTER SYSTEM SET log_checkpoints = 'on';
ALTER SYSTEM SET log_connections = 'on';
ALTER SYSTEM SET log_disconnections = 'on';
ALTER SYSTEM SET log_lock_waits = 'on';
ALTER SYSTEM SET log_temp_files = 0; -- Log all temp files
ALTER SYSTEM SET log_autovacuum_min_duration = '0'; -- Log all autovacuum operations

-- Log destination
ALTER SYSTEM SET logging_collector = 'on';
ALTER SYSTEM SET log_directory = 'log';
ALTER SYSTEM SET log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log';
ALTER SYSTEM SET log_rotation_age = '1d';
ALTER SYSTEM SET log_rotation_size = '100MB';

-- ============================================================================
-- TIMESCALEDB-SPECIFIC SETTINGS
-- ============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- TimescaleDB tuning
ALTER SYSTEM SET timescaledb.max_background_workers = 8;

-- Parallelize chunk operations
ALTER SYSTEM SET timescaledb.max_parallel_workers_per_gather = 4;

-- Enable distributed transactions (if using distributed hypertables)
ALTER SYSTEM SET timescaledb.enable_2pc = 'on';

-- ============================================================================
-- PERFORMANCE MONITORING EXTENSIONS
-- ============================================================================

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
ALTER SYSTEM SET pg_stat_statements.track = 'all';
ALTER SYSTEM SET pg_stat_statements.max = 10000;

-- Enable auto_explain to log slow query execution plans
CREATE EXTENSION IF NOT EXISTS auto_explain;
ALTER SYSTEM SET auto_explain.log_min_duration = '1s';
ALTER SYSTEM SET auto_explain.log_analyze = 'on';
ALTER SYSTEM SET auto_explain.log_buffers = 'on';
ALTER SYSTEM SET auto_explain.log_timing = 'on';
ALTER SYSTEM SET auto_explain.log_triggers = 'on';
ALTER SYSTEM SET auto_explain.log_verbose = 'on';
ALTER SYSTEM SET auto_explain.log_nested_statements = 'on';

-- ============================================================================
-- PARALLEL QUERY SETTINGS
-- ============================================================================

-- Enable parallel query execution
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;
ALTER SYSTEM SET max_worker_processes = 8;

-- Parallel execution thresholds
ALTER SYSTEM SET parallel_tuple_cost = 0.1;
ALTER SYSTEM SET parallel_setup_cost = 1000;
ALTER SYSTEM SET min_parallel_table_scan_size = '8MB';
ALTER SYSTEM SET min_parallel_index_scan_size = '512kB';

-- ============================================================================
-- JIT COMPILATION (PostgreSQL 11+)
-- ============================================================================

-- Enable JIT for complex queries (can improve performance)
ALTER SYSTEM SET jit = 'on';
ALTER SYSTEM SET jit_above_cost = 100000;
ALTER SYSTEM SET jit_inline_above_cost = 500000;
ALTER SYSTEM SET jit_optimize_above_cost = 500000;

-- ============================================================================
-- RELOAD CONFIGURATION
-- ============================================================================

-- After applying settings, reload configuration
-- Some settings require a restart
SELECT pg_reload_conf();

-- ============================================================================
-- NOTES
-- ============================================================================

-- 1. Adjust memory settings based on your server's total RAM
-- 2. For dedicated PostgreSQL servers, you can be more aggressive
-- 3. Monitor performance with pg_stat_statements and adjust as needed
-- 4. Test changes in development before applying to production
-- 5. Some settings require PostgreSQL restart: 
--    sudo systemctl restart postgresql
-- 6. Monitor logs after changes: tail -f /var/log/postgresql/postgresql-*.log

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check current settings
-- SELECT name, setting, unit, context FROM pg_settings WHERE name IN (
--     'shared_buffers', 'effective_cache_size', 'work_mem', 
--     'maintenance_work_mem', 'max_connections', 'random_page_cost'
-- );

-- Check if restart is required
-- SELECT name, setting, pending_restart 
-- FROM pg_settings 
-- WHERE pending_restart = true;

