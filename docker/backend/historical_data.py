"""
Historical Data API
Time-series metrics storage and retrieval
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncpg

logger = logging.getLogger(__name__)


class TimeRange:
    """Predefined time ranges for queries"""

    LAST_HOUR = timedelta(hours=1)
    LAST_6_HOURS = timedelta(hours=6)
    LAST_24_HOURS = timedelta(days=1)
    LAST_7_DAYS = timedelta(days=7)
    LAST_30_DAYS = timedelta(days=30)
    LAST_90_DAYS = timedelta(days=90)

    @staticmethod
    def from_string(range_str: str) -> timedelta:
        """Convert string to timedelta"""
        mapping = {
            '1h': TimeRange.LAST_HOUR,
            '6h': TimeRange.LAST_6_HOURS,
            '24h': TimeRange.LAST_24_HOURS,
            '7d': TimeRange.LAST_7_DAYS,
            '30d': TimeRange.LAST_30_DAYS,
            '90d': TimeRange.LAST_90_DAYS
        }
        return mapping.get(range_str, TimeRange.LAST_24_HOURS)


class AggregationInterval:
    """Aggregation intervals for time-series data"""

    RAW = None  # No aggregation
    MINUTE = '1 minute'
    FIVE_MINUTES = '5 minutes'
    FIFTEEN_MINUTES = '15 minutes'
    HOUR = '1 hour'
    DAY = '1 day'

    @staticmethod
    def auto_select(time_range: timedelta) -> str:
        """Automatically select appropriate interval based on time range"""
        hours = time_range.total_seconds() / 3600

        if hours <= 1:
            return AggregationInterval.MINUTE
        elif hours <= 6:
            return AggregationInterval.FIVE_MINUTES
        elif hours <= 24:
            return AggregationInterval.FIFTEEN_MINUTES
        elif hours <= 168:  # 7 days
            return AggregationInterval.HOUR
        else:
            return AggregationInterval.DAY


class HistoricalDataService:
    """Service for querying historical metrics data"""

    def __init__(self, db_pool):
        self.db = db_pool
        self.retention_days = int(os.getenv('METRICS_RETENTION_DAYS', '90'))

    async def get_vm_metrics_history(
        self,
        hostname: str,
        time_range: str = '24h',
        interval: Optional[str] = None
    ) -> Dict:
        """Get historical metrics for a VM"""

        # Parse time range
        range_delta = TimeRange.from_string(time_range)
        end_time = datetime.now()
        start_time = end_time - range_delta

        # Auto-select interval if not specified
        if not interval:
            interval = AggregationInterval.auto_select(range_delta)

        async with self.db.acquire() as conn:
            if interval:
                # Aggregated data
                query = """
                    SELECT
                        DATE_TRUNC($1, timestamp) AS bucket,
                        AVG(cpu_usage) AS avg_cpu,
                        MAX(cpu_usage) AS max_cpu,
                        MIN(cpu_usage) AS min_cpu,
                        AVG(memory_usage) AS avg_memory,
                        MAX(memory_usage) AS max_memory,
                        MIN(memory_usage) AS min_memory,
                        AVG(disk_usage) AS avg_disk,
                        MAX(disk_usage) AS max_disk,
                        MIN(disk_usage) AS min_disk,
                        COUNT(*) AS sample_count
                    FROM vm_metrics_history
                    WHERE hostname = $2
                      AND timestamp BETWEEN $3 AND $4
                    GROUP BY bucket
                    ORDER BY bucket
                """
                rows = await conn.fetch(query, interval, hostname, start_time, end_time)
            else:
                # Raw data
                query = """
                    SELECT
                        timestamp AS bucket,
                        cpu_usage AS avg_cpu,
                        cpu_usage AS max_cpu,
                        cpu_usage AS min_cpu,
                        memory_usage AS avg_memory,
                        memory_usage AS max_memory,
                        memory_usage AS min_memory,
                        disk_usage AS avg_disk,
                        disk_usage AS max_disk,
                        disk_usage AS min_disk,
                        1 AS sample_count
                    FROM vm_metrics_history
                    WHERE hostname = $1
                      AND timestamp BETWEEN $2 AND $3
                    ORDER BY timestamp
                """
                rows = await conn.fetch(query, hostname, start_time, end_time)

            # Format data for charts
            timestamps = []
            cpu_data = []
            memory_data = []
            disk_data = []

            for row in rows:
                timestamps.append(row['bucket'].isoformat())
                cpu_data.append({
                    'avg': float(row['avg_cpu']) if row['avg_cpu'] else None,
                    'max': float(row['max_cpu']) if row['max_cpu'] else None,
                    'min': float(row['min_cpu']) if row['min_cpu'] else None
                })
                memory_data.append({
                    'avg': float(row['avg_memory']) if row['avg_memory'] else None,
                    'max': float(row['max_memory']) if row['max_memory'] else None,
                    'min': float(row['min_memory']) if row['min_memory'] else None
                })
                disk_data.append({
                    'avg': float(row['avg_disk']) if row['avg_disk'] else None,
                    'max': float(row['max_disk']) if row['max_disk'] else None,
                    'min': float(row['min_disk']) if row['min_disk'] else None
                })

            return {
                'hostname': hostname,
                'time_range': time_range,
                'interval': interval or 'raw',
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'data_points': len(timestamps),
                'timestamps': timestamps,
                'metrics': {
                    'cpu': cpu_data,
                    'memory': memory_data,
                    'disk': disk_data
                }
            }

    async def get_fleet_metrics_summary(
        self,
        time_range: str = '24h'
    ) -> Dict:
        """Get aggregated metrics for entire fleet"""

        range_delta = TimeRange.from_string(time_range)
        end_time = datetime.now()
        start_time = end_time - range_delta

        async with self.db.acquire() as conn:
            # Average metrics across fleet
            query = """
                SELECT
                    DATE_TRUNC('hour', timestamp) AS hour,
                    AVG(cpu_usage) AS avg_cpu,
                    AVG(memory_usage) AS avg_memory,
                    AVG(disk_usage) AS avg_disk,
                    COUNT(DISTINCT hostname) AS vm_count
                FROM vm_metrics_history
                WHERE timestamp BETWEEN $1 AND $2
                GROUP BY hour
                ORDER BY hour
            """
            rows = await conn.fetch(query, start_time, end_time)

            timestamps = []
            avg_cpu = []
            avg_memory = []
            avg_disk = []
            vm_counts = []

            for row in rows:
                timestamps.append(row['hour'].isoformat())
                avg_cpu.append(float(row['avg_cpu']) if row['avg_cpu'] else 0)
                avg_memory.append(float(row['avg_memory']) if row['avg_memory'] else 0)
                avg_disk.append(float(row['avg_disk']) if row['avg_disk'] else 0)
                vm_counts.append(row['vm_count'])

            return {
                'time_range': time_range,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'data_points': len(timestamps),
                'timestamps': timestamps,
                'fleet_averages': {
                    'cpu': avg_cpu,
                    'memory': avg_memory,
                    'disk': avg_disk
                },
                'vm_counts': vm_counts
            }

    async def get_metric_statistics(
        self,
        hostname: str,
        metric: str = 'cpu',
        time_range: str = '7d'
    ) -> Dict:
        """Get statistical analysis of a specific metric"""

        range_delta = TimeRange.from_string(time_range)
        end_time = datetime.now()
        start_time = end_time - range_delta

        metric_column = f"{metric}_usage"

        async with self.db.acquire() as conn:
            query = f"""
                SELECT
                    AVG({metric_column}) AS mean,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {metric_column}) AS median,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {metric_column}) AS p95,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY {metric_column}) AS p99,
                    MAX({metric_column}) AS max_value,
                    MIN({metric_column}) AS min_value,
                    STDDEV({metric_column}) AS stddev,
                    COUNT(*) AS sample_count
                FROM vm_metrics_history
                WHERE hostname = $1
                  AND timestamp BETWEEN $2 AND $3
                  AND {metric_column} IS NOT NULL
            """
            row = await conn.fetchrow(query, hostname, start_time, end_time)

            if not row or row['sample_count'] == 0:
                return {
                    'error': 'No data available',
                    'hostname': hostname,
                    'metric': metric,
                    'time_range': time_range
                }

            return {
                'hostname': hostname,
                'metric': metric,
                'time_range': time_range,
                'statistics': {
                    'mean': float(row['mean']) if row['mean'] else 0,
                    'median': float(row['median']) if row['median'] else 0,
                    'p95': float(row['p95']) if row['p95'] else 0,
                    'p99': float(row['p99']) if row['p99'] else 0,
                    'max': float(row['max_value']) if row['max_value'] else 0,
                    'min': float(row['min_value']) if row['min_value'] else 0,
                    'stddev': float(row['stddev']) if row['stddev'] else 0,
                    'samples': row['sample_count']
                }
            }

    async def get_top_resource_consumers(
        self,
        metric: str = 'cpu',
        time_range: str = '24h',
        limit: int = 10
    ) -> List[Dict]:
        """Get VMs with highest average resource usage"""

        range_delta = TimeRange.from_string(time_range)
        end_time = datetime.now()
        start_time = end_time - range_delta

        metric_column = f"{metric}_usage"

        async with self.db.acquire() as conn:
            query = f"""
                SELECT
                    hostname,
                    AVG({metric_column}) AS avg_usage,
                    MAX({metric_column}) AS max_usage,
                    COUNT(*) AS sample_count
                FROM vm_metrics_history
                WHERE timestamp BETWEEN $1 AND $2
                  AND {metric_column} IS NOT NULL
                GROUP BY hostname
                ORDER BY avg_usage DESC
                LIMIT $3
            """
            rows = await conn.fetch(query, start_time, end_time, limit)

            return [
                {
                    'hostname': row['hostname'],
                    'metric': metric,
                    'avg_usage': float(row['avg_usage']),
                    'max_usage': float(row['max_usage']),
                    'samples': row['sample_count']
                }
                for row in rows
            ]

    async def cleanup_old_data(self) -> int:
        """Clean up metrics older than retention period"""

        async with self.db.acquire() as conn:
            query = """
                DELETE FROM vm_metrics_history
                WHERE timestamp < NOW() - ($1 || ' days')::INTERVAL
            """
            result = await conn.execute(query, self.retention_days)

            # Extract count from result string "DELETE N"
            count = int(result.split()[-1]) if result else 0

            logger.info(f"Cleaned up {count} old metric records (retention: {self.retention_days} days)")
            return count

    async def refresh_aggregates(self):
        """Refresh materialized views for aggregated data"""

        async with self.db.acquire() as conn:
            try:
                await conn.execute("REFRESH MATERIALIZED VIEW vm_metrics_hourly")
                await conn.execute("REFRESH MATERIALIZED VIEW vm_metrics_daily")
                logger.info("✓ Refreshed aggregated metrics views")
            except Exception as e:
                logger.error(f"✗ Failed to refresh aggregates: {e}")


# Helper function for easy access
def create_historical_service(db_pool):
    """Create historical data service instance"""
    return HistoricalDataService(db_pool)
