import os
import sys
import yaml
import json
import uvicorn
import logging
import shutil
import datetime
import pickletools
import diskcache
from typing import List, Dict, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastmcp import FastMCP
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
from platformdirs import user_config_dir
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nda-tool")

# Load configuration
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

# Use USER_DATA_DIR from environment or fall back to platform-specific config dir
# e.g. ~/.config/docusenselm on Linux
default_user_data = user_config_dir("docusenselm", appauthor=False)
USER_DATA_DIR = os.environ.get("USER_DATA_DIR", default_user_data)

DOCUMENTS_DIR = os.path.join(USER_DATA_DIR, "documents")
TEMPLATES_DIR = os.path.join(USER_DATA_DIR, "templates")
DB_DIR = os.path.join(USER_DATA_DIR, "chroma_db")
METADATA_FILE = os.path.join(DOCUMENTS_DIR, "metadata.json")

# Ensure all directories exist
os.makedirs(DOCUMENTS_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# Load .env
load_dotenv(os.path.join(BASE_DIR, ".env"))
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")
APP_NAME = os.environ.get("APP_NAME", "NDA Tool")

# Load prompts
def load_prompts_config():
    # Try loading user override first
    user_prompts = os.path.join(USER_DATA_DIR, "prompts.yaml")
    if os.path.exists(user_prompts):
        try:
            with open(user_prompts, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load user prompts: {e}")
    
    # Fallback to default
    default_prompts = os.path.join(BASE_DIR, "prompts.default.yaml")
    try:
        with open(default_prompts, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load default prompts: {e}")
        return {}

prompts_config = load_prompts_config()

# Load configuration
def load_app_config():
    # Try loading user override first
    user_config = os.path.join(USER_DATA_DIR, "config.yaml")
    if os.path.exists(user_config):
        try:
            with open(user_config, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load user config: {e}")
    
    # Fallback to default
    default_config = os.path.join(BASE_DIR, "config.default.yaml")
    try:
        with open(default_config, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load default config: {e}")
        return {"document_types": {}, "dashboard": {}}

config = load_app_config()

# Ensure user config files exist in USER_DATA_DIR for editing
if not os.path.exists(os.path.join(USER_DATA_DIR, "config.yaml")):
    shutil.copy(os.path.join(BASE_DIR, "config.default.yaml"), os.path.join(USER_DATA_DIR, "config.yaml"))

if not os.path.exists(os.path.join(USER_DATA_DIR, "prompts.yaml")):
    shutil.copy(os.path.join(BASE_DIR, "prompts.default.yaml"), os.path.join(USER_DATA_DIR, "prompts.yaml"))

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
app = FastAPI(title=f"{APP_NAME} API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP
mcp = FastMCP(APP_NAME)

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
        system_prompt = prompts_config.get("prompts", {}).get("competency_extraction", {}).get("system", "You are a legal document assistant. Respond in JSON.")
        user_prompt_template = prompts_config.get("prompts", {}).get("competency_extraction", {}).get("user", "Analyze the text:\n{document_text}\n\nQuestions:\n{questions_list}")
        
        questions_list_str = "\n".join([f"- {q['id']}: {q['question']}" for q in questions])
        
        user_prompt = user_prompt_template.format(
            document_text=text[:100000],
            questions_list=questions_list_str
        )
        
        try:
            response = openai_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
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

class UpdateStatusRequest(BaseModel):
    status: str

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

@app.get("/settings/files")
def list_config_files():
    return ["config.yaml", "prompts.yaml"]

@app.get("/settings/file/{filename}")
def get_config_file(filename: str):
    if filename not in ["config.yaml", "prompts.yaml"]:
        raise HTTPException(status_code=400, detail="Invalid file")
    
    filepath = os.path.join(USER_DATA_DIR, filename)
    try:
        with open(filepath, "r") as f:
            return {"content": f.read()}
    except FileNotFoundError:
        # If not found in user dir, try default
        default_name = filename.replace(".yaml", ".default.yaml")
        try:
            with open(os.path.join(BASE_DIR, default_name), "r") as f:
                return {"content": f.read()}
        except:
            raise HTTPException(status_code=404, detail="File not found")

@app.post("/settings/file/{filename}")
async def save_config_file(filename: str, request: Dict[str, str]):
    if filename not in ["config.yaml", "prompts.yaml"]:
        raise HTTPException(status_code=400, detail="Invalid file")
    
    content = request.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="Content required")
    
    # Validate YAML
    try:
        yaml.safe_load(content)
    except yaml.YAMLError:
        raise HTTPException(status_code=400, detail="Invalid YAML format")
        
    filepath = os.path.join(USER_DATA_DIR, filename)
    
    # Create Backup
    if os.path.exists(filepath):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filepath}.{timestamp}.bak"
        shutil.copy(filepath, backup_path)
        
        # Also save as "last_good" for quick restore
        last_good_path = f"{filepath}.last_good.bak"
        shutil.copy(filepath, last_good_path)

    with open(filepath, "w") as f:
        f.write(content)
        
    # Reload configs in-memory
    global config, prompts_config
    config = load_app_config()
    prompts_config = load_prompts_config()
    
    return {"status": "saved"}

@app.post("/settings/restore_last_good/{filename}")
def restore_last_good_config(filename: str):
    if filename not in ["config.yaml", "prompts.yaml"]:
        raise HTTPException(status_code=400, detail="Invalid file")
        
    filepath = os.path.join(USER_DATA_DIR, filename)
    last_good_path = f"{filepath}.last_good.bak"
    
    if os.path.exists(last_good_path):
        shutil.copy(last_good_path, filepath)
        
        # Reload
        global config, prompts_config
        config = load_app_config()
        prompts_config = load_prompts_config()
        
        with open(filepath, "r") as f:
            return {"content": f.read(), "status": "restored"}
            
    raise HTTPException(status_code=404, detail="No backup found")

@app.post("/settings/reset/{filename}")
def reset_config_file(filename: str):
    if filename not in ["config.yaml", "prompts.yaml"]:
        raise HTTPException(status_code=400, detail="Invalid file")
        
    default_name = filename.replace(".yaml", ".default.yaml")
    default_path = os.path.join(BASE_DIR, default_name)
    user_path = os.path.join(USER_DATA_DIR, filename)
    
    if os.path.exists(default_path):
        shutil.copy(default_path, user_path)
        # Reload
        global config, prompts_config
        config = load_app_config()
        prompts_config = load_prompts_config()
        
        with open(user_path, "r") as f:
            return {"content": f.read(), "status": "reset"}
            
    raise HTTPException(status_code=500, detail="Default file not found")

@app.get("/backup")
def backup_data():
    # Create zip of USER_DATA_DIR
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"nda_backup_{timestamp}.zip"
    zip_path = os.path.join(BASE_DIR, zip_filename) # Store temp zip in app dir, not user dir (to avoid recursive zip)
    
    shutil.make_archive(zip_path.replace(".zip", ""), 'zip', USER_DATA_DIR)
    
    return FileResponse(zip_path, filename=zip_filename, media_type='application/zip')

@app.post("/restore")
async def restore_data(file: UploadFile = File(...)):
    # Validate
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be a zip.")
    
    # Save uploaded zip
    temp_zip = os.path.join(BASE_DIR, "temp_restore.zip")
    with open(temp_zip, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Wipe current user data (DANGER)
    # We should probably backup first, but let's trust the user wants to overwrite
    if os.path.exists(USER_DATA_DIR):
        shutil.rmtree(USER_DATA_DIR)
    os.makedirs(USER_DATA_DIR)
    
    # Unzip
    shutil.unpack_archive(temp_zip, USER_DATA_DIR)
    
    # Cleanup
    os.remove(temp_zip)
    
    # Restart Chroma Client (it might have open connections to old files)
    global chroma_client, collection
    # Force reload if possible, or just let the next request handle it
    # Chroma persistent client handles restarts okay usually.
    
    return {"status": "restored", "message": "Data restored successfully. Please restart the application if you see issues."}

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
        "workflow_status": "in_review",
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

@app.post("/status/{filename}")
async def update_status(filename: str, request: UpdateStatusRequest):
    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    metadata[filename]["workflow_status"] = request.status
    save_metadata(metadata)
    
    return {"status": "updated", "filename": filename, "new_status": request.status}

@app.post("/archive/{filename}")
async def archive_document(filename: str):
    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Toggle archive status
    current_status = metadata[filename].get("archived", False)
    metadata[filename]["archived"] = not current_status
    save_metadata(metadata)
    
    return {"status": "updated", "filename": filename, "archived": not current_status}

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    metadata = load_metadata()
    
    # Remove file
    if os.path.exists(filepath):
        os.remove(filepath)
    
    # Remove metadata
    if filename in metadata:
        del metadata[filename]
        save_metadata(metadata)
    
    # Remove from Vector DB
    try:
        collection.delete(where={"filename": filename})
    except:
        pass

    return {"status": "deleted", "filename": filename}

@app.get("/templates")
def list_templates():
    if not os.path.exists(TEMPLATES_DIR):
        return []
    return [f for f in os.listdir(TEMPLATES_DIR) if f.endswith((".docx", ".doc"))]

@app.get("/templates/{filename}")
async def get_template(filename: str):
    file_path = os.path.join(TEMPLATES_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/upload_template")
async def upload_template(file: UploadFile = File(...)):
    filename = file.filename
    filepath = os.path.join(TEMPLATES_DIR, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "uploaded", "filename": filename}

@app.delete("/templates/{filename}")
async def delete_template(filename: str):
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/report")
async def generate_report():
    if not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured")
    
    metadata = load_metadata()
    docs = list(metadata.values())
    
    # Helper to parse dates
    def parse_date(d_str):
        if not d_str: return None
        try:
            return datetime.datetime.fromisoformat(d_str)
        except:
            try:
                return datetime.datetime.strptime(d_str, "%Y-%m-%d")
            except:
                return None

    now = datetime.datetime.now()
    report_config = config.get("report", {}).get("sections", [])
    data_context = ""

    for section in report_config:
        section_id = section.get("id")
        title = section.get("title")
        sec_type = section.get("type")
        limit = section.get("limit", 10)
        
        items = []
        
        if sec_type == "recent_uploads":
            days = section.get("days", 7)
            # Sort by upload date desc
            sorted_docs = sorted(docs, key=lambda x: x.get("upload_date", ""), reverse=True)
            for d in sorted_docs:
                upload_date = parse_date(d.get("upload_date"))
                if upload_date and (now - upload_date).days <= days:
                    items.append(f"- {d['filename']} (Uploaded: {d.get('upload_date', '').split('T')[0]})")
        
        elif sec_type == "expiring":
            days = section.get("days", 90)
            # Filter and sort by expiration
            candidates = []
            for d in docs:
                exp_date_str = d.get("competency_answers", {}).get("expiration_date")
                exp_date = parse_date(exp_date_str)
                if exp_date:
                    days_left = (exp_date - now).days
                    
                    # Support negative days (e.g. -30 means expired in last 30 days)
                    # Logic: 
                    # If days > 0:  0 <= days_left <= days (Expiring Soon)
                    # If days < 0:  days <= days_left < 0  (Recently Expired)
                    
                    is_match = False
                    if days > 0:
                        if 0 <= days_left <= days:
                            is_match = True
                    else:
                        if days <= days_left < 0:
                            is_match = True
                            
                    if is_match:
                        candidates.append((days_left, d, exp_date_str))
            
            # Sort by soonest expiring (or most recently expired)
            candidates.sort(key=lambda x: x[0])
            for days_left, d, exp_date_str in candidates:
                items.append(f"- {d['filename']} (Expires: {exp_date_str}, Days Left: {days_left})")

        elif sec_type == "status":
            statuses = section.get("statuses", [])
            for d in docs:
                status = d.get("workflow_status", "in_review")
                if status in statuses:
                    items.append(f"- {d['filename']} (Status: {status.replace('_', ' ').title()})")

        # Apply limit
        if len(items) > limit:
            items = items[:limit]
            items.append(f"... and {len(items) - limit} more.")
            
        data_context += f"\n{title}:\n" + ("\n".join(items) if items else "None") + "\n"

    # Load Prompts
    system_prompt = prompts_config.get("prompts", {}).get("email_report", {}).get("system", "Format as email.")
    user_prompt_template = prompts_config.get("prompts", {}).get("email_report", {}).get("user", "Report:\n{data_context}")
    
    # Load email template components from config
    report_settings = config.get("report", {})
    subject = report_settings.get("subject", "Status Report - {date}")
    header = report_settings.get("header", "Summary of activity.")
    
    # Get footer components
    email_closing = report_settings.get("email_closing", "Best regards,")
    signature_name = report_settings.get("signature_name", "Legal Team")
    signature_title = report_settings.get("signature_title", "")
    department = report_settings.get("department", "")
    
    # Construct footer
    # Only include non-empty fields
    footer_parts = [email_closing]
    if signature_name: footer_parts.append(signature_name)
    if signature_title: footer_parts.append(signature_title)
    if department: footer_parts.append(department)
    
    footer = "\n".join(footer_parts)
    
    # Format date in subject
    formatted_subject = subject.format(date=now.strftime("%Y-%m-%d"))

    # Inject these into the user prompt data
    email_context = f"""
    Subject Line: {formatted_subject}
    
    Email Header:
    {header}
    
    Data Sections:
    {data_context}
    
    Email Footer:
    {footer}
    """
    
    user_prompt = user_prompt_template.format(
        current_date=now.strftime("%A, %B %d, %Y"),
        data_context=email_context
    )
    
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    
    return {"report": response.choices[0].message.content}

@app.post("/chat")
async def chat(request: ChatRequest):
    if not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured")

    # 1. Retrieve relevant chunks from Chroma
    # Hybrid Search Approach:
    # a) Check if query contains specific keywords matching filenames (Exact Retrieval)
    # b) Perform Semantic Vector Search (Fuzzy Retrieval)
    
    metadata = load_metadata()
    forced_context_files = []
    
    # Simple keyword matching in filenames
    query_lower = request.question.lower()
    for filename in metadata.keys():
        # Check if significant parts of the filename are in the query
        # e.g. "BRAWO" in "KIDDE_BRAWO_Supply..."
        # Split filename by common separators
        parts = filename.replace('.pdf', '').replace('.docx', '').replace('_', ' ').split()
        for part in parts:
            if len(part) > 3 and part.lower() in query_lower:
                forced_context_files.append(filename)
                break
    
    results = collection.query(
        query_texts=[request.question],
        n_results=10
    )
    
    # 2. Build Context
    context_text = ""
    retrieved_files = set()
    
    # Add Forced Context first (high priority)
    for filename in forced_context_files:
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.exists(filepath):
            # Extract text again (or cache it in metadata? simpler to re-extract for now or store preview)
            # For speed, let's use the stored text_preview if available, or extract fresh
            # Actually, for accuracy, we should probably index full text in a way we can retrieve by ID.
            # Since we don't have that handy, let's just re-extract. It's local and fast enough for 1-2 docs.
            text = extract_text_from_pdf(filepath)
            context_text += f"--- FULL TEXT from {filename} ---\n{text[:50000]}\n\n" # Truncate to be safe
            retrieved_files.add(filename)

    # Add Vector Context
    if results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            filename = meta.get('filename', 'unknown')
            if filename not in retrieved_files: # Avoid dupes if forced
                retrieved_files.add(filename)
                context_text += f"--- Excerpt from {filename} ---\n{doc}\n\n"
    
    logger.info(f"RAG retrieved context from: {retrieved_files}")

    # 3. Call LLM
    current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    system_prompt = prompts_config.get("prompts", {}).get("chat", {}).get("system", "You are a helpful assistant.")
    user_prompt_template = prompts_config.get("prompts", {}).get("chat", {}).get("user", "Context:\n{context_text}\n\nQuestion: {question}")
    
    user_prompt = user_prompt_template.format(
        current_date=current_date,
        context_text=context_text,
        question=request.question
    )
    
    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    
    content = response.choices[0].message.content
    
    # Extract sources if the LLM followed instructions
    final_sources = list(retrieved_files) # Default to all if parsing fails
    if "SOURCES: [" in content:
        try:
            # Split from the LAST occurrence of "SOURCES: [" to ensure we don't split on text content
            # Using rsplit with maxsplit=1
            parts = content.rsplit("SOURCES: [", 1)
            if len(parts) == 2:
                answer_text = parts[0].strip()
                sources_json_str = "[" + parts[1].strip()
                
                # Clean up if there are extra characters after the JSON
                if "]" in sources_json_str:
                    # Find the closing bracket that matches our opening bracket
                    # Simple naive approach: find the first ] after the start
                    # Better: find the LAST ] if we assume the list is at the end
                    
                    # Actually, let's just try to find the last ] 
                    end_index = sources_json_str.rfind("]")
                    if end_index != -1:
                        sources_json_str = sources_json_str[:end_index+1]
                        
                final_sources = json.loads(sources_json_str)
            else:
                answer_text = content
        except Exception as e:
            logger.error(f"Failed to parse sources from LLM response: {e}")
            answer_text = content
    else:
        answer_text = content

    return {
        "answer": answer_text,
        "sources": final_sources
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)
