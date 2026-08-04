FROM python:3.11-slim

LABEL maintainer="VM Monitor Team"
LABEL description="Telegraf metrics processor for VM monitoring"

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir psycopg2-binary

# Copy script
COPY telegraf_metrics_to_postgres.py .

# Make executable
RUN chmod +x telegraf_metrics_to_postgres.py

# Run the script reading from stdin
CMD ["python3", "-u", "telegraf_metrics_to_postgres.py"]
