#!/usr/bin/env python3
"""
TimescaleDB Monitoring Script

Checks database health, performance metrics, and alerts on issues.
"""
import os
import sys
import asyncpg
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Import shared utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../apps'))
from shared_utils import setup_logging, get_logger

setup_logging('timescaledb-monitor', level='INFO')
logger = get_logger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/monitor')


class TimescaleDBMonitor:
    """Monitor TimescaleDB health and performance."""
    
    def __init__(self, database_url: str):
        """Initialize monitor."""
        self.database_url = database_url
        self.conn: asyncpg.Connection = None
    
    async def connect(self) -> None:
        """Connect to database."""
        self.conn = await asyncpg.connect(self.database_url)
        logger.info("connected_to_database")
    
    async def close(self) -> None:
        """Close database connection."""
        if self.conn:
            await self.conn.close()
        logger.info("database_connection_closed")
    
    async def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        query = "SELECT * FROM system_health"
        result = await self.conn.fetchrow(query)
        
        health = dict(result) if result else {}
        logger.info("system_health_checked", **health)
        
        return health
    
    async def check_high_failure_rate(self, threshold_pct: float = 10.0) -> List[Dict]:
        """Check for high failure rates."""
        query = "SELECT * FROM check_high_failure_rate($1, 1)"
        results = await self.conn.fetch(query, threshold_pct)
        
        alerts = [dict(r) for r in results]
        
        if alerts:
            for alert in alerts:
                logger.warning(
                    "high_failure_rate_detected",
                    site_id=alert['site_id'],
                    app_name=alert['app_name'],
                    failure_rate_pct=alert['failure_rate_pct'],
                    alert_level=alert['alert_level']
                )
        
        return alerts
    
    async def check_no_activity(self, threshold_minutes: int = 30) -> List[Dict]:
        """Check for sites with no recent activity."""
        query = "SELECT * FROM check_no_activity($1)"
        results = await self.conn.fetch(query, threshold_minutes)
        
        alerts = [dict(r) for r in results]
        
        if alerts:
            for alert in alerts:
                logger.warning(
                    "no_activity_detected",
                    site_id=alert['site_id'],
                    minutes_since_activity=alert['minutes_since_activity'],
                    alert_level=alert['alert_level']
                )
        
        return alerts
    
    async def check_chunk_compression(self) -> Dict[str, Any]:
        """Check chunk compression status."""
        query = """
        SELECT 
            hypertable_name,
            COUNT(*) AS total_chunks,
            COUNT(*) FILTER (WHERE is_compressed) AS compressed_chunks,
            SUM(total_bytes) AS total_bytes,
            SUM(compressed_total_bytes) AS compressed_bytes,
            ROUND(100.0 * SUM(compressed_total_bytes) / NULLIF(SUM(total_bytes), 0), 2) AS compression_ratio_pct
        FROM timescaledb_information.chunks
        GROUP BY hypertable_name
        """
        results = await self.conn.fetch(query)
        
        compression_status = {}
        for row in results:
            hypertable = row['hypertable_name']
            compression_status[hypertable] = {
                'total_chunks': row['total_chunks'],
                'compressed_chunks': row['compressed_chunks'],
                'compression_ratio_pct': float(row['compression_ratio_pct']) if row['compression_ratio_pct'] else 0,
                'total_gb': round(row['total_bytes'] / (1024**3), 2),
                'compressed_gb': round(row['compressed_bytes'] / (1024**3), 2) if row['compressed_bytes'] else 0
            }
            
            logger.info(
                "chunk_compression_status",
                hypertable=hypertable,
                **compression_status[hypertable]
            )
        
        return compression_status
    
    async def check_database_size(self) -> Dict[str, Any]:
        """Check database and table sizes."""
        query = "SELECT * FROM database_size_overview ORDER BY total_bytes DESC"
        results = await self.conn.fetch(query)
        
        sizes = {}
        total_size = 0
        
        for row in results:
            table = row['tablename']
            sizes[table] = {
                'total_size': row['total_size'],
                'table_size': row['table_size'],
                'indexes_size': row['indexes_size']
            }
            total_size += row['total_bytes']
        
        total_size_gb = round(total_size / (1024**3), 2)
        logger.info("database_size_checked", total_size_gb=total_size_gb)
        
        return {'tables': sizes, 'total_size_gb': total_size_gb}
    
    async def check_slow_queries(self, min_duration_ms: int = 1000) -> List[Dict]:
        """Check for slow queries."""
        try:
            query = "SELECT * FROM get_slow_queries($1)"
            results = await self.conn.fetch(query, min_duration_ms)
            
            slow_queries = []
            for row in results:
                slow_queries.append({
                    'query': row['query_text'][:100],  # Truncate for logging
                    'calls': row['calls'],
                    'mean_time_ms': float(row['mean_exec_time_ms']),
                    'max_time_ms': float(row['max_exec_time_ms'])
                })
                
                logger.warning(
                    "slow_query_detected",
                    mean_time_ms=float(row['mean_exec_time_ms']),
                    calls=row['calls']
                )
            
            return slow_queries
        except Exception as e:
            logger.info("slow_query_check_skipped", reason=str(e))
            return []
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        # Connection stats
        conn_query = """
        SELECT 
            COUNT(*) AS total_connections,
            COUNT(*) FILTER (WHERE state = 'active') AS active_connections,
            COUNT(*) FILTER (WHERE state = 'idle') AS idle_connections
        FROM pg_stat_activity
        WHERE datname = current_database()
        """
        conn_stats = await self.conn.fetchrow(conn_query)
        
        # Transaction stats
        txn_query = """
        SELECT 
            xact_commit,
            xact_rollback,
            blks_read,
            blks_hit,
            ROUND(100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0), 2) AS cache_hit_ratio
        FROM pg_stat_database
        WHERE datname = current_database()
        """
        txn_stats = await self.conn.fetchrow(txn_query)
        
        metrics = {
            'connections': dict(conn_stats),
            'transactions': {
                'commits': txn_stats['xact_commit'],
                'rollbacks': txn_stats['xact_rollback'],
                'cache_hit_ratio_pct': float(txn_stats['cache_hit_ratio']) if txn_stats['cache_hit_ratio'] else 0
            }
        }
        
        logger.info("performance_metrics_collected", **metrics)
        
        return metrics
    
    async def run_health_check(self) -> Dict[str, Any]:
        """Run complete health check."""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy',
            'checks': {}
        }
        
        try:
            # System health
            system_health = await self.check_system_health()
            results['checks']['system_health'] = {
                'status': 'ok',
                'data': system_health
            }
            
            # High failure rates
            failure_alerts = await self.check_high_failure_rate()
            if failure_alerts:
                results['status'] = 'degraded'
                results['checks']['failure_rate'] = {
                    'status': 'alert',
                    'alerts': failure_alerts
                }
            else:
                results['checks']['failure_rate'] = {'status': 'ok'}
            
            # No activity
            activity_alerts = await self.check_no_activity()
            if activity_alerts:
                results['status'] = 'degraded'
                results['checks']['activity'] = {
                    'status': 'alert',
                    'alerts': activity_alerts
                }
            else:
                results['checks']['activity'] = {'status': 'ok'}
            
            # Compression
            compression = await self.check_chunk_compression()
            results['checks']['compression'] = {
                'status': 'ok',
                'data': compression
            }
            
            # Database size
            size_info = await self.check_database_size()
            results['checks']['database_size'] = {
                'status': 'ok',
                'data': size_info
            }
            
            # Performance metrics
            perf_metrics = await self.get_performance_metrics()
            results['checks']['performance'] = {
                'status': 'ok',
                'data': perf_metrics
            }
            
            # Slow queries
            slow_queries = await self.check_slow_queries()
            if slow_queries:
                results['checks']['slow_queries'] = {
                    'status': 'warning',
                    'count': len(slow_queries),
                    'queries': slow_queries[:5]  # Top 5
                }
        
        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            results['status'] = 'error'
            results['error'] = str(e)
        
        return results


async def main():
    """Main entry point."""
    monitor = TimescaleDBMonitor(DATABASE_URL)
    
    try:
        await monitor.connect()
        
        # Run health check
        results = await monitor.run_health_check()
        
        # Print summary
        print(f"\n{'='*70}")
        print(f"TimescaleDB Health Check - {results['timestamp']}")
        print(f"{'='*70}")
        print(f"Overall Status: {results['status'].upper()}")
        print(f"{'='*70}\n")
        
        # Print each check
        for check_name, check_data in results['checks'].items():
            status_emoji = {
                'ok': '✅',
                'warning': '⚠️',
                'alert': '🚨',
                'error': '❌'
            }.get(check_data['status'], '❓')
            
            print(f"{status_emoji} {check_name.replace('_', ' ').title()}: {check_data['status'].upper()}")
            
            if 'alerts' in check_data:
                for alert in check_data['alerts']:
                    print(f"   - {alert}")
        
        print(f"\n{'='*70}\n")
        
        # Exit with appropriate code
        if results['status'] == 'healthy':
            sys.exit(0)
        elif results['status'] == 'degraded':
            sys.exit(1)
        else:
            sys.exit(2)
    
    finally:
        await monitor.close()


if __name__ == '__main__':
    asyncio.run(main())

