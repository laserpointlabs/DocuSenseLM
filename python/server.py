import os
import sys
import yaml
import json
import uvicorn
import logging
import shutil
import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastmcp import FastMCP
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nda-tool")

# Load configuration
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
DOCUMENTS_DIR = os.path.join(BASE_DIR, "documents")
DB_DIR = os.path.join(BASE_DIR, "chroma_db")
METADATA_FILE = os.path.join(DOCUMENTS_DIR, "metadata.json")

# Load .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

os.makedirs(DOCUMENTS_DIR, exist_ok=True)

try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.error(f"Failed to load config: {e}")
    config = {"document_types": {}, "dashboard": {}}

# Initialize OpenAI
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path=DB_DIR)
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.environ.get("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)
collection = chroma_client.get_or_create_collection(
    name="nda_documents",
    embedding_function=openai_ef
)

# Initialize FastAPI
app = FastAPI(title="NDA Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP
mcp = FastMCP("NDA Tool")

# --- Helpers ---

def load_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_metadata(metadata):
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

def extract_text_from_pdf(filepath):
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting text from {filepath}: {e}")
        return ""

def index_document(filename: str, text: str):
    # Split text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = text_splitter.split_text(text)
    
    # Prepare for Chroma
    ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"filename": filename, "chunk_index": i} for i in range(len(chunks))]
    
    # Delete existing chunks for this file to avoid duplication
    try:
        collection.delete(where={"filename": filename})
    except:
        pass # Might not exist
    
    # Upsert
    if chunks:
        collection.upsert(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )
    logger.info(f"Indexed {len(chunks)} chunks for {filename}")

async def process_document_background(filename: str, filepath: str, doc_type: str):
    logger.info(f"Processing {filename}...")
    text = extract_text_from_pdf(filepath)
    
    if not text:
        logger.warning(f"No text extracted from {filename}")
        return

    # 1. Index into Vector Store
    try:
        index_document(filename, text)
    except Exception as e:
        logger.error(f"Indexing failed for {filename}: {e}")

    # 2. Run Competency Questions
    questions = config.get("document_types", {}).get(doc_type, {}).get("competency_questions", [])
    answers = {}
    
    if questions and openai_client.api_key:
        prompt = f"Analyze the following document text and answer the questions.\n\nDocument Text:\n{text[:100000]}...\n\nQuestions:\n"
        for q in questions:
            prompt += f"- {q['id']}: {q['question']}\n"
        
        prompt += "\nProvide answers in JSON format with keys matching the question IDs."
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a legal document assistant. Respond in JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            answers = json.loads(content)
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
    
    # Update metadata
    metadata = load_metadata()
    if filename in metadata:
        metadata[filename]["status"] = "processed"
        metadata[filename]["competency_answers"] = answers
        save_metadata(metadata)
    
    logger.info(f"Finished processing {filename}")

# --- Models ---

class ChatRequest(BaseModel):
    question: str

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.1", "rag": "enabled"}

@app.get("/config")
def get_config():
    return config

@app.get("/documents")
def list_documents():
    return load_metadata()

@app.get("/files/{filename}")
async def get_file(filename: str):
    file_path = os.path.join(DOCUMENTS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/upload")
async def upload_document(file: UploadFile = File(...), doc_type: str = "nda", background_tasks: BackgroundTasks = None):
    filename = file.filename
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    
    # Save file
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Init metadata
    metadata = load_metadata()
    metadata[filename] = {
        "filename": filename,
        "doc_type": doc_type,
        "upload_date": datetime.datetime.now().isoformat(),
        "status": "pending",
        "competency_answers": {}
    }
    save_metadata(metadata)
    
    # Process
    background_tasks.add_task(process_document_background, filename, filepath, doc_type)
    
    return {"status": "uploaded", "filename": filename}

@app.post("/reprocess/{filename}")
async def reprocess_document(filename: str, background_tasks: BackgroundTasks):
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    # Update status
    metadata[filename]["status"] = "reprocessing"
    save_metadata(metadata)
    
    # Re-run processing
    doc_type = metadata[filename].get("doc_type", "nda")
    background_tasks.add_task(process_document_background, filename, filepath, doc_type)
    
    return {"status": "reprocessing_started", "filename": filename}

@app.post("/chat")
async def chat(request: ChatRequest):
    if not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured")

    # 1. Retrieve relevant chunks from Chroma
    results = collection.query(
        query_texts=[request.question],
        n_results=10
    )
    
    # 2. Build Context
    context_text = ""
    retrieved_files = set()
    
    if results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            filename = meta.get('filename', 'unknown')
            retrieved_files.add(filename)
            context_text += f"--- Excerpt from {filename} ---\n{doc}\n\n"
    
    logger.info(f"RAG retrieved context from: {retrieved_files}")

    # 3. Call LLM
    prompt = f"Context:\n{context_text}\n\nQuestion: {request.question}"
    
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for analyzing legal documents. Use the provided context to answer the user's question. Cite the document filename if possible."},
            {"role": "user", "content": prompt}
        ]
    )
    
    return {
        "answer": response.choices[0].message.content,
        "sources": list(retrieved_files)
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)
