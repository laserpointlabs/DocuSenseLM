import os
import json
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from openai import OpenAI

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")

app = FastAPI(title="MCP LLM Server")
mcp = FastMCP("mcp-llm")

api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is required for MCP LLM Server")

client = OpenAI(api_key=api_key)


class ClassifyRequest(BaseModel):
    text: str


class ExtractRequest(BaseModel):
    text: str


class CaptureField(BaseModel):
    id: str
    question: str
    type: Optional[str] = None  # hint (e.g., date, text, bool, number)


class ClassifyExtractRequest(BaseModel):
    text: str
    capture_fields: Optional[List[CaptureField]] = Field(default=None, description="Optional list of fields/questions to extract; answers keyed by id")


def call_llm(system_prompt: str, user_prompt: str) -> str:
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM call failed: {exc}") from exc


@app.post("/classify")
async def classify(req: ClassifyRequest):
    system_prompt = (
        "You are a document type classifier for legal and business agreements. "
        "Return a JSON object with fields: doc_type (string), confidence (0-1). "
        "doc_type must be simple types like 'nda', 'distributor_agreement', 'msa', 'po', 'other'."
    )
    user_prompt = f"Text:\n{req.text[:8000]}"
    content = call_llm(system_prompt, user_prompt)
    try:
        data = json.loads(content)
    except Exception:
        data = {"doc_type": "other", "confidence": 0.0, "raw": content}
    return data


@app.post("/extract")
async def extract(req: ExtractRequest):
    system_prompt = (
        "You are an information extractor for legal documents. "
        "Return a JSON object with fields: parties (list of strings), effective_date, "
        "execution_date, expiration_date, term_length, auto_renewal (bool), notices (string). "
        "Use ISO date strings when possible; use empty string if unknown."
    )
    user_prompt = f"Document text:\n{req.text[:20000]}"
    content = call_llm(system_prompt, user_prompt)
    try:
        data = json.loads(content)
    except Exception:
        data = {"parties": [], "effective_date": "", "execution_date": "", "expiration_date": "", "term_length": "", "auto_renewal": False, "notices": "", "raw": content}
    return data


@app.post("/classify_and_extract")
async def classify_and_extract(req: ClassifyExtractRequest):
    if req.capture_fields:
        fields_desc = "\n".join(
            [f"- {f.id}: {f.question} (type: {f.type or 'text'})" for f in req.capture_fields]
        )
        extraction_instruction = (
            "Return 'extraction' as a JSON object with keys exactly matching the field ids below. "
            "Use ISO date strings for date fields when possible; use empty string if unknown. "
            "Fields:\n" + fields_desc
        )
    else:
        extraction_instruction = (
            "Return 'extraction' as a JSON object with keys: parties, effective_date, execution_date, expiration_date, term_length, auto_renewal, notices. "
            "Use ISO date strings when possible; use empty string if unknown."
        )

    system_prompt = (
        "You are a legal document assistant. "
        "Return a JSON object with two keys: "
        "'classification': {doc_type, confidence}, "
        f"'extraction': ... {extraction_instruction}"
    )
    user_prompt = f"Document text:\n{req.text[:20000]}"
    content = call_llm(system_prompt, user_prompt)
    try:
        data = json.loads(content)
    except Exception:
        default_extraction = {f.id: "" for f in (req.capture_fields or [])}
        data = {
            "classification": {"doc_type": "other", "confidence": 0.0},
            "extraction": default_extraction,
            "raw": content,
        }
    return data


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("MCP_LLM_PORT", "7003")))

