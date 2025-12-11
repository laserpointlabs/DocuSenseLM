import os
import json
from typing import List

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from fastapi import FastAPI, HTTPException
from fastmcp import FastMCP
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
os.makedirs(DB_DIR, exist_ok=True)

app = FastAPI(title="MCP RAG Server")
mcp = FastMCP("mcp-rag")

chroma_client = chromadb.PersistentClient(
    path=DB_DIR,
    settings=Settings(anonymized_telemetry=False),
)

api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is required for embeddings")

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=api_key,
    model_name="text-embedding-3-small",
)
collection = chroma_client.get_or_create_collection(
    name="rag_documents", embedding_function=openai_ef
)


class IngestRequest(BaseModel):
    doc_id: str
    filename: str
    text: str
    chunk_size: int = 1000
    chunk_overlap: int = 200
    metadata: dict = {}


class QueryRequest(BaseModel):
    query: str
    n: int = 5


@app.post("/ingest")
async def ingest(req: IngestRequest):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_text(req.text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks produced from text")

    ids = [f"{req.doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {"doc_id": req.doc_id, "filename": req.filename, "chunk_index": i, **req.metadata}
        for i in range(len(chunks))
    ]
    collection.upsert(documents=chunks, ids=ids, metadatas=metadatas)
    return {"status": "ok", "chunks": len(chunks)}


@app.post("/query")
async def query(req: QueryRequest):
    results = collection.query(query_texts=[req.query], n_results=req.n)
    out = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        out.append({"text": doc, "metadata": meta})
    return {"results": out}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("MCP_RAG_PORT", "8002")))

