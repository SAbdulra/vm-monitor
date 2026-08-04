#!/usr/bin/env python3
"""
Telegraf execd output plugin
Receives metrics from Telegraf via stdin, writes directly to PostgreSQL
This triggers pg_notify() immediately for real-time dashboard updates
"""

import sys
import json
import os
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)  # Telegraf reads stdout, logs go to stderr
    ]
)
logger = logging.getLogger(__name__)

# PostgreSQL connection - configure via environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'infra_monitor'),
    'user': os.getenv('DB_USER', 'vm_monitor'),
    'password': os.getenv('DB_PASSWORD')  # REQUIRED - set in environment
}

def parse_telegraf_metric(metric):
    """Parse Telegraf JSON metric into our schema"""
    try:
        name = metric.get('name')
        tags = metric.get('tags', {})
        fields = metric.get('fields', {})
        timestamp = metric.get('timestamp', int(datetime.now().timestamp()))

        # http_listener_v2 wraps metrics - unwrap if needed
        if name == 'http_listener_v2':
            # Telegraf wrapped the original metric in fields
            inner_fields = fields.get('fields', {})
            if inner_fields:
                # Extract original metric name from field names
                for key in inner_fields:
                    if key.startswith('fields_'):
                        # This is a wrapped metric
                        original_field = key.replace('fields_', '')
                        fields[original_field] = inner_fields[key]
                # Get original name from tags if available
                if 'name' in fields:
                    name = fields['name']
            timestamp = fields.get('timestamp', timestamp)

        # Get hostname from tags or fields
        hostname = tags.get('host', fields.get('host', 'unknown'))

        # Convert timestamp to datetime (handle both seconds and nanoseconds)
        if timestamp > 10000000000000:  # nanoseconds
            dt = datetime.fromtimestamp(timestamp / 1_000_000_000)
        else:  # seconds
            dt = datetime.fromtimestamp(timestamp)

        # Extract metrics based on measurement type
        data = {
            'hostname': hostname,
            'timestamp': dt,
            'cpu_usage': None,
            'memory_usage': None,
            'disk_usage': None,
            'status': 'online'
        }

        if name == 'cpu' or 'usage_idle' in fields:
            # Telegraf reports usage_idle, we want usage_active
            usage_idle = fields.get('usage_idle')
            if usage_idle is not None:
                data['cpu_usage'] = round(100 - usage_idle, 2)

        if name == 'mem' or 'used_percent' in fields:
            # mem reports used_percent directly
            used_percent = fields.get('used_percent')
            if used_percent is not None:
                data['memory_usage'] = round(used_percent, 2)

        if name == 'disk':
            # disk reports used_percent per mount (aggregate across mounts)
            used_percent = fields.get('used_percent')
            if used_percent is not None:
                data['disk_usage'] = round(used_percent, 2)

        if name == 'swap':
            # swap reports used_percent
            used_percent = fields.get('used_percent')
            if used_percent is not None:
                data['disk_usage'] = round(used_percent, 2)

        # Only return if we have at least one metric
        if any([data['cpu_usage'], data['memory_usage'], data['disk_usage']]):
            return data

        return None

    except Exception as e:
        logger.error(f"Error parsing metric: {e} | Metric: {metric}")
        return None

def aggregate_metrics(metrics_batch):
    """Aggregate metrics by hostname (latest values win)"""
    by_host = {}

    for metric in metrics_batch:
        if not metric:
            continue

        host = metric['hostname']

        if host not in by_host:
            by_host[host] = {
                'hostname': host,
                'timestamp': metric['timestamp'],
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'status': 'online'
            }

        # Update with latest non-None values
        if metric['cpu_usage'] is not None:
            by_host[host]['cpu_usage'] = metric['cpu_usage']
            by_host[host]['timestamp'] = metric['timestamp']  # Update timestamp

        if metric['memory_usage'] is not None:
            by_host[host]['memory_usage'] = metric['memory_usage']

        if metric['disk_usage'] is not None:
            by_host[host]['disk_usage'] = metric['disk_usage']

    return list(by_host.values())

def insert_to_postgres(conn, metrics_batch):
    """Batch insert metrics into PostgreSQL"""
    if not metrics_batch:
        return

    try:
        cursor = conn.cursor()

        # Aggregate metrics by hostname
        aggregated = aggregate_metrics(metrics_batch)

        if not aggregated:
            return

        # Batch insert
        for data in aggregated:
            cursor.execute("""
                INSERT INTO vm_detailed_metrics
                (hostname, cpu_usage_percent, ram_usage_percent, swap_usage_percent, timestamp, status)
                VALUES (%(hostname)s, %(cpu_usage)s, %(memory_usage)s, %(disk_usage)s, %(timestamp)s, %(status)s)
            """, data)

        conn.commit()
        logger.info(f"✓ Inserted {len(aggregated)} VM metrics → PostgreSQL (triggers NOTIFY)")

    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        conn.rollback()

def main():
    """Read metrics from stdin (Telegraf execd), write to PostgreSQL"""

    logger.info("🚀 Telegraf→PostgreSQL Direct Writer Starting...")
    logger.info(f"   Target: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    # Connect to PostgreSQL
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("✓ Connected to PostgreSQL on ashdaimonapp01l")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    metrics_batch = []
    batch_size = 100  # Insert every 100 metrics (or every 5s via flush_interval)
    metrics_processed = 0

    try:
        logger.info("📡 Listening for Telegraf metrics on stdin...")

        for line in sys.stdin:
            try:
                # Telegraf sends one metric per line as JSON
                line = line.strip()
                if not line:
                    continue

                metric = json.loads(line)
                parsed = parse_telegraf_metric(metric)

                if parsed:
                    metrics_batch.append(parsed)
                    metrics_processed += 1

                # Batch insert when we have enough
                if len(metrics_batch) >= batch_size:
                    insert_to_postgres(conn, metrics_batch)
                    metrics_batch = []

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                continue
            except Exception as e:
                logger.error(f"Error processing line: {e}")
                continue

    except KeyboardInterrupt:
        logger.info("⚠️  Received interrupt signal")
    finally:
        # Insert remaining metrics
        if metrics_batch:
            logger.info(f"Flushing {len(metrics_batch)} remaining metrics...")
            insert_to_postgres(conn, metrics_batch)

        conn.close()
        logger.info(f"✓ PostgreSQL connection closed ({metrics_processed} total metrics processed)")

if __name__ == '__main__':
    main()
