#!/bin/bash
#
# Clean restart script for NDA Tool
# Usage: ./scripts/restart.sh [--clean] [--no-seed] [--no-build]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default options
CLEAN_VOLUMES=false
SEED_DATA=true
BUILD_IMAGES=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_VOLUMES=true
            shift
            ;;
        --no-seed)
            SEED_DATA=false
            shift
            ;;
        --build)
            BUILD_IMAGES=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --clean     Clean volumes (removes all data)"
            echo "  --no-seed   Skip seeding sample documents"
            echo "  --build      Rebuild Docker images"
            echo "  --help, -h   Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Quick restart (keeps data)"
            echo "  $0 --clean            # Clean restart (removes all data)"
            echo "  $0 --clean --no-seed  # Clean restart without seeding"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Detect docker compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}Error: docker-compose or docker compose not found${NC}"
    exit 1
fi

echo -e "${GREEN}=== NDA Tool Restart Script ===${NC}"
echo ""

# Step 1: Stop services
echo -e "${YELLOW}[1/5] Stopping services...${NC}"
$COMPOSE_CMD down

# Step 2: Clean volumes if requested
if [ "$CLEAN_VOLUMES" = true ]; then
    echo -e "${YELLOW}[2/5] Cleaning volumes (this will remove all data)...${NC}"
    $COMPOSE_CMD down -v
else
    echo -e "${GREEN}[2/5] Keeping volumes (data preserved)${NC}"
fi

# Step 3: Build images if requested
if [ "$BUILD_IMAGES" = true ]; then
    echo -e "${YELLOW}[3/5] Building Docker images...${NC}"
    $COMPOSE_CMD build --parallel
else
    echo -e "${GREEN}[3/5] Skipping image build${NC}"
fi

# Step 4: Start services
echo -e "${YELLOW}[4/5] Starting services...${NC}"
$COMPOSE_CMD up -d

# Wait for postgres to be ready
echo -e "${YELLOW}Waiting for database to be ready...${NC}"
sleep 5
for i in {1..30}; do
    if $COMPOSE_CMD exec -T postgres pg_isready -U nda_user &> /dev/null; then
        echo -e "${GREEN}Database is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Timeout waiting for database${NC}"
        exit 1
    fi
    sleep 1
done

# Step 5: Initialize database
echo -e "${YELLOW}[5/5] Initializing database schema...${NC}"
$COMPOSE_CMD exec -T api python -m api.db.migrations.001_init_schema || {
    echo -e "${RED}Failed to initialize database${NC}"
    exit 1
}

# Step 6: Seed data if requested
if [ "$SEED_DATA" = true ]; then
    echo -e "${YELLOW}[6/6] Seeding sample documents...${NC}"
    $COMPOSE_CMD exec -T api python scripts/seed_data.py || {
        echo -e "${YELLOW}Warning: Failed to seed data (this is OK if documents already exist)${NC}"
    }
else
    echo -e "${GREEN}[6/6] Skipping data seeding${NC}"
fi

echo ""
echo -e "${GREEN}=== Restart Complete! ===${NC}"
echo ""
echo "Services are running:"
echo "  • UI:      http://localhost:3000"
echo "  • API:     http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo ""
echo "To view logs: $COMPOSE_CMD logs -f"
echo "To stop:     $COMPOSE_CMD down"

