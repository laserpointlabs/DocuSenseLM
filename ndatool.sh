#!/bin/bash
#
# NDA Tool Management Script
# Comprehensive script to manage the NDA Tool application
#
# Usage: ./ndatool.sh <command> [options]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
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

# Functions
show_help() {
    cat << EOF
${GREEN}NDA Tool Management Script${NC}

Usage: ./ndatool.sh <command> [options]

Commands:
  start          Start all services
  stop           Stop all services
  restart        Restart services (keeps data)
  restart-clean  Clean restart (removes all data)
  status         Show status of all services
  logs           Show logs (use --follow or -f to follow)
  shell          Open shell in API container
  db-init        Initialize database schema
  seed           Seed sample documents
  reindex        Re-index all documents
  build          Build Docker images
  clean          Stop and remove volumes (removes all data)
  health         Check health of services
  info           Show application information

Options:
  --no-seed      Skip seeding when restarting
  --build        Rebuild images when restarting
  --follow, -f    Follow logs (for logs command)
  --service      Specify service name (for logs command)

Examples:
  ./ndatool.sh start              # Start all services
  ./ndatool.sh restart            # Restart (keeps data)
  ./ndatool.sh restart-clean      # Clean restart
  ./ndatool.sh logs --follow      # Follow logs
  ./ndatool.sh logs --service api # Show API logs only
  ./ndatool.sh status             # Check service status
  ./ndatool.sh shell              # Open API shell

EOF
}

wait_for_db() {
    echo -e "${YELLOW}Waiting for database to be ready...${NC}"
    sleep 3
    for i in {1..30}; do
        if $COMPOSE_CMD exec -T postgres pg_isready -U nda_user &> /dev/null 2>&1; then
            echo -e "${GREEN}Database is ready!${NC}"
            return 0
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}Timeout waiting for database${NC}"
            return 1
        fi
        sleep 1
    done
}

cmd_start() {
    echo -e "${GREEN}=== Starting NDA Tool ===${NC}"
    $COMPOSE_CMD up -d
    wait_for_db
    echo ""
    echo -e "${GREEN}Services started!${NC}"
    echo ""
    show_info
}

cmd_stop() {
    echo -e "${YELLOW}=== Stopping NDA Tool ===${NC}"
    $COMPOSE_CMD down
    echo -e "${GREEN}Services stopped${NC}"
}

cmd_restart() {
    local CLEAN=false
    local SEED=true
    local BUILD=false
    
    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean)
                CLEAN=true
                shift
                ;;
            --no-seed)
                SEED=false
                shift
                ;;
            --build)
                BUILD=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    echo -e "${GREEN}=== Restarting NDA Tool ===${NC}"
    echo ""
    
    # Stop services
    echo -e "${YELLOW}[1/6] Stopping services...${NC}"
    $COMPOSE_CMD down
    
    # Clean volumes if requested
    if [ "$CLEAN" = true ]; then
        echo -e "${YELLOW}[2/6] Cleaning volumes (this will remove all data)...${NC}"
        $COMPOSE_CMD down -v
    else
        echo -e "${GREEN}[2/6] Keeping volumes (data preserved)${NC}"
    fi
    
    # Build images if requested
    if [ "$BUILD" = true ]; then
        echo -e "${YELLOW}[3/6] Building Docker images...${NC}"
        $COMPOSE_CMD build --parallel
    else
        echo -e "${GREEN}[3/6] Skipping image build${NC}"
    fi
    
    # Start services
    echo -e "${YELLOW}[4/6] Starting services...${NC}"
    $COMPOSE_CMD up -d
    
    # Wait for database
    wait_for_db
    
    # Initialize database
    echo -e "${YELLOW}[5/6] Initializing database schema...${NC}"
    $COMPOSE_CMD exec -T api python -m api.db.migrations.001_init_schema || {
        echo -e "${RED}Failed to initialize database${NC}"
        exit 1
    }
    
    # Seed data if requested
    if [ "$SEED" = true ]; then
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
    show_info
}

cmd_restart_clean() {
    cmd_restart --clean "$@"
}

cmd_status() {
    echo -e "${GREEN}=== Service Status ===${NC}"
    echo ""
    $COMPOSE_CMD ps
    echo ""
    echo -e "${BLUE}Service URLs:${NC}"
    echo "  • UI:      http://localhost:3000"
    echo "  • API:     http://localhost:8000"
    echo "  • API Docs: http://localhost:8000/docs"
    echo "  • MinIO:   http://localhost:9001"
}

cmd_logs() {
    local FOLLOW=false
    local SERVICE=""
    
    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --follow|-f)
                FOLLOW=true
                shift
                ;;
            --service)
                SERVICE="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    if [ "$FOLLOW" = true ]; then
        if [ -n "$SERVICE" ]; then
            $COMPOSE_CMD logs -f "$SERVICE"
        else
            $COMPOSE_CMD logs -f
        fi
    else
        if [ -n "$SERVICE" ]; then
            $COMPOSE_CMD logs --tail=100 "$SERVICE"
        else
            $COMPOSE_CMD logs --tail=100
        fi
    fi
}

cmd_shell() {
    echo -e "${GREEN}Opening shell in API container...${NC}"
    $COMPOSE_CMD exec api /bin/bash
}

cmd_db_init() {
    echo -e "${YELLOW}Initializing database schema...${NC}"
    $COMPOSE_CMD exec -T api python -m api.db.migrations.001_init_schema
    echo -e "${GREEN}Database initialized${NC}"
}

cmd_seed() {
    echo -e "${YELLOW}Seeding sample documents...${NC}"
    $COMPOSE_CMD exec api python scripts/seed_data.py
    echo -e "${GREEN}Seeding complete${NC}"
}

cmd_reindex() {
    echo -e "${YELLOW}Re-indexing all documents...${NC}"
    $COMPOSE_CMD exec api python scripts/reindex.py --all
    echo -e "${GREEN}Re-indexing complete${NC}"
}

cmd_build() {
    echo -e "${YELLOW}Building Docker images...${NC}"
    $COMPOSE_CMD build --parallel
    echo -e "${GREEN}Build complete${NC}"
}

cmd_clean() {
    echo -e "${RED}WARNING: This will remove all data!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo -e "${YELLOW}Cleaning volumes and containers...${NC}"
        $COMPOSE_CMD down -v
        echo -e "${GREEN}Clean complete${NC}"
    else
        echo -e "${YELLOW}Cancelled${NC}"
    fi
}

cmd_health() {
    echo -e "${GREEN}=== Health Check ===${NC}"
    echo ""
    
    # Check API
    echo -n "API: "
    if curl -s http://localhost:8000/ > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
    
    # Check UI
    echo -n "UI: "
    if curl -s http://localhost:3000/ > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Running${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
    
    # Check database
    echo -n "Database: "
    if $COMPOSE_CMD exec -T postgres pg_isready -U nda_user &> /dev/null 2>&1; then
        echo -e "${GREEN}✓ Ready${NC}"
    else
        echo -e "${RED}✗ Not ready${NC}"
    fi
    
    echo ""
    cmd_status
}

show_info() {
    echo -e "${BLUE}Application Information:${NC}"
    echo "  • UI:      http://localhost:3000"
    echo "  • API:     http://localhost:8000"
    echo "  • API Docs: http://localhost:8000/docs"
    echo "  • MinIO:   http://localhost:9001"
    echo ""
    echo "Useful commands:"
    echo "  ./ndatool.sh logs --follow    # Follow logs"
    echo "  ./ndatool.sh status           # Check status"
    echo "  ./ndatool.sh shell            # Open API shell"
}

# Main command dispatcher
case "${1:-help}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        shift
        cmd_restart "$@"
        ;;
    restart-clean)
        shift
        cmd_restart_clean "$@"
        ;;
    status)
        cmd_status
        ;;
    logs)
        shift
        cmd_logs "$@"
        ;;
    shell)
        cmd_shell
        ;;
    db-init)
        cmd_db_init
        ;;
    seed)
        cmd_seed
        ;;
    reindex)
        cmd_reindex
        ;;
    build)
        cmd_build
        ;;
    clean)
        cmd_clean
        ;;
    health)
        cmd_health
        ;;
    info)
        show_info
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

