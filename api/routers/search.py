"""
Search router
"""
from fastapi import APIRouter, HTTPException
from api.models.requests import SearchRequest
from api.models.responses import SearchResponse, SearchResult
from api.services.search_service import get_search_service_instance

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Hybrid search endpoint (BM25 + vector)
    """
    try:
        service = get_search_service_instance()
        results = service.hybrid_search(
            query=request.query,
            k=request.k,
            filters=request.filters
        )

        # Convert to response format
        search_results = [
            SearchResult(
                chunk_id=r['chunk_id'],
                score=r['score'],
                text=r['text'],
                doc_id=r['doc_id'],
                section_type=r['section_type'],
                clause_number=r.get('clause_number'),
                page_num=r['page_num'],
                span_start=r['span_start'],
                span_end=r['span_end'],
                source_uri=r['source_uri']
            )
            for r in results
        ]

        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=request.query
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
