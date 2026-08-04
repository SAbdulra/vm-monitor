FROM python:3.11-slim

LABEL maintainer="VM Monitor Team"
LABEL description="FastAPI backend for VM monitoring platform"

WORKDIR /app

# Install system dependencies including LDAP development headers
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    libldap2-dev \
    libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py ./

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/dashboard/stats || exit 1

# Run with uvicorn
CMD ["uvicorn", "postgres_backend:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
