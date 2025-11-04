"""
Health check router
"""
from fastapi import APIRouter
from api.models.responses import HealthResponse
from datetime import datetime
from ingest.indexer_opensearch import opensearch_indexer
from ingest.indexer_qdrant import qdrant_indexer

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    """
    services = {}

    # Check OpenSearch
    try:
        opensearch_indexer.client.cluster.health()
        services["opensearch"] = "healthy"
    except:
        services["opensearch"] = "unhealthy"

    # Check Qdrant
    try:
        qdrant_indexer.client.get_collections()
        services["qdrant"] = "healthy"
    except:
        services["qdrant"] = "unhealthy"

    # Overall status
    all_healthy = all(status == "healthy" for status in services.values())
    status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=status,
        services=services,
        timestamp=datetime.now()
    )
