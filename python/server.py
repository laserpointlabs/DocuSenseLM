import os
# Disable ChromaDB telemetry (must be set before importing chromadb)
os.environ["ANONYMIZED_TELEMETRY"] = "False"
import sys
import yaml
import json
import uvicorn
import logging
import shutil
import datetime
import pickletools
import diskcache
import webbrowser  # Ensure stdlib module is loaded for PyInstaller
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

# Load configuration first to get BASE_DIR
# Get the correct base directory (project root)
# Electron may set working directory to python/ folder, so we need to go up one level
if getattr(sys, '_MEIPASS', False):
    # Running in PyInstaller bundle
    BASE_DIR = os.path.dirname(sys._MEIPASS)
else:
    # Running in development - find project root from __file__
    current_dir = os.getcwd()
    if os.path.basename(current_dir) == 'python':
        # We're in the python subdirectory, go up one level
        BASE_DIR = os.path.dirname(current_dir)
    else:
        # We're in the project root
        BASE_DIR = current_dir

logger.info(f"BASE_DIR resolved to: {BASE_DIR}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"__file__ path: {__file__}")

# OCR imports (optional - will gracefully degrade if not available)
OCR_AVAILABLE = False
OCR_READER = None

try:
    import easyocr
    import fitz  # PyMuPDF - for PDF to image conversion without poppler
    OCR_AVAILABLE = True
    # Initialize EasyOCR reader (English only for now)
    # Models are stored in tools/easyocr_models/
    OCR_READER = None  # Will be initialized on first use
    logger.info("OCR libraries (easyocr, PyMuPDF) loaded successfully")
except ImportError as e:
    OCR_AVAILABLE = False
    OCR_READER = None
    logger.warning(f"OCR libraries not available: {e}")

# Log OCR availability status
if not OCR_AVAILABLE:
    logger.warning("Scanned PDFs will not be processed (OCR unavailable)")
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
APP_NAME = os.environ.get("APP_NAME", "DocuSenseLM")

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
    config_default_path = os.path.join(BASE_DIR, "config.default.yaml")
    if os.path.exists(config_default_path):
        shutil.copy(config_default_path, os.path.join(USER_DATA_DIR, "config.yaml"))
    else:
        logger.warning(f"config.default.yaml not found at {config_default_path}, skipping copy")

if not os.path.exists(os.path.join(USER_DATA_DIR, "prompts.yaml")):
    prompts_default_path = os.path.join(BASE_DIR, "prompts.default.yaml")
    if os.path.exists(prompts_default_path):
        shutil.copy(prompts_default_path, os.path.join(USER_DATA_DIR, "prompts.yaml"))
    else:
        logger.warning(f"prompts.default.yaml not found at {prompts_default_path}, skipping copy")

# Function to get API key from config or environment
def get_api_key():
    # Priority 1: Environment variable
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key
    
    # Priority 2: Config file
    if config and "api" in config and "openai_api_key" in config["api"]:
        config_key = config["api"]["openai_api_key"]
        if config_key and config_key.strip():
            return config_key.strip()
    
    return None

# Function to initialize or reinitialize OpenAI client
def initialize_openai_client():
    global openai_client, openai_ef, collection
    
    api_key = get_api_key()
    
    if not api_key:
        logger.warning("No OpenAI API key found in environment or config")
        openai_client = None
        openai_ef = None
        collection = None
        return False
    
    try:
        # Initialize OpenAI client with timeout to prevent hanging
        openai_client = OpenAI(api_key=api_key, timeout=60.0)
        logger.info("OpenAI client initialized successfully with 60s timeout")
        
        # Initialize ChromaDB with OpenAI embeddings
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small"
        )
        collection = chroma_client.get_or_create_collection(
            name="nda_documents",
            embedding_function=openai_ef
        )
        logger.info("ChromaDB collection initialized with OpenAI embeddings")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        openai_client = None
        openai_ef = None
        collection = None
        return False

# Initialize ChromaDB (without embeddings initially)
chroma_client = chromadb.PersistentClient(path=DB_DIR)
openai_client = None
openai_ef = None
collection = None

# Try to initialize OpenAI
initialize_openai_client()

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

def is_scanned_pdf(filepath):
    """
    Detect if a PDF is scanned (image-based) or text-based.
    Returns True if scanned, False if text-based.
    """
    try:
        reader = PdfReader(filepath)
        total_text_length = 0
        
        # Check first few pages to determine document type
        pages_to_check = min(3, len(reader.pages))
        if pages_to_check == 0:
            return True  # No pages, assume scanned
        
        text_samples = []
        for i in range(pages_to_check):
            page = reader.pages[i]
            page_text = page.extract_text()
            if page_text:
                text_samples.append(page_text.strip())
                total_text_length += len(page_text.strip())
        
        combined_text = " ".join(text_samples).strip()
        
        # Heuristics for scanned PDF detection:
        # 1. Very little text (< 100 chars per page on average)
        avg_text_per_page = total_text_length / pages_to_check if pages_to_check > 0 else 0
        
        # 2. Text is mostly metadata (DocuSign, envelope IDs, signatures only)
        is_mostly_metadata = (
            len(combined_text) < 500 or 
            (len(combined_text) < 1000 and ('DocuSign' in combined_text or 'Envelope ID' in combined_text))
        )
        
        # If average text per page is very low (< 100 chars) or mostly metadata, it's scanned
        is_scanned = avg_text_per_page < 100 or is_mostly_metadata
        
        logger.info(f"PDF type detection for {filepath}: avg_text_per_page={avg_text_per_page:.0f}, is_mostly_metadata={is_mostly_metadata}, detected_as_scanned={is_scanned}")
        
        return is_scanned
        
    except Exception as e:
        logger.error(f"Error detecting PDF type for {filepath}: {e}")
        # If detection fails, assume it might be scanned
        return True

def extract_text_from_pdf(filepath):
    """
    Extract text from PDF, handling both native PDFs and scanned PDFs.
    Detects document type first, then uses appropriate extraction method.
    """
    # Detect if PDF is scanned or text-based
    requires_ocr = is_scanned_pdf(filepath)
    
    if requires_ocr:
        # Scanned PDF - use OCR
        if OCR_AVAILABLE:
            try:
                logger.info(f"Detected scanned PDF - using OCR for {filepath}")
                
                # Initialize EasyOCR reader on first use
                global OCR_READER
                if OCR_READER is None:
                    # Set model directory to tools/easyocr_models if it exists
                    model_dir = os.path.join(BASE_DIR, "tools", "easyocr_models")
                    if os.path.exists(model_dir):
                        logger.info(f"Using EasyOCR models from {model_dir}")
                        OCR_READER = easyocr.Reader(['en'], model_storage_directory=model_dir)
                    else:
                        logger.info("Using default EasyOCR model location")
                        OCR_READER = easyocr.Reader(['en'])
                
                # Convert all PDF pages to images for OCR using PyMuPDF
                ocr_text = ""
                pdf_doc = fitz.open(filepath)
                total_pages = len(pdf_doc)
                logger.info(f"Opened PDF with {total_pages} pages for OCR processing")
                
                pages_processed = 0
                pages_failed = 0
                total_chars_extracted = 0
                
                for page_num in range(total_pages):
                    logger.info(f"Processing page {page_num+1}/{total_pages} with EasyOCR")
                    try:
                        page = pdf_doc[page_num]
                        # Render page to image at 300 DPI for better accuracy
                        mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                        pix = page.get_pixmap(matrix=mat)
                        
                        # Convert to numpy array for EasyOCR
                        import numpy as np
                        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                        # Convert RGBA to RGB if needed
                        if pix.n == 4:
                            img_array = img_array[:, :, :3]
                        
                        # Perform OCR on the page
                        result = OCR_READER.readtext(img_array)
                        page_text = "\n".join([detection[1] for detection in result if len(detection) > 1])
                        
                        # Accumulate text with page separator
                        if page_text.strip():
                            ocr_text += f"\n--- Page {page_num+1} ---\n{page_text}\n"
                            total_chars_extracted += len(page_text)
                            logger.info(f"Page {page_num+1}/{total_pages} OCR extracted {len(page_text)} characters")
                        else:
                            logger.warning(f"Page {page_num+1}/{total_pages} OCR returned no text")
                        
                        pages_processed += 1
                        
                        # Clean up pixmap to free memory
                        pix = None
                        
                    except Exception as e:
                        pages_failed += 1
                        logger.error(f"Error processing page {page_num+1}/{total_pages} with OCR: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        # Continue processing remaining pages even if one fails
                        continue
                
                pdf_doc.close()
                
                ocr_text_stripped = ocr_text.strip()
                logger.info(f"OCR processing complete: {pages_processed}/{total_pages} pages processed, {pages_failed} failed, {len(ocr_text_stripped)} total characters extracted")
                
                # Return text even if minimal - let the indexing decide if it's useful
                # Previously we returned empty string if < 50 chars, which prevented indexing
                if ocr_text_stripped:
                    logger.info(f"OCR extracted {len(ocr_text_stripped)} characters from scanned PDF {filepath}")
                    return ocr_text_stripped
                else:
                    logger.warning(f"OCR returned no text for {filepath} after processing {total_pages} pages")
                    return ""
            except Exception as e:
                logger.error(f"OCR failed for {filepath}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return ""
        else:
            logger.error(f"Scanned PDF detected but OCR not available for {filepath}")
            return ""
    else:
        # Text-based PDF - use regular extraction
        logger.info(f"Detected text-based PDF - using regular extraction for {filepath}")
        text = ""
        try:
            reader = PdfReader(filepath)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            logger.info(f"Regular extraction got {len(text.strip())} characters from text PDF {filepath}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from {filepath}: {e}")
            return ""

def index_document(filename: str, text: str):
    """
    Index document text into ChromaDB vector store.
    Ensures all text is properly chunked and indexed.
    """
    if not text or not text.strip():
        logger.warning(f"Attempted to index empty text for {filename}")
        return
    
    if collection is None:
        logger.error(f"Cannot index {filename}: ChromaDB collection not initialized")
        return
    
    try:
        # Split text into chunks
        # Larger chunks preserve more context for semantic search
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,  # Increased from 1000 to preserve more context
            chunk_overlap=400,  # Increased overlap to ensure important info isn't split
            length_function=len,
        )
        chunks = text_splitter.split_text(text)
        
        if not chunks:
            logger.warning(f"No chunks created from text for {filename}")
            return
        
        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters for {filename}")
        
        # Prepare for Chroma
        ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"filename": filename, "chunk_index": i} for i in range(len(chunks))]
        
        # Delete existing chunks for this file to avoid duplication
        try:
            # Get existing chunks to check count (collection.count() doesn't support where)
            existing = collection.get(where={"filename": filename}, include=[])
            existing_count = len(existing['ids']) if existing and existing.get('ids') else 0
            if existing_count > 0:
                logger.info(f"Deleting {existing_count} existing chunks for {filename}")
                collection.delete(where={"filename": filename})
        except Exception as e:
            logger.warning(f"Error deleting existing chunks for {filename}: {e}")
            # Continue anyway - upsert will handle duplicates
        
        # Upsert all chunks
        collection.upsert(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )
        
        # Verify indexing - use get() instead of count() with where clause
        verify_result = collection.get(where={"filename": filename}, include=[])
        verify_count = len(verify_result['ids']) if verify_result and verify_result.get('ids') else 0
        logger.info(f"Successfully indexed {verify_count} chunks for {filename} (expected {len(chunks)})")
        
        if verify_count != len(chunks):
            logger.warning(f"Chunk count mismatch for {filename}: expected {len(chunks)}, got {verify_count}")
            
    except Exception as e:
        logger.error(f"Error indexing document {filename}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def process_document_background(filename: str, filepath: str, doc_type: str):
    """
    Process document in background. FastAPI BackgroundTasks handles async functions correctly.
    """
    logger.info(f"=== STARTING BACKGROUND PROCESSING FOR {filename} ===")
    logger.info(f"Filepath: {filepath}")
    logger.info(f"Doc type: {doc_type}")

    # Update status to processing
    metadata = load_metadata()
    if filename in metadata:
        metadata[filename]["status"] = "processing"
        save_metadata(metadata)
        logger.info(f"Status set to 'processing' for {filename}")
    else:
        logger.warning(f"Filename {filename} not found in metadata when starting processing")

    try:
        logger.info(f"Step 1: Extracting text from PDF {filename}")
        text = extract_text_from_pdf(filepath)
        logger.info(f"Step 1 complete: Extracted {len(text) if text else 0} characters")

        # Initialize metadata early to ensure document is visible
        metadata = load_metadata()
        if filename not in metadata:
            logger.warning(f"Metadata not found for {filename}, creating entry")
            metadata[filename] = {
                "filename": filename,
                "doc_type": doc_type,
                "upload_date": datetime.datetime.now().isoformat(),
                "status": "processing",  # Should already be set, but ensure it
                "workflow_status": "in_review",
                "competency_answers": {}
            }
        
        # Track if we have extractable text - lowered threshold to allow shorter OCR results
        # OCR can produce valid but short text, so we index anything with meaningful content
        text_stripped = text.strip() if text else ""
        has_text = bool(text_stripped and len(text_stripped) > 10)  # Lowered from 50 to 10
        
        if not has_text:
            logger.warning(f"No meaningful text extracted from {filename} ({len(text_stripped)} chars) - document will be visible but not searchable")
            # Still update metadata to mark as processed (even if without text)
            metadata[filename]["status"] = "processed"
            metadata[filename]["text_extracted"] = False
            metadata[filename]["competency_answers"] = {}
            save_metadata(metadata)
            logger.info(f"Finished processing {filename} (no text extracted)")
            return

        # 1. Index into Vector Store (only if we have text)
        logger.info(f"Step 2: Indexing {len(text_stripped)} characters of text for {filename}")
        indexing_successful = False
        try:
            index_document(filename, text_stripped)
            indexing_successful = True
            logger.info(f"Step 2 complete: Successfully indexed {filename}")
        except Exception as e:
            logger.error(f"Indexing failed for {filename}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            indexing_successful = False

        # 2. Run Competency Questions (only if we have text and API key)
        doc_config = config.get("document_types", {}).get(doc_type, {})
        # Support both old and new config field names
        questions = doc_config.get("competency_questions") or doc_config.get("capture_fields", [])
        answers = {}
        
        # Check if OpenAI client is initialized
        has_openai = openai_client is not None
        logger.info(f"Questions configured: {len(questions) if questions else 0}, OpenAI client available: {has_openai}")
        
        if questions and openai_client:
            system_prompt = prompts_config.get("prompts", {}).get("competency_extraction", {}).get("system", "You are a legal document assistant. Respond in JSON.")
            user_prompt_template = prompts_config.get("prompts", {}).get("competency_extraction", {}).get("user", "Analyze the text:\n{document_text}\n\nQuestions:\n{questions_list}")
            
            questions_list_str = "\n".join([f"- {q['id']}: {q['question']}" for q in questions])
            
            user_prompt = user_prompt_template.format(
                document_text=text[:100000],
                questions_list=questions_list_str
            )
            
            try:
                logger.info(f"Calling OpenAI API for competency extraction on {filename}")
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
                logger.info(f"OpenAI API call completed successfully for {filename}")
            except Exception as e:
                logger.error(f"LLM processing failed for {filename}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                answers = {}
                # Don't fail the whole process if LLM call fails - continue with empty answers
        else:
            if not questions:
                logger.info(f"No competency questions configured for doc_type '{doc_type}'")
            if not has_openai:
                logger.info(f"OpenAI API key not configured, skipping metadata extraction")
        
        # Update metadata - always mark as processed, even if extraction failed
        logger.info(f"Step 4: Updating final status to 'processed' for {filename}")
        # Reload metadata to ensure we have the latest version (in case it was modified elsewhere)
        metadata = load_metadata()
        if filename in metadata:
            metadata[filename]["status"] = "processed"
            metadata[filename]["competency_answers"] = answers
            # Set text_extracted based on whether indexing succeeded
            metadata[filename]["text_extracted"] = indexing_successful and has_text
            save_metadata(metadata)
            logger.info(f"=== COMPLETED PROCESSING FOR {filename} - Status set to 'processed', text_extracted={metadata[filename]['text_extracted']} ===")
        else:
            logger.error(f"CRITICAL: Metadata entry not found for {filename} when trying to update status")
        
        logger.info(f"=== FINISHED PROCESSING {filename} ===")
        
    except Exception as e:
        # Catch any unexpected errors and ensure status is updated
        logger.error(f"Unexpected error processing {filename}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Update status to processed even on error
        metadata = load_metadata()
        if filename in metadata:
            metadata[filename]["status"] = "processed"
            metadata[filename]["text_extracted"] = False
            save_metadata(metadata)

# --- Models ---

class ChatRequest(BaseModel):
    question: str

class UpdateStatusRequest(BaseModel):
    status: str

class UpdateDocTypeRequest(BaseModel):
    doc_type: str

# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.1", "rag": "enabled"}

@app.get("/config")
def get_config():
    # Reload config to ensure we have latest (in case it was changed)
    global config
    config = load_app_config()
    
    # Return config but mask the API key for security
    safe_config = dict(config)
    
    # Ensure api section exists
    if "api" not in safe_config:
        safe_config["api"] = {}
    
    # Get the actual API key being used (from config or environment)
    actual_key = get_api_key()
    
    # Handle API key masking
    if actual_key and len(actual_key) > 8:
        # Show first 4 and last 4 characters
        safe_config["api"]["openai_api_key_masked"] = f"{actual_key[:4]}...{actual_key[-4:]}"
        safe_config["api"]["openai_api_key_set"] = True
    else:
        safe_config["api"]["openai_api_key_masked"] = ""
        safe_config["api"]["openai_api_key_set"] = False
    
    # Remove the actual key from the response if it exists
    if "openai_api_key" in safe_config["api"]:
        del safe_config["api"]["openai_api_key"]
    
    return safe_config

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
    if filename == "config.yaml":
        config = load_app_config()
        # Reinitialize OpenAI client with potentially new API key
        initialize_openai_client()
    elif filename == "prompts.yaml":
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
    # Get show_on_dashboard default from config, default to True if not specified
    doc_type_config = config.get("document_types", {}).get(doc_type, {})
    show_on_dashboard = doc_type_config.get("show_on_dashboard", True)
    
    metadata[filename] = {
        "filename": filename,
        "doc_type": doc_type,
        "upload_date": datetime.datetime.now().isoformat(),
        "status": "pending",
        "workflow_status": "in_review",
        "show_on_dashboard": show_on_dashboard,
        "competency_answers": {}
    }
    save_metadata(metadata)
    
    # Process
    background_tasks.add_task(process_document_background, filename, filepath, doc_type)
    
    return {"status": "uploaded", "filename": filename}

@app.post("/reprocess/{filename}")
async def reprocess_document(filename: str, background_tasks: BackgroundTasks):
    logger.info(f"=== REPROCESS ENDPOINT CALLED FOR {filename} ===")
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        raise HTTPException(status_code=404, detail="File not found")
    
    metadata = load_metadata()
    if filename not in metadata:
        logger.error(f"Metadata not found for: {filename}")
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    # Update status
    logger.info(f"Setting status to 'reprocessing' for {filename}")
    metadata[filename]["status"] = "reprocessing"
    save_metadata(metadata)
    
    # Re-run processing
    doc_type = metadata[filename].get("doc_type", "nda")
    logger.info(f"Adding background task for {filename} (doc_type: {doc_type}, filepath: {filepath})")
    
    # Ensure the background task will execute - FastAPI BackgroundTasks handles async functions
    background_tasks.add_task(process_document_background, filename, filepath, doc_type)
    
    logger.info(f"Background task added successfully for {filename}, returning response")
    return {"status": "reprocessing_started", "filename": filename}

@app.post("/fix-stuck/{filename}")
async def fix_stuck_document(filename: str):
    """
    Manually fix a document that's stuck in 'processing' or 'reprocessing' status.
    This will mark it as 'processed' without re-running the processing.
    """
    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    current_status = metadata[filename].get("status")
    if current_status not in ["processing", "reprocessing"]:
        return {"status": "not_stuck", "message": f"Document is not stuck (current status: {current_status})"}
    
    metadata[filename]["status"] = "processed"
    save_metadata(metadata)
    logger.info(f"Manually fixed stuck document {filename} (was {current_status})")
    
    return {"status": "fixed", "filename": filename, "previous_status": current_status}

@app.post("/status/{filename}")
async def update_status(filename: str, request: UpdateStatusRequest):
    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="File not found")

    metadata[filename]["workflow_status"] = request.status
    save_metadata(metadata)

    return {"status": "updated", "filename": filename, "new_status": request.status}

@app.post("/type/{filename}")
async def update_doc_type(filename: str, request: UpdateDocTypeRequest):
    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="File not found")

    metadata[filename]["doc_type"] = request.doc_type
    save_metadata(metadata)

    return {"status": "updated", "filename": filename, "new_doc_type": request.doc_type}

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
        if collection is not None:
            collection.delete(where={"filename": filename})
            logger.info(f"Removed {filename} from vector database")
        else:
            logger.warning(f"Collection not initialized, skipping vector DB deletion for {filename}")
    except Exception as e:
        logger.error(f"Error removing {filename} from vector DB: {e}")
        # Don't fail deletion if vector DB removal fails

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
    if not openai_client:
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
    if not openai_client:
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
    
    # Perform vector search - OpenAI embeddings handle semantic matching
    logger.info(f"Searching vector database for: '{request.question}'")
    
    # For queries about specific services/pricing, retrieve more chunks to ensure we get the right one
    query_lower = request.question.lower()
    is_pricing_query = any(word in query_lower for word in ['pay', 'cost', 'price', 'fee', 'charge', 'hour', 'rate', 'per'])
    n_results = 15 if is_pricing_query else 5  # Retrieve more chunks for pricing queries
    
    results = collection.query(
        query_texts=[request.question],
        n_results=n_results,
        include=['documents', 'metadatas', 'distances']
    )
    
    num_chunks = len(results['documents'][0]) if results['documents'] and len(results['documents']) > 0 else 0
    logger.info(f"Vector search returned {num_chunks} chunks (is_pricing_query={is_pricing_query})")
    
    # 2. Build Context - Only include highly relevant chunks
    context_text = ""
    retrieved_files = set()
    
    # Add Forced Context first (high priority) - limit to 1 document
    for filename in forced_context_files[:1]:  # Only first forced file
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.exists(filepath):
            text = extract_text_from_pdf(filepath)
            context_text += f"--- FULL TEXT from {filename} ---\n{text[:50000]}\n\n"
            retrieved_files.add(filename)
            logger.info(f"Forced context: Added full text from {filename} ({len(text)} chars)")

    # Add Vector Context - filter by distance threshold
    # For cosine distance: lower is better (0 = identical, 1 = orthogonal)
    # OpenAI embeddings typically have distances 0.3-0.7 for good matches
    # 0.5 is too strict - increasing to 0.75 to include more relevant results
    DISTANCE_THRESHOLD = 0.75  # Include chunks with distance < 0.75
    
    # Initialize relevant_chunks outside the if block
    relevant_chunks = []
    query_keywords = set(word.lower() for word in request.question.split() if len(word) > 3)
    
    if results['documents'] and len(results['documents']) > 0:
        distances = results.get('distances', [[]])[0] if results.get('distances') else []
        logger.info(f"Processing {num_chunks} retrieved chunks with distances: {distances}")
        
        # Filter chunks by distance threshold and prioritize chunks with key terms
        
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i] if results['metadatas'] and len(results['metadatas']) > 0 and i < len(results['metadatas'][0]) else {}
            filename = meta.get('filename', 'unknown')
            distance = distances[i] if i < len(distances) else 999.0
            
            chunk_preview = doc[:150] if len(doc) > 150 else doc
            logger.info(f"Chunk {i+1}: distance={distance:.4f}, filename={filename[:40]}, preview: {chunk_preview}...")
            
            # Check if chunk contains key terms from query (boost relevance)
            doc_lower = doc.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw in doc_lower)
            has_price_info = any(term in doc_lower for term in ['$', 'dollar', 'per hour', 'per man', 'rate', 'cost', 'fee'])
            
            # For pricing queries, prioritize chunks with both the service term AND price info
            if is_pricing_query:
                has_service_term = any(kw in doc_lower for kw in query_keywords)
                if has_service_term and has_price_info:
                    # Boost this chunk by reducing its effective distance
                    effective_distance = distance * 0.7  # Boost chunks with both service and price
                    logger.info(f"  -> BOOSTED (has service term + price info, effective distance: {effective_distance:.4f})")
                else:
                    effective_distance = distance
            else:
                effective_distance = distance
            
            # Only include chunks below distance threshold
            if effective_distance < DISTANCE_THRESHOLD:
                relevant_chunks.append({
                    'doc': doc,
                    'filename': filename,
                    'distance': effective_distance,  # Use effective distance for sorting
                    'original_distance': distance,
                    'keyword_matches': keyword_matches,
                    'has_price_info': has_price_info
                })
                logger.info(f"  -> INCLUDED (effective distance {effective_distance:.4f} < threshold {DISTANCE_THRESHOLD}, keywords={keyword_matches}, has_price={has_price_info})")
            else:
                logger.info(f"  -> EXCLUDED (effective distance {effective_distance:.4f} >= threshold {DISTANCE_THRESHOLD})")
        
        # Sort by effective distance, then by keyword matches, then by price info
        relevant_chunks.sort(key=lambda x: (x['distance'], -x['keyword_matches'], -x['has_price_info']))
        
        # For pricing queries, include more chunks to ensure we get the right pricing info
        max_chunks = 5 if is_pricing_query else 3
        for chunk_info in relevant_chunks[:max_chunks]:
            filename = chunk_info['filename']
            
            # Skip if we already have this document from forced context
            if filename in retrieved_files:
                continue
            
            retrieved_files.add(filename)
            context_text += f"--- Excerpt from {filename} ---\n{chunk_info['doc']}\n\n"
            logger.info(f"Added chunk from {filename} (effective distance: {chunk_info['distance']:.4f}, original: {chunk_info['original_distance']:.4f})")
        
        logger.info(f"Final: Added {min(len(relevant_chunks), max_chunks)} chunks from {len(retrieved_files)} documents")
    else:
        logger.warning(f"No documents retrieved from vector search for query: '{request.question}'")
        relevant_chunks = []  # Initialize to avoid unbound variable
    
    logger.info(f"RAG retrieved context from {len(retrieved_files)} files: {retrieved_files}")
    logger.info(f"Total context length: {len(context_text)} characters")
    
    # Log the actual context being sent (truncated for readability)
    context_preview = context_text[:2000] if len(context_text) > 2000 else context_text
    logger.info(f"=== CONTEXT BEING SENT TO LLM (first 2000 chars) ===\n{context_preview}\n=== END CONTEXT PREVIEW ===")
    
    # Also log full context length and number of documents
    logger.info(f"=== RETRIEVAL SUMMARY ===")
    logger.info(f"  Query: '{request.question}'")
    logger.info(f"  Chunks retrieved: {num_chunks}")
    logger.info(f"  Chunks after filtering: {len(relevant_chunks) if 'relevant_chunks' in locals() else 0}")
    logger.info(f"  Documents included: {len(retrieved_files)}")
    logger.info(f"  Context size: {len(context_text)} chars")
    logger.info(f"  Files: {list(retrieved_files)}")
    
    # 3. Call LLM
    current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    system_prompt = prompts_config.get("prompts", {}).get("chat", {}).get("system", "You are a helpful assistant.")
    user_prompt_template = prompts_config.get("prompts", {}).get("chat", {}).get("user", "Context:\n{context_text}\n\nQuestion: {question}")
    
    user_prompt = user_prompt_template.format(
        current_date=current_date,
        context_text=context_text,
        question=request.question
    )
    
    logger.info(f"=== USER PROMPT BEING SENT (first 2000 chars) ===\n{user_prompt[:2000]}\n=== END USER PROMPT PREVIEW ===")
    
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
    print("Starting FastAPI server...")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
