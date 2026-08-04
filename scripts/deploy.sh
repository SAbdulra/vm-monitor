#!/bin/bash
# VM Monitor - Deployment Script

set -e

echo "======================================"
echo "VM Monitor - Deployment Script"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure your settings"
    exit 1
fi

# Source environment variables
source .env

echo -e "${GREEN}✓${NC} Environment variables loaded"

# Check if Docker/Podman is installed
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    COMPOSE_CMD="podman-compose"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Error: Neither Docker nor Podman is installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Using $CONTAINER_CMD"

# Build images
echo ""
echo "Building container images..."
cd docker

echo "  Building backend..."
$CONTAINER_CMD build -t vm-monitor-backend:latest ./backend

echo "  Building telegraf-processor..."
$CONTAINER_CMD build -t vm-monitor-telegraf-processor:latest ./telegraf-processor

echo "  Building cve-downloader..."
$CONTAINER_CMD build -t vm-monitor-cve-downloader:latest ./cve-downloader

echo -e "${GREEN}✓${NC} All images built successfully"

# Start containers
echo ""
echo "Starting containers..."
$COMPOSE_CMD up -d

echo ""
echo "Waiting for containers to start..."
sleep 10

# Check container status
echo ""
echo "Container Status:"
$CONTAINER_CMD ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Test backend health
echo ""
echo "Testing backend health..."
sleep 5

if curl -s -f http://localhost:8001/api/dashboard/stats > /dev/null; then
    echo -e "${GREEN}✓${NC} Backend is responding"
else
    echo -e "${YELLOW}⚠${NC}  Backend is starting up, please wait..."
fi

echo ""
echo "======================================"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Configure Nginx (see nginx/vm_monitor.conf)"
echo "2. Access dashboard at: https://your-server/
"
echo "3. Check logs: $CONTAINER_CMD logs vm-monitor-backend-1"
echo "4. Monitor resources: $CONTAINER_CMD stats"
echo ""
echo "Useful commands:"
echo "  Stop:    $COMPOSE_CMD down"
echo "  Restart: $COMPOSE_CMD restart"
echo "  Logs:    $COMPOSE_CMD logs -f"
echo ""
