"""
Answer router
"""
from fastapi import APIRouter, HTTPException
from api.models.requests import AnswerRequest
from api.models.responses import AnswerResponse, Citation
from api.services.answer_service import answer_service

router = APIRouter(prefix="/answer", tags=["answer"])


@router.post("", response_model=AnswerResponse)
async def answer(request: AnswerRequest):
    """
    Generate answer using LLM with citations
    """
    try:
        answer_obj = await answer_service.generate_answer(
            question=request.question,
            filters=request.filters,
            max_context_chunks=request.max_context_chunks
        )

        # Convert citations to response format
        citations = [
            Citation(
                doc_id=c.doc_id,
                clause_number=c.clause_number,
                page_num=c.page_num,
                span_start=c.span_start,
                span_end=c.span_end,
                source_uri=c.source_uri,
                excerpt=c.excerpt
            )
            for c in answer_obj.citations
        ]

        return AnswerResponse(
            answer=answer_obj.text,
            citations=citations,
            question=request.question
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
