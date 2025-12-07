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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastmcp import FastMCP
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nda-tool")

# Load configuration
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
DOCUMENTS_DIR = os.path.join(BASE_DIR, "documents")
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
# Note: In a real app, we might want to pass this from the frontend or config
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

async def process_document_background(filename: str, filepath: str, doc_type: str):
    logger.info(f"Processing {filename}...")
    text = extract_text_from_pdf(filepath)
    
    # Run competency questions using LLM
    questions = config.get("document_types", {}).get(doc_type, {}).get("competency_questions", [])
    answers = {}
    
    if questions and text and openai_client.api_key:
        prompt = f"Analyze the following document text and answer the questions.\n\nDocument Text:\n{text[:20000]}...\n\nQuestions:\n"
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
        metadata[filename]["text_preview"] = text[:200]
        metadata[filename]["competency_answers"] = answers
        save_metadata(metadata)
    
    logger.info(f"Finished processing {filename}")

# --- Models ---

class ChatRequest(BaseModel):
    question: str
    context_files: List[str] = []

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/config")
def get_config():
    return config

@app.get("/documents")
def list_documents():
    return load_metadata()

@app.post("/upload")
async def upload_document(file: UploadFile = File(...), doc_type: str = "nda", background_tasks: BackgroundTasks = None):
    filename = file.filename
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    metadata = load_metadata()
    metadata[filename] = {
        "filename": filename,
        "doc_type": doc_type,
        "upload_date": datetime.datetime.now().isoformat(),
        "status": "pending",
        "competency_answers": {}
    }
    save_metadata(metadata)
    
    background_tasks.add_task(process_document_background, filename, filepath, doc_type)
    
    return {"status": "uploaded", "filename": filename}

@app.post("/chat")
async def chat(request: ChatRequest):
    if not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured")

    context = ""
    # Naive context loading: load text of all selected files
    # In a real app with "hundreds" of docs, we need a vector store (e.g. Chroma/FAISS) or better selection.
    # For now, we'll limit to the first few or rely on specific selection.
    
    metadata = load_metadata()
    for filename in request.context_files:
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.exists(filepath):
            text = extract_text_from_pdf(filepath)
            context += f"--- Document: {filename} ---\n{text[:10000]}\n\n" # Truncate for token limits
            
    prompt = f"Context:\n{context}\n\nQuestion: {request.question}"
    
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for analyzing legal documents."},
            {"role": "user", "content": prompt}
        ]
    )
    
    return {"answer": response.choices[0].message.content}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)
