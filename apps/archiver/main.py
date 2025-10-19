"""
Archiver - Export monitoring data to S3 for long-term storage.

Periodically exports job, subjob, and event data from TimescaleDB to S3.
Supports 10-year archival with efficient Parquet format.
"""
import os
import asyncio
import asyncpg
import pandas as pd
from datetime import datetime, timedelta, timezone
import boto3
from botocore.exceptions import ClientError

# Import shared utilities
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared_utils import setup_logging, get_logger, trace_async
from shared_utils import ArchiverConfig

# Configuration
config = ArchiverConfig()

# Setup logging
setup_logging(config.service_name, level=config.log_level, json_logs=config.json_logs)
logger = get_logger(__name__)


@trace_async("export_partition")
async def export_partition(table: str, start: datetime, end: datetime) -> int:
    """
    Export a time partition of data to S3.
    
    Args:
        table: Table name (job, subjob, or event)
        start: Start timestamp
        end: End timestamp
        
    Returns:
        Number of rows exported
    """
    logger.info(
        "export_partition_started",
        table=table,
        start=start.isoformat(),
        end=end.isoformat()
    )
    
    try:
        # Connect to database
        con = await asyncpg.connect(config.database_url)
        
        # Fetch data
        rows = await con.fetch(
            f"SELECT * FROM {table} WHERE inserted_at >= $1 AND inserted_at < $2",
            start,
            end
        )
        await con.close()
        
        if not rows:
            logger.info(
                "export_partition_empty",
                table=table,
                start=start.isoformat()
            )
            return 0
        
        # Convert to DataFrame
        df = pd.DataFrame([dict(r) for r in rows])
        
        # Write to local Parquet file
        tmp_path = f"/tmp/{table}-{start:%Y%m%d%H}-{end:%Y%m%d%H}.parquet"
        df.to_parquet(tmp_path, engine='pyarrow', compression='snappy')
        
        logger.info(
            "parquet_file_created",
            table=table,
            path=tmp_path,
            size_bytes=os.path.getsize(tmp_path),
            rows=len(df)
        )
        
        # Upload to S3
        s3 = boto3.client('s3')
        key = f"{config.s3_prefix}{config.site_id}/{table}/dt={start:%Y/%m/%d/%H}/part.parquet"
        
        s3.upload_file(tmp_path, config.s3_bucket, key)
        
        logger.info(
            "export_partition_completed",
            table=table,
            bucket=config.s3_bucket,
            key=key,
            rows=len(df)
        )
        
        # Clean up temp file
        os.remove(tmp_path)
        
        return len(df)
    
    except ClientError as e:
        logger.error(
            "s3_upload_failed",
            table=table,
            error=str(e),
            error_code=e.response['Error']['Code']
        )
        raise
    
    except Exception as e:
        logger.error(
            "export_partition_failed",
            table=table,
            error=str(e),
            error_type=type(e).__name__
        )
        raise


async def archive_cycle() -> None:
    """
    Run one archival cycle.
    
    Exports data from the previous hour for all tables.
    """
    now = datetime.now(timezone.utc)
    # Archive the previous complete hour
    end = now.replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=1)
    
    logger.info(
        "archive_cycle_started",
        start=start.isoformat(),
        end=end.isoformat()
    )
    
    total_rows = 0
    
    for table in ['job', 'subjob', 'event']:
        try:
            rows = await export_partition(table, start, end)
            total_rows += rows
        except Exception as e:
            logger.error(
                "table_export_failed",
                table=table,
                error=str(e)
            )
    
    logger.info(
        "archive_cycle_completed",
        total_rows=total_rows,
        duration_s=(datetime.now(timezone.utc) - now).total_seconds()
    )


async def continuous_archiver() -> None:
    """
    Continuously run archival cycles.
    
    Runs every `config.archive_interval_hours` hours.
    """
    logger.info(
        "archiver_started",
        site_id=config.site_id,
        s3_bucket=config.s3_bucket,
        s3_prefix=config.s3_prefix,
        interval_hours=config.archive_interval_hours
    )
    
    while True:
        try:
            await archive_cycle()
        except Exception as e:
            logger.error("archive_cycle_error", error=str(e))
        
        # Wait for next cycle
        sleep_seconds = config.archive_interval_hours * 3600
        logger.info("sleeping_until_next_cycle", seconds=sleep_seconds)
        await asyncio.sleep(sleep_seconds)


async def main() -> None:
    """Main entry point."""
    try:
        await continuous_archiver()
    except KeyboardInterrupt:
        logger.info("archiver_stopped_by_user")
    except Exception as e:
        logger.error("archiver_fatal_error", error=str(e))
        raise


if __name__ == '__main__':
    asyncio.run(main())
