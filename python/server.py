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
import webbrowser  # Ensure stdlib module is loaded for PyInstaller
import subprocess
import time
from typing import List, Dict, Optional, Any

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastmcp import FastMCP
from openai import OpenAI
from dotenv import load_dotenv
from platformdirs import user_config_dir

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
APP_NAME = os.environ.get("APP_NAME", "DocuSenseLM")
MCP_OCR_URL = os.environ.get("MCP_OCR_URL", "http://localhost:7001")
MCP_RAG_URL = os.environ.get("MCP_RAG_URL", "http://localhost:7002")
MCP_LLM_URL = os.environ.get("MCP_LLM_URL", "http://localhost:7003")
MCP_START_SERVERS = os.environ.get("MCP_START_SERVERS", "1") == "1"

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
    global openai_client

    api_key = get_api_key()

    if not api_key:
        logger.warning("No OpenAI API key found in environment or config")
        openai_client = None
        return False

    try:
        openai_client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        openai_client = None
        return False

openai_client = None
mcp_processes: List[subprocess.Popen] = []

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


@app.on_event("startup")
def ensure_mcp_on_start():
    ensure_mcp_server(
        name="MCP OCR",
        module="mcp_ocr_server.main",
        url=MCP_OCR_URL,
        port_env="MCP_OCR_PORT",
        default_port=MCP_OCR_URL.rsplit(":", 1)[-1],
        health_path="/health",
        method="GET",
    )
    ensure_mcp_server(
        name="MCP RAG",
        module="mcp_rag_server.main",
        url=MCP_RAG_URL,
        port_env="MCP_RAG_PORT",
        default_port=MCP_RAG_URL.rsplit(":", 1)[-1],
        health_path="/health",
        method="GET",
    )
    ensure_mcp_server(
        name="MCP LLM",
        module="mcp_llm_server.main",
        url=MCP_LLM_URL,
        port_env="MCP_LLM_PORT",
        default_port=MCP_LLM_URL.rsplit(":", 1)[-1],
        health_path="/health",
        method="GET",
    )


@app.on_event("shutdown")
def shutdown_mcp():
    for proc in mcp_processes:
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in mcp_processes:
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

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

def require_openai():
    if not openai_client or not openai_client.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured")


def call_mcp_ocr_pdf(filepath: str) -> List[str]:
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    with open(filepath, "rb") as f:
        files = {"file": (os.path.basename(filepath), f, "application/pdf")}
        try:
            resp = httpx.post(f"{MCP_OCR_URL}/ocr_pdf", files=files, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data.get("pages", [])
        except Exception as e:
            logger.error(f"OCR failed for {filepath}: {e}")
            raise HTTPException(status_code=500, detail=f"OCR failed: {e}")


def call_mcp_ocr_snippet(filepath: str) -> str:
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    with open(filepath, "rb") as f:
        files = {"file": (os.path.basename(filepath), f, "application/pdf")}
        try:
            resp = httpx.post(f"{MCP_OCR_URL}/classify_snippet", files=files, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data.get("snippet", "")
        except Exception as e:
            logger.error(f"OCR snippet failed for {filepath}: {e}")
            raise HTTPException(status_code=500, detail=f"OCR snippet failed: {e}")


def call_mcp_llm_classify_extract(text: str, capture_fields: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    try:
        resp = httpx.post(
            f"{MCP_LLM_URL}/classify_and_extract",
            json={"text": text, "capture_fields": capture_fields},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"LLM classify/extract failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM classify/extract failed: {e}")


def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    for k, v in metadata.items():
        if isinstance(v, list):
            sanitized[k] = "; ".join([str(x) for x in v])
        elif isinstance(v, dict):
            sanitized[k] = json.dumps(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            sanitized[k] = v
        else:
            sanitized[k] = str(v)
    return sanitized


def call_mcp_rag_ingest(filename: str, text: str, metadata: Dict[str, Any], chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
    payload = {
        "doc_id": filename,
        "filename": filename,
        "text": text,
        "metadata": _sanitize_metadata(metadata),
    }
    if chunk_size is not None:
        payload["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        payload["chunk_overlap"] = chunk_overlap
    try:
        resp = httpx.post(f"{MCP_RAG_URL}/ingest", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"RAG ingest failed for {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"RAG ingest failed: {e}")


def call_mcp_rag_query(question: str, n: int = 10):
    try:
        resp = httpx.post(
            f"{MCP_RAG_URL}/query",
            json={"query": question, "n": n},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")


def ensure_mcp_server(
    name: str,
    module: str,
    url: str,
    port_env: str,
    default_port: str,
    health_path: str = "/health",
    method: str = "GET",
):
    """Ensure MCP server is running; start if not reachable. No fallbacks."""
    try:
        if method == "POST":
            resp = httpx.post(f"{url}{health_path}", json={}, timeout=5)
        else:
            resp = httpx.get(f"{url}{health_path}", timeout=5)
        if resp.status_code < 500:
            logger.info(f"{name} already running at {url}")
            return
    except Exception:
        logger.info(f"{name} not reachable; attempting to start...")

    if not MCP_START_SERVERS:
        raise RuntimeError(f"{name} is not running and MCP_START_SERVERS=0")

    # Detect if we're in a packaged app and adjust paths accordingly
    is_packaged = (
        'win-unpacked' in os.getcwd() or
        'resources' in os.getcwd() or
        hasattr(sys, '_MEIPASS') or
        getattr(sys, 'frozen', False)
    )
    if is_packaged:
        # Packaged app: use bundled Python executable and resources path
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller
            app_path = sys._MEIPASS
            python_exe = os.path.join(app_path, "python", "python_embed", "python.exe")
        else:
            # Other packagers (like Electron with python_embed)
            app_path = os.path.dirname(sys.executable)
            python_exe = os.path.join(app_path, "resources", "python", "python_embed", "python.exe")
        
        if not os.path.exists(python_exe):
            # Fallback: look for python.exe in resources
            python_exe = os.path.join(app_path, "resources", "python", "python_embed", "python.exe")
        
        python_path = os.path.join(app_path, "resources", "python")
        working_dir = os.path.join(app_path, "resources")
    else:
        # Development: use current Python and paths
        python_exe = sys.executable
        python_path = os.path.join(BASE_DIR, "python")
        working_dir = BASE_DIR

    env = os.environ.copy()
    env["PYTHONPATH"] = python_path
    env[port_env] = default_port
    
    # Log startup attempt for debugging
    logger.info(f"Starting {name} with python={python_exe}, cwd={working_dir}, module={module}")
    
    try:
        # Detect if we're running in a packaged Electron app
        is_packaged = (
            'win-unpacked' in working_dir or
            'resources' in working_dir or
            hasattr(sys, '_MEIPASS') or
            getattr(sys, 'frozen', False)
        )

        if is_packaged:
            # For packaged apps, run the main.py file directly
            module_path = os.path.join(python_path, module.replace(".", os.sep) + ".py")
            if not os.path.exists(module_path):
                raise FileNotFoundError(f"Module file not found: {module_path}")
            cmd = [python_exe, module_path]
        else:
            # Development mode: use -m flag
            cmd = [python_exe, "-m", module]

        proc = subprocess.Popen(
            cmd,
            cwd=working_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        mcp_processes.append(proc)
    except Exception as e:
        logger.error(f"Failed to start {name}: {e}")
        raise RuntimeError(f"Failed to start {name}: {e}")

    deadline = time.time() + 120
    while time.time() < deadline:
        # Check if process died
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            logger.error(f"{name} process exited with code {proc.returncode}")
            logger.error(f"{name} stdout: {stdout.decode()}")
            logger.error(f"{name} stderr: {stderr.decode()}")
            raise RuntimeError(f"{name} process failed to start")
            
        try:
            if method == "POST":
                resp = httpx.post(f"{url}{health_path}", json={}, timeout=5)
            else:
                resp = httpx.get(f"{url}{health_path}", timeout=5)
            if resp.status_code < 500:
                logger.info(f"{name} started at {url}")
                return
        except Exception:
            pass
        time.sleep(2)

    # If we get here, the process might still be running but not responding
    if proc.poll() is None:
        try:
            stdout, stderr = proc.communicate(timeout=5)
            logger.error(f"{name} timeout - stdout: {stdout.decode()}")
            logger.error(f"{name} timeout - stderr: {stderr.decode()}")
        except subprocess.TimeoutExpired:
            logger.error(f"{name} timeout - process still running but not responding")
    
    raise RuntimeError(f"{name} failed to start at {url} within timeout")

async def process_document_background(filename: str, filepath: str, doc_type_hint: str):
    logger.info(f"Processing {filename} via MCP...")

    pages = call_mcp_ocr_pdf(filepath)
    full_text = "\n".join(pages)
    if not full_text.strip():
        logger.warning(f"No text extracted from {filename}")
        return

    snippet = pages[0] if pages else call_mcp_ocr_snippet(filepath)
    capture_fields = config.get("document_types", {}).get(doc_type, {}).get("capture_fields", [])
    classification = call_mcp_llm_classify_extract(snippet or full_text, capture_fields=capture_fields)
    doc_type = classification.get("classification", {}).get("doc_type", doc_type_hint)
    extraction = classification.get("extraction", {})

    ingest_cfg = config.get("document_types", {}).get(doc_type, {}).get("ingest", {})
    chunk_size = ingest_cfg.get("chunk_size")
    chunk_overlap = ingest_cfg.get("chunk_overlap")
    column_detection = ingest_cfg.get("column_detection")

    # Ingest into RAG MCP with metadata
    metadata_payload = {
        "doc_type": doc_type,
        "column_detection": column_detection,
        **extraction,
    }
    call_mcp_rag_ingest(filename, full_text, metadata_payload, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # Update metadata locally
    metadata = load_metadata()
    if filename in metadata:
        metadata[filename]["status"] = "processed"
        metadata[filename]["doc_type"] = doc_type
        metadata[filename]["extraction"] = extraction
        metadata[filename]["competency_answers"] = extraction
        save_metadata(metadata)
    
    logger.info(f"Finished processing {filename}")

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


@app.post("/documents/{filename}/doc_type")
async def update_doc_type(filename: str, request: UpdateDocTypeRequest, background_tasks: BackgroundTasks):
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    allowed_types = set((config or {}).get("document_types", {}).keys())
    if request.doc_type not in allowed_types and request.doc_type.lower() != "auto":
        raise HTTPException(status_code=400, detail="Invalid doc_type")

    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="Metadata not found")

    metadata[filename]["doc_type"] = request.doc_type
    metadata[filename]["status"] = "reprocessing"
    save_metadata(metadata)

    # Re-run processing with the new doc_type hint
    background_tasks.add_task(process_document_background, filename, filepath, request.doc_type)

    return {"status": "updated", "filename": filename, "doc_type": request.doc_type}

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
    if not openai_client or not openai_client.api_key:
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
    require_openai()

    metadata = load_metadata()
    forced_context_files = []
    query_lower = request.question.lower()
    for filename in metadata.keys():
        parts = filename.replace('.pdf', '').replace('.docx', '').replace('_', ' ').split()
        for part in parts:
            if len(part) > 3 and part.lower() in query_lower:
                forced_context_files.append(filename)
                break

    rag_results = call_mcp_rag_query(request.question, n=10)
    vector_results = rag_results.get("results", [])

    context_text = ""
    retrieved_files = set()

    for filename in forced_context_files:
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.exists(filepath):
            text_pages = call_mcp_ocr_pdf(filepath)
            text = "\n".join(text_pages)
            context_text += f"--- FULL TEXT from {filename} ---\n{text[:50000]}\n\n"
            retrieved_files.add(filename)

    for result in vector_results:
        doc_text = result.get("text", "")
        meta = result.get("metadata", {})
        filename = meta.get("filename", "unknown")
        if filename not in retrieved_files:
            retrieved_files.add(filename)
            context_text += f"--- Excerpt from {filename} ---\n{doc_text}\n\n"

    logger.info(f"RAG retrieved context from: {retrieved_files}")

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

    final_sources = list(retrieved_files)
    if "SOURCES: [" in content:
        try:
            parts = content.rsplit("SOURCES: [", 1)
            if len(parts) == 2:
                answer_text = parts[0].strip()
                sources_json_str = "[" + parts[1].strip()
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
