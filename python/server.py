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
import tempfile
import asyncio
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Any, Tuple
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastmcp import FastMCP
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv
from platformdirs import user_config_dir
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nda-tool")

# --- Heavy dependency loading / initialization ---
# In packaged Windows builds, importing chromadb (and initializing persistent clients/collections)
# can take tens of seconds on some machines (AV scanning, many site-packages, SQLite init, etc.).
# If we do that at module import time, Uvicorn won't bind its port, and Electron will appear "stuck"
# because /health can't connect. We therefore lazy-import + initialize RAG in a background thread.
_chroma_import_lock = threading.Lock()
_chroma_init_lock = threading.Lock()
_chromadb_mod = None
_embedding_functions_mod = None

def _ensure_chromadb_modules() -> Tuple[Any, Any]:
    global _chromadb_mod, _embedding_functions_mod
    if _chromadb_mod is not None and _embedding_functions_mod is not None:
        return _chromadb_mod, _embedding_functions_mod
    with _chroma_import_lock:
        if _chromadb_mod is None or _embedding_functions_mod is None:
            import chromadb as _c  # heavy; keep out of cold-start path
            from chromadb.utils import embedding_functions as _ef  # heavy; keep out of cold-start path
            _chromadb_mod = _c
            _embedding_functions_mod = _ef
    return _chromadb_mod, _embedding_functions_mod

rag_init_state: str = "not_started"  # not_started|initializing|ready|disabled|error
rag_init_error: Optional[str] = None

# --- RAG defaults / configuration helpers ---
DEFAULT_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION", "nda_documents")
DEFAULT_DISTANCE_THRESHOLD = float(os.environ.get("RAG_DISTANCE_THRESHOLD", "0.75"))

# Resolve BASE_DIR robustly (works for dev, win-unpacked, and installed builds).
# We anchor to server.py's location rather than cwd so config/prompts are found even if cwd changes.
if getattr(sys, "_MEIPASS", False):
    # Running in PyInstaller bundle
    _meipass = getattr(sys, "_MEIPASS", None)  # PyInstaller sets this at runtime
    BASE_DIR = os.path.dirname(_meipass) if _meipass else os.getcwd()
else:
    # Running from source copied into Electron resources/python
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

logger.info(f"BASE_DIR resolved to: {BASE_DIR}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"__file__ path: {__file__}")

# OCR (optional): lazy-import on first use to avoid slowing down app startup in packaged builds.
# EasyOCR + PyMuPDF can add minutes to cold start on some Windows machines if imported eagerly.
OCR_AVAILABLE = False
OCR_READER = None
_OCR_IMPORT_ERROR: Optional[str] = None

def ensure_ocr_loaded() -> bool:
    """
    Lazily import OCR dependencies only when needed.
    Returns True when OCR is available for use, otherwise False.
    """
    global OCR_AVAILABLE, _OCR_IMPORT_ERROR
    if OCR_AVAILABLE:
        return True
    if _OCR_IMPORT_ERROR is not None:
        return False

    try:
        # Import only when required (can be slow).
        global easyocr, fitz  # type: ignore[global-variable-not-assigned]
        import easyocr  # type: ignore
        import fitz  # type: ignore  # PyMuPDF
        OCR_AVAILABLE = True
        logger.info("OCR libraries loaded (lazy): easyocr, PyMuPDF")
        return True
    except Exception as e:
        _OCR_IMPORT_ERROR = str(e)
        OCR_AVAILABLE = False
        logger.warning(f"OCR libraries not available (lazy): {e}")
        return False
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

# Use USER_DATA_DIR from environment or fall back to platform-specific config dir
# e.g. ~/.config/docusenselm on Linux
default_user_data = user_config_dir("docusenselm", appauthor=False)
USER_DATA_DIR = os.environ.get("USER_DATA_DIR", default_user_data)
logger.info(f"USER_DATA_DIR resolved to: {USER_DATA_DIR}")

DOCUMENTS_DIR = os.path.join(USER_DATA_DIR, "documents")
TEMPLATES_DIR = os.path.join(USER_DATA_DIR, "templates")
DB_DIR = os.path.join(USER_DATA_DIR, "chroma_db")
METADATA_FILE = os.path.join(DOCUMENTS_DIR, "metadata.json")

# Ensure all directories exist
os.makedirs(DOCUMENTS_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# Load .env (optional). Prefer userData .env for installed builds; fall back to BASE_DIR .env for dev.
# Do not override existing env vars.
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)
load_dotenv(os.path.join(USER_DATA_DIR, ".env"), override=False)
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
    """
    Load configuration with default + user override semantics.
    IMPORTANT: We deep-merge default config into user config so new default keys (e.g. rag.*)
    appear automatically even if the user's config.yaml was created on an older version.
    """
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(base or {})
        for k, v in (override or {}).items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = _deep_merge(out[k], v)  # type: ignore[arg-type]
            else:
                out[k] = v
        return out

    # Load defaults first
    default_config_path = os.path.join(BASE_DIR, "config.default.yaml")
    defaults: Dict[str, Any] = {}
    try:
        with open(default_config_path, "r") as f:
            defaults = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load default config: {e}")
        defaults = {"document_types": {}, "dashboard": {}}

    # Then apply user overrides (if present)
    user_config_path = os.path.join(USER_DATA_DIR, "config.yaml")
    user_cfg: Dict[str, Any] = {}
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, "r") as f:
                user_cfg = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load user config: {e}")
            user_cfg = {}
    else:
        logger.info(f"No user config.yaml found at {user_config_path} (will use defaults)")

    logger.info(f"Config paths: default={default_config_path} (exists={os.path.exists(default_config_path)}), user={user_config_path} (exists={os.path.exists(user_config_path)})")
    return _deep_merge(defaults, user_cfg)

config = load_app_config()

# RAG configuration (from config.yaml with env fallbacks)
def _get_collection_name() -> str:
    try:
        name = (config or {}).get("rag", {}).get("collection_name")
        if name and str(name).strip():
            return str(name).strip()
    except Exception:
        pass
    return DEFAULT_COLLECTION_NAME

def _get_distance_threshold() -> float:
    try:
        val = (config or {}).get("rag", {}).get("distance_threshold")
        if val is not None:
            return float(val)
    except Exception:
        pass
    return DEFAULT_DISTANCE_THRESHOLD

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
        logger.info("OpenAI API key source: environment variable OPENAI_API_KEY (present)")
        return env_key

    # Priority 2: Config file
    if config and "api" in config and "openai_api_key" in config["api"]:
        config_key = config["api"]["openai_api_key"]
        if config_key and config_key.strip():
            logger.info("OpenAI API key source: USER_DATA_DIR/config.yaml (present)")
            return config_key.strip()

    logger.info("OpenAI API key source: none (missing)")
    return None

# Function to initialize or reinitialize OpenAI client
def initialize_openai_client():
    global openai_client, openai_ef, collection, chroma_client

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

        # Ensure Chroma is available (lazy import/init)
        chromadb, embedding_functions = _ensure_chromadb_modules()
        if chroma_client is None:
            with _chroma_init_lock:
                if chroma_client is None:
                    chroma_client = chromadb.PersistentClient(path=DB_DIR)

        # Initialize ChromaDB with OpenAI embeddings
        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-3-small"
        )
        # Initialize ChromaDB collection with OpenAI embeddings
        # If collection name changes across versions, we want to avoid silently creating a new empty one.
        desired_name = _get_collection_name()
        try:
            collection = chroma_client.get_or_create_collection(
                name=desired_name,
                embedding_function=openai_ef
            )
        except Exception:
            # Fallback for older Chroma versions that may not accept embedding_function on get_or_create
            collection = chroma_client.get_or_create_collection(name=desired_name)
            try:
                # Try to attach embedding function if supported
                collection._embedding_function = openai_ef  # type: ignore[attr-defined]
            except Exception:
                pass

        # Detect common footgun: an empty freshly-created collection while another legacy collection has data.
        try:
            desired_count = collection.count() if collection is not None else 0
            if desired_count == 0:
                legacy_candidates = []
                for c in chroma_client.list_collections():
                    try:
                        cname = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else None)  # type: ignore[attr-defined]
                    except Exception:
                        cname = None
                    if not cname or cname == desired_name:
                        continue
                    try:
                        legacy_col = chroma_client.get_collection(name=cname, embedding_function=openai_ef)  # type: ignore[arg-type]
                    except Exception:
                        legacy_col = chroma_client.get_collection(name=cname)  # type: ignore[arg-type]
                    try:
                        legacy_count = legacy_col.count()
                    except Exception:
                        legacy_count = 0
                    if legacy_count > 0:
                        legacy_candidates.append((cname, legacy_count))
                if legacy_candidates:
                    legacy_candidates.sort(key=lambda x: -x[1])
                    chosen_name, chosen_count = legacy_candidates[0]
                    logger.warning(
                        f"Chroma collection '{desired_name}' is empty but found legacy collection '{chosen_name}' with {chosen_count} chunks. "
                        f"Using legacy collection to avoid silent RAG breakage."
                    )
                    try:
                        collection = chroma_client.get_collection(name=chosen_name, embedding_function=openai_ef)  # type: ignore[arg-type]
                    except Exception:
                        collection = chroma_client.get_collection(name=chosen_name)  # type: ignore[arg-type]
                        try:
                            collection._embedding_function = openai_ef  # type: ignore[attr-defined]
                        except Exception:
                            pass

        except Exception as e:
            logger.warning(f"Could not validate Chroma collections on init: {e}")

        logger.info(f"ChromaDB collection initialized: name='{_get_collection_name()}'")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        openai_client = None
        openai_ef = None
        collection = None
        return False

# Chroma/OpenAI clients are initialized lazily (see initialize_openai_client + startup_event).
chroma_client = None
openai_client = None
openai_ef = None
collection = None

# Initialize FastAPI
app = FastAPI(title=f"{APP_NAME} API")

# Thread pool for parallel document processing
# Best Practice: Use ThreadPoolExecutor for I/O-bound and CPU-intensive tasks
# This allows multiple documents to process in parallel rather than sequentially
processing_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="doc_processor")

# Thread lock for metadata file access (CRITICAL for thread safety)
# Prevents race conditions when multiple threads update metadata simultaneously
metadata_lock = threading.Lock()

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

# Common English stop words to exclude from keyword extraction
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
    'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
    'this', 'that', 'these', 'those', 'what', 'which', 'who', 'whom', 'where', 'when',
    'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
    'about', 'after', 'before', 'between', 'into', 'through', 'during', 'above', 'below',
    'from', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
}

def extract_keywords(query: str) -> List[str]:
    """
    Extract meaningful keywords from a query for keyword-based search.
    Filters out stop words and very short words.
    """
    import re
    # Tokenize and clean
    words = re.findall(r'\b[a-zA-Z]+\b', query.lower())
    # Filter: remove stop words and words <= 2 chars
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return keywords

def _normalize_token(s: str) -> str:
    """
    Normalize tokens for fuzzy filename matching: lowercase and keep only [a-z0-9].
    """
    import re
    return re.sub(r'[^a-z0-9]+', '', (s or "").lower())

def _bounded_levenshtein(a: str, b: str, max_dist: int) -> int:
    """
    Levenshtein distance with an upper bound. Returns max_dist+1 if it exceeds max_dist.
    This is used only for short tokens to keep filename matching tolerant to typos.
    """
    if max_dist < 0:
        return max_dist + 1

    if a == b:
        return 0

    # Quick length check
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return max_dist + 1

    # Ensure a is the shorter string
    if la > lb:
        a, b = b, a
        la, lb = lb, la

    prev = list(range(la + 1))
    for j in range(1, lb + 1):
        bj = b[j - 1]
        cur = [j] + [0] * la
        row_min = cur[0]
        for i in range(1, la + 1):
            cost = 0 if a[i - 1] == bj else 1
            cur[i] = min(
                prev[i] + 1,       # deletion
                cur[i - 1] + 1,    # insertion
                prev[i - 1] + cost # substitution
            )
            if cur[i] < row_min:
                row_min = cur[i]
        if row_min > max_dist:
            return max_dist + 1
        prev = cur

    dist = prev[la]
    return dist if dist <= max_dist else max_dist + 1

def keyword_search(query: str, all_chunks: List[Dict], n_results: int = 20) -> List[Dict]:
    """
    Perform keyword-based search using a lightweight BM25-style scorer.
    Returns chunks ranked by keyword match score.

    Args:
        query: The search query
        all_chunks: List of dicts with 'id', 'doc', 'metadata'
        n_results: Max results to return

    Returns:
        List of chunk dicts with added 'keyword_score' field, sorted by score descending
    """
    keywords = extract_keywords(query)
    if not keywords:
        return []

    import math

    # Tokenize chunks once (exact-ish word matching, but allow prefix matches for short stems like "pay" -> "payment")
    tokenized = []
    for chunk in all_chunks:
        doc = chunk.get("doc") or ""
        tokens = re.findall(r"\b[a-zA-Z]+\b", doc.lower())
        tokenized.append((chunk, tokens))

    N = len(tokenized) or 1
    avgdl = (sum(len(toks) for _, toks in tokenized) / N) if N else 0.0

    # Document frequency per keyword
    df = {kw: 0 for kw in keywords}
    for _, toks in tokenized:
        if not toks:
            continue
        tok_set = set(toks)
        for kw in keywords:
            # Consider token match if exact OR token startswith kw (e.g., pay->payment)
            if kw in tok_set or any(t.startswith(kw) for t in tok_set):
                df[kw] += 1

    # BM25 parameters (lightweight defaults)
    k1 = 1.2
    b = 0.75

    scored_chunks = []
    for chunk, toks in tokenized:
        if not toks:
            continue
        dl = len(toks)

        score = 0.0
        matched_keywords = []
        for kw in keywords:
            # Term frequency with prefix match support
            tf = 0
            for t in toks:
                if t == kw or t.startswith(kw):
                    tf += 1
            if tf <= 0:
                continue

            matched_keywords.append(kw)
            # IDF (always positive)
            dfi = df.get(kw, 0)
            idf = math.log(1 + (N - dfi + 0.5) / (dfi + 0.5))
            denom = tf + k1 * (1 - b + b * (dl / (avgdl or 1.0)))
            score += idf * (tf * (k1 + 1) / (denom or 1.0))

        # Coverage bonus: prefer chunks that match multiple distinct keywords
        if len(matched_keywords) > 1:
            score *= (1 + 0.15 * (len(matched_keywords) - 1))

        if score > 0:
            chunk_copy = chunk.copy()
            chunk_copy["keyword_score"] = float(score)
            chunk_copy["matched_keywords"] = matched_keywords
            scored_chunks.append(chunk_copy)

    scored_chunks.sort(key=lambda x: -x["keyword_score"])
    return scored_chunks[:n_results]

def hybrid_search_rrf(query: str, collection, n_results: int = 10, k: int = 60) -> List[Dict]:
    """
    Perform hybrid search using Reciprocal Rank Fusion (RRF).
    Combines semantic vector search with keyword-based search.

    RRF Score = Σ 1/(k + rank) for each ranking where document appears

    Args:
        query: The search query
        collection: ChromaDB collection
        n_results: Number of final results to return
        k: RRF constant (default 60, higher = more weight to lower ranks)

    Returns:
        List of chunk dicts sorted by combined RRF score
    """
    if collection is None:
        logger.warning("Collection is None, cannot perform hybrid search")
        return []

    # Keep RAG logs quiet by default (logs can contain filenames and retrieval internals).
    # Enable detailed logs via config.yaml -> rag.debug_logging: true
    rag_debug = bool((config or {}).get("rag", {}).get("debug_logging", False))

    # Retrieve more candidates for fusion
    semantic_n = n_results * 3
    keyword_n = n_results * 3

    # 1. Semantic Search (vector-based)
    semantic_results = collection.query(
        query_texts=[query],
        n_results=semantic_n,
        include=['documents', 'metadatas', 'distances']
    )

    # 2. Get all chunks for keyword search (we'll score them)
    all_chunks_result = collection.get(include=['documents', 'metadatas'])
    all_chunks = []
    if all_chunks_result and all_chunks_result.get('ids'):
        for i, doc_id in enumerate(all_chunks_result['ids']):
            all_chunks.append({
                'id': doc_id,
                'doc': all_chunks_result['documents'][i],
                'metadata': all_chunks_result['metadatas'][i] if all_chunks_result['metadatas'] else {}
            })

    # 3. Keyword Search
    keyword_results = keyword_search(query, all_chunks, n_results=keyword_n)

    # 4. Build RRF scores
    rrf_scores = {}  # doc_id -> {'score': float, 'chunk_data': dict}

    # Process semantic results
    if semantic_results and semantic_results.get('documents') and len(semantic_results['documents']) > 0:
        for rank, (doc, meta, dist) in enumerate(zip(
            semantic_results['documents'][0],
            semantic_results['metadatas'][0] if semantic_results.get('metadatas') else [{}] * len(semantic_results['documents'][0]),
            semantic_results['distances'][0] if semantic_results.get('distances') else [0] * len(semantic_results['documents'][0])
        )):
            # Create a stable ID for the chunk (Python's built-in hash() is randomized per process).
            chunk_id = hashlib.sha1(doc[:200].encode("utf-8", errors="ignore")).hexdigest()

            rrf_contribution = 1.0 / (k + rank)

            if chunk_id not in rrf_scores:
                rrf_scores[chunk_id] = {
                    'score': 0,
                    'semantic_rank': rank + 1,
                    'keyword_rank': None,
                    'semantic_distance': dist,
                    'doc': doc,
                    'metadata': meta,
                    'filename': meta.get('filename', 'unknown') if meta else 'unknown'
                }
            rrf_scores[chunk_id]['score'] += rrf_contribution
            rrf_scores[chunk_id]['semantic_rank'] = rank + 1

    # Process keyword results
    for rank, chunk in enumerate(keyword_results):
        chunk_id = hashlib.sha1((chunk.get('doc') or "")[:200].encode("utf-8", errors="ignore")).hexdigest()

        rrf_contribution = 1.0 / (k + rank)

        if chunk_id not in rrf_scores:
            rrf_scores[chunk_id] = {
                'score': 0,
                'semantic_rank': None,
                'keyword_rank': rank + 1,
                'semantic_distance': None,
                'doc': chunk['doc'],
                'metadata': chunk['metadata'],
                'filename': chunk['metadata'].get('filename', 'unknown') if chunk['metadata'] else 'unknown'
            }
        rrf_scores[chunk_id]['score'] += rrf_contribution
        rrf_scores[chunk_id]['keyword_rank'] = rank + 1
        rrf_scores[chunk_id]['keyword_score'] = chunk.get('keyword_score', 0)
        rrf_scores[chunk_id]['matched_keywords'] = chunk.get('matched_keywords', [])

    # 5. Sort by RRF score and return top n
    sorted_results = sorted(rrf_scores.values(), key=lambda x: -x['score'])

    # Log hybrid search results (debug-only)
    if rag_debug:
        logger.info(f"=== HYBRID SEARCH (RRF) RESULTS ===")
        logger.info(f"Query: '{query}'")
        logger.info(f"Semantic candidates: {len(semantic_results['documents'][0]) if semantic_results.get('documents') else 0}")
        logger.info(f"Keyword candidates: {len(keyword_results)}")
        logger.info(f"Unique chunks after fusion: {len(rrf_scores)}")

        for i, result in enumerate(sorted_results[:n_results]):
            sem_rank = result.get('semantic_rank', '-')
            kw_rank = result.get('keyword_rank', '-')
            kw_matches = result.get('matched_keywords', [])
            logger.info(f"  #{i+1}: RRF={result['score']:.4f}, sem_rank={sem_rank}, kw_rank={kw_rank}, file={result['filename'][:40]}, kw_matches={kw_matches}")

    return sorted_results[:n_results]

def load_metadata():
    """
    Thread-safe metadata loading.
    Uses lock to prevent race conditions during concurrent access.
    """
    with metadata_lock:
        if os.path.exists(METADATA_FILE):
            try:
                with open(METADATA_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return {}
        return {}

def save_metadata(metadata):
    """
    Thread-safe metadata saving.
    Uses lock to prevent race conditions during concurrent writes.
    CRITICAL: This prevents data loss when multiple documents process in parallel.
    """
    with metadata_lock:
        try:
            with open(METADATA_FILE, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            raise

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
        # Scanned PDF - use OCR (lazy import to avoid slowing app startup)
        if ensure_ocr_loaded():
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
        # Heavy import: keep out of cold-start path.
        from langchain_text_splitters import RecursiveCharacterTextSplitter
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

def process_document_sync(filename: str, filepath: str, doc_type: str):
    """
    Synchronous wrapper for document processing. Used by ThreadPoolExecutor for parallel processing.
    """
    # Run the async function in a new event loop (thread-safe)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_process_document_async(filename, filepath, doc_type))
        loop.close()
    except Exception as e:
        logger.error(f"Error in sync wrapper for {filename}: {e}")
        # Update status to error
        try:
            metadata = load_metadata()
            if filename in metadata:
                metadata[filename]["status"] = "error"
                save_metadata(metadata)
        except:
            pass

async def _process_document_async(filename: str, filepath: str, doc_type: str):
    """
    Internal async function for document processing.
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
        # Update status to error on unexpected errors
        metadata = load_metadata()
        if filename in metadata:
            metadata[filename]["status"] = "error"
            metadata[filename]["text_extracted"] = False
            save_metadata(metadata)

async def process_document_background(filename: str, filepath: str, doc_type: str):
    """
    Process document in background. FastAPI BackgroundTasks handles async functions correctly.
    This is kept for backwards compatibility with single file uploads.
    """
    await _process_document_async(filename, filepath, doc_type)

# --- Models ---

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    sources: Optional[List[str]] = None  # Optional: sources cited by assistant in previous turns (for stable multi-turn RAG)

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[ChatMessage]] = None  # Previous conversation turns

class UpdateStatusRequest(BaseModel):
    status: str

class UpdateDocTypeRequest(BaseModel):
    doc_type: str

class UpdateMetadataRequest(BaseModel):
    competency_answers: Dict[str, Any]

# --- Endpoints ---

@app.get("/health")
def health_check():
    # Keep this endpoint lightweight: it must return fast so Electron can decide the backend is up.
    # Detailed diagnostics are available at /rag/status.
    return {
        "status": "ok",
        "version": "1.0.1",
        "rag": rag_init_state,
        "rag_error": rag_init_error,
    }


def _safe_collection_count(col) -> int:
    try:
        return int(col.count())
    except Exception:
        return 0


def _safe_collection_filename_count(col, filename: str) -> int:
    try:
        res = col.get(where={"filename": filename}, include=[])
        ids = res.get("ids") if res else None
        return len(ids) if ids else 0
    except Exception:
        return 0


def _list_collections_with_counts() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if chroma_client is None:
        return out
    try:
        cols = chroma_client.list_collections()
    except Exception:
        return out
    for c in cols:
        try:
            cname = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else None)  # type: ignore[attr-defined]
        except Exception:
            cname = None
        if not cname:
            continue
        try:
            col_obj = chroma_client.get_collection(name=cname)  # type: ignore[arg-type]
            cnt = _safe_collection_count(col_obj)
        except Exception:
            cnt = 0
        out.append({"name": cname, "count": cnt})
    out.sort(key=lambda x: (-x["count"], x["name"]))
    return out


def get_rag_status() -> Dict[str, Any]:
    """
    RAG diagnostics endpoint data. This is designed to make "silent RAG failure" impossible.
    """
    md = load_metadata()
    md_items = list(md.values()) if isinstance(md, dict) else []

    desired_collection = _get_collection_name()
    distance_threshold = _get_distance_threshold()

    total_chunks = _safe_collection_count(collection) if collection is not None else 0

    # Detect processed docs that claim to be searchable but have 0 indexed chunks.
    missing_index: List[Dict[str, Any]] = []
    example_fixture_filename = None
    for k in (md.keys() if isinstance(md, dict) else []):
        # Prefer a known synthetic fixture if present (safe for public repos)
        if isinstance(k, str) and "scanned_pricing_test" in k.lower():
            example_fixture_filename = k
            break

    # Limit per-file checks to avoid long response times.
    processed_searchable = [
        d for d in md_items
        if isinstance(d, dict) and d.get("status") == "processed" and d.get("text_extracted") is True
    ]
    for d in processed_searchable[:75]:
        fname = d.get("filename")
        if not fname or not isinstance(fname, str) or collection is None:
            continue
        cnt = _safe_collection_filename_count(collection, fname)
        if cnt == 0:
            missing_index.append({"filename": fname, "doc_type": d.get("doc_type"), "status": d.get("status")})

    example_fixture_chunks = _safe_collection_filename_count(collection, example_fixture_filename) if (collection is not None and example_fixture_filename) else 0

    ready = bool(openai_client) and bool(collection) and total_chunks > 0
    return {
        "ready": ready,
        "openai_configured": bool(openai_client),
        "user_data_dir": USER_DATA_DIR,
        "db_dir": DB_DIR,
        "documents_dir": DOCUMENTS_DIR,
        "metadata_file": METADATA_FILE,
        "collection_name": desired_collection,
        "collections": _list_collections_with_counts(),
        "total_chunks": total_chunks,
        "distance_threshold": distance_threshold,
        "metadata_documents": len(md_items),
        "processed_searchable_documents": len(processed_searchable),
        "missing_index_documents": missing_index,
        "example_fixture_filename": example_fixture_filename,
        "example_fixture_chunks": example_fixture_chunks,
    }


@app.get("/rag/status")
def rag_status():
    return get_rag_status()


@app.get("/rag/debug-search")
def rag_debug_search(q: str):
    """
    Lightweight debug endpoint to validate retrieval without invoking the LLM.
    Helps diagnose cases where /chat returns empty sources.
    """
    if collection is None:
        raise HTTPException(status_code=500, detail="Chroma collection not initialized")

    query_lower = q.lower()
    is_pricing_query = any(word in query_lower for word in ['pay', 'cost', 'price', 'fee', 'charge', 'hour', 'rate', 'per'])
    n_results = 8 if is_pricing_query else 5
    distance_threshold = _get_distance_threshold()

    hybrid_results = hybrid_search_rrf(q, collection, n_results=n_results * 2)

    max_chunks = 5 if is_pricing_query else 3
    included = []
    for r in hybrid_results:
        if len(included) >= max_chunks:
            break
        semantic_distance = r.get("semantic_distance")
        matched_keywords = r.get("matched_keywords", []) or []
        has_keyword_match = len(matched_keywords) > 0

        include = True
        reason = "default"
        if semantic_distance is not None and not has_keyword_match:
            if semantic_distance > distance_threshold:
                include = False
                reason = "distance_gt_threshold_no_keywords"
        if include:
            included.append({
                "filename": r.get("filename", "unknown"),
                "semantic_distance": semantic_distance,
                "matched_keywords": matched_keywords,
                "semantic_rank": r.get("semantic_rank"),
                "keyword_rank": r.get("keyword_rank"),
                "rrf_score": r.get("score"),
                "include_reason": reason,
                "preview": (r.get("doc", "") or "")[:240]
            })

    return {
        "query": q,
        "is_pricing_query": is_pricing_query,
        "distance_threshold": distance_threshold,
        "hybrid_candidates": len(hybrid_results),
        "included": included,
    }


@app.get("/rag/chunks")
def rag_chunks(filename: str, limit: int = 5):
    """
    Return a small preview of indexed chunks for a given filename.
    This is purely for diagnostics and helps confirm whether key terms (e.g. "WEEDING") are present in the index.
    """
    if collection is None:
        raise HTTPException(status_code=500, detail="Chroma collection not initialized")
    try:
        res = collection.get(where={"filename": filename}, include=["documents", "metadatas"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read chunks from Chroma: {e}")

    docs = (res.get("documents") if res else None) or []
    metas = (res.get("metadatas") if res else None) or []
    out = []
    for i, doc in enumerate(docs[: max(1, min(int(limit), 25))]):
        meta = metas[i] if i < len(metas) else {}
        out.append({
            "i": i,
            "chars": len(doc or ""),
            "preview": (doc or "")[:800],
            "metadata": meta,
        })
    return {"filename": filename, "chunks": out, "chunk_count": len(docs)}


@app.post("/rag/rebuild-missing")
async def rag_rebuild_missing():
    """
    Rebuild the vector index for documents that are marked searchable but have no chunks in Chroma.
    This is the primary "self-heal" mechanism to prevent flaky RAG after restarts.
    """
    if not openai_client or collection is None:
        raise HTTPException(status_code=500, detail="RAG not configured (OpenAI key missing or collection not initialized)")

    status = get_rag_status()
    missing = status.get("missing_index_documents", [])
    if not missing:
        return {"status": "ok", "message": "No missing-index documents detected", "queued": []}

    md = load_metadata()
    queued = []
    for item in missing:
        fname = item.get("filename")
        if not fname or not isinstance(fname, str):
            continue
        file_path = os.path.join(DOCUMENTS_DIR, fname)
        if not os.path.exists(file_path):
            continue
        doc_type = "nda"
        try:
            if isinstance(md, dict) and fname in md and isinstance(md[fname], dict):
                doc_type = md[fname].get("doc_type", "nda")
        except Exception:
            doc_type = "nda"

        # Mark as processing and submit to executor
        try:
            if isinstance(md, dict) and fname in md and isinstance(md[fname], dict):
                md[fname]["status"] = "processing"
                md[fname]["text_extracted"] = False
        except Exception:
            pass
        queued.append(fname)
        processing_executor.submit(process_document_sync, fname, file_path, doc_type)

    try:
        if isinstance(md, dict):
            save_metadata(md)
    except Exception:
        pass

    return {"status": "ok", "message": f"Queued {len(queued)} documents for re-indexing", "queued": queued}

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
async def backup_data():
    # Create zip of USER_DATA_DIR
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"nda_backup_{timestamp}.zip"
    # Create the zip in OS temp (NOT repo root) to avoid cluttering BASE_DIR.
    temp_dir = tempfile.mkdtemp(prefix="docusenselm_backup_")
    zip_path = os.path.join(temp_dir, zip_filename)

    # Create zip manually, skipping locked/cache files
    import zipfile
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(USER_DATA_DIR):
            # Skip Cache directories (locked by Electron)
            dirs[:] = [d for d in dirs if d not in ['Cache', 'GPUCache', 'Code Cache']]

            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, USER_DATA_DIR)
                try:
                    zipf.write(file_path, arcname)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Skipping locked file in backup: {arcname} ({e})")
                    continue

    # Stream the file and delete it after streaming completes
    def generate():
        try:
            with open(zip_path, 'rb') as f:
                while True:
                    chunk = f.read(64 * 1024)  # 64KB chunks
                    if not chunk:
                        break
                    yield chunk
        finally:
            # Delete file after streaming is complete
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                    logger.info(f"Cleaned up backup file: {zip_path}")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.error(f"Error cleaning up backup file {zip_path}: {e}")

    headers = {
        "Content-Disposition": f'attachment; filename="{zip_filename}"'
    }

    return StreamingResponse(
        generate(),
        media_type='application/zip',
        headers=headers
    )

def cleanup_root_zip_artifacts():
    """
    Safety cleanup: legacy versions created backup/restore zips in BASE_DIR (repo root).
    This ensures we never leave .zip artifacts there.
    """
    try:
        # Old backup naming
        for name in os.listdir(BASE_DIR):
            if name.startswith("nda_backup_") and name.endswith(".zip"):
                try:
                    os.remove(os.path.join(BASE_DIR, name))
                except Exception:
                    pass
        # Old restore temp zip naming
        legacy_restore = os.path.join(BASE_DIR, "temp_restore.zip")
        if os.path.exists(legacy_restore):
            try:
                os.remove(legacy_restore)
            except Exception:
                pass
    except Exception:
        # Never block app behavior on cleanup
        pass

@app.post("/restore")
async def restore_data(file: UploadFile = File(...)):
    logger.info(f"=== RESTORE ENDPOINT CALLED ===")
    logger.info(f"Uploaded file: {file.filename}")

    # Validate
    if not file.filename.endswith(".zip"):
        logger.error(f"Invalid file type: {file.filename}")
        raise HTTPException(status_code=400, detail="Invalid file type. Must be a zip.")

    # Never write temp restore zips into BASE_DIR (repo root). Use OS temp instead.
    cleanup_root_zip_artifacts()
    temp_dir = tempfile.mkdtemp(prefix="docusenselm_restore_")
    temp_zip = os.path.join(temp_dir, "restore.zip")
    logger.info(f"Using temp restore location: {temp_zip}")

    try:
        logger.info("Writing uploaded file to temp...")
        with open(temp_zip, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Temp file written, size: {os.path.getsize(temp_zip)} bytes")

        # Wipe current user data (DANGER)
        # Skip locked files (Cache, etc.) that are held by the running Electron app
        logger.info(f"Wiping USER_DATA_DIR: {USER_DATA_DIR}")
        if os.path.exists(USER_DATA_DIR):
            def handle_remove_error(func, path, exc_info):
                """Skip locked files during restore"""
                logger.warning(f"Skipping locked file during restore: {path}")

            shutil.rmtree(USER_DATA_DIR, onerror=handle_remove_error)
        os.makedirs(USER_DATA_DIR, exist_ok=True)

        # Unzip manually to skip locked files
        logger.info("Unpacking archive...")
        import zipfile
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            for member in zip_ref.namelist():
                try:
                    zip_ref.extract(member, USER_DATA_DIR)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Skipping locked file during extraction: {member} ({e})")
                    continue
        logger.info("Archive unpacked successfully (skipped locked files)")
    finally:
        # Cleanup temp restore artifacts
        try:
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
        except Exception:
            pass
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    # Restart Chroma Client (it might have open connections to old files)
    global chroma_client, collection
    # Force reload if possible, or just let the next request handle it
    # Chroma persistent client handles restarts okay usually.

    return {"status": "restored", "message": "Data restored successfully. Please restart the application if you see issues."}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...), doc_type: str = "nda", skip_processing: bool = False, background_tasks: BackgroundTasks = None):
    """
    Upload a document file. Optionally skip immediate processing for bulk uploads.

    Best Practices Implemented:
    - File validation (type, size, name sanitization)
    - Streaming upload for large files
    - Secure file storage with sanitized names
    - Separate upload and processing phases
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = file.filename.lower().split('.')[-1]
    if file_ext not in ['pdf', 'docx']:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are allowed")

    # Sanitize filename to prevent path traversal attacks
    # Remove any path components and use only the basename
    import os.path
    import re
    safe_filename = os.path.basename(file.filename)
    # Remove any non-alphanumeric characters except .-_
    safe_filename = re.sub(r'[^\w\s\-\.]', '', safe_filename)
    # Ensure filename is not empty after sanitization
    if not safe_filename or safe_filename == '.':
        safe_filename = f"document_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"

    # Check for duplicate filename
    original_safe_filename = safe_filename
    counter = 1
    filepath = os.path.join(DOCUMENTS_DIR, safe_filename)
    while os.path.exists(filepath):
        name_part, ext_part = os.path.splitext(original_safe_filename)
        safe_filename = f"{name_part}_{counter}{ext_part}"
        filepath = os.path.join(DOCUMENTS_DIR, safe_filename)
        counter += 1

    # Validate file size (streaming - don't load entire file into memory)
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB limit
    file_size = 0

    try:
        # Stream file to disk in chunks (best practice for large files)
        with open(filepath, "wb") as buffer:
            while chunk := await file.read(8192):  # Read in 8KB chunks
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    # Clean up partial file
                    buffer.close()
                    os.remove(filepath)
                    raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB")
                buffer.write(chunk)
    except Exception as e:
        # Clean up on error
        if os.path.exists(filepath):
            os.remove(filepath)
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

    # Init metadata
    metadata = load_metadata()
    # Get show_on_dashboard default from config, default to True if not specified
    doc_type_config = config.get("document_types", {}).get(doc_type, {})
    show_on_dashboard = doc_type_config.get("show_on_dashboard", True)

    metadata[safe_filename] = {
        "filename": safe_filename,
        "original_filename": file.filename,  # Track original name
        "doc_type": doc_type,
        "upload_date": datetime.datetime.now().isoformat(),
        "file_size": file_size,
        "status": "pending",
        "workflow_status": "in_review",
        "show_on_dashboard": show_on_dashboard,
        "competency_answers": {}
    }
    save_metadata(metadata)

    logger.info(f"File uploaded successfully: {safe_filename} (size: {file_size} bytes)")

    # Process immediately only if skip_processing is False
    if not skip_processing:
        background_tasks.add_task(process_document_background, safe_filename, filepath, doc_type)

    return {"status": "uploaded", "filename": safe_filename, "original_filename": file.filename, "file_size": file_size}

@app.post("/start-processing")
async def start_processing():
    """
    Start processing all documents with 'pending' status in PARALLEL.

    Best Practice: Uses ThreadPoolExecutor to process multiple documents simultaneously
    rather than sequentially. This is much faster for bulk uploads.

    This endpoint is used after bulk upload to trigger processing of all uploaded files.
    """
    logger.info("=== START-PROCESSING ENDPOINT CALLED ===")
    metadata = load_metadata()

    # Find all pending documents
    pending_files = [
        (filename, data)
        for filename, data in metadata.items()
        if data.get("status") == "pending"
    ]

    if not pending_files:
        logger.info("No pending documents to process")
        return {"status": "no_pending_files", "message": "No documents are pending processing"}

    logger.info(f"Starting parallel processing of {len(pending_files)} documents")

    # Submit all pending files to thread pool for PARALLEL processing
    # Best Practice: Process documents in parallel using thread pool
    futures = []
    for filename, data in pending_files:
        filepath = os.path.join(DOCUMENTS_DIR, filename)
        doc_type = data.get("doc_type", "nda")

        if os.path.exists(filepath):
            logger.info(f"Submitting {filename} for parallel processing (doc_type: {doc_type})")
            # Submit to thread pool - will process in parallel up to max_workers
            future = processing_executor.submit(process_document_sync, filename, filepath, doc_type)
            futures.append((filename, future))
        else:
            logger.warning(f"File not found, skipping: {filepath}")
            # Mark as error in metadata
            if filename in metadata:
                metadata[filename]["status"] = "error"
                save_metadata(metadata)

    logger.info(f"Submitted {len(futures)} documents for parallel processing")
    return {
        "status": "processing_started",
        "message": f"Started processing {len(futures)} document(s) in parallel",
        "count": len(futures),
        "files": [f[0] for f in futures]
    }

@app.post("/reprocess/{filename}")
async def reprocess_document(filename: str):
    """
    Reprocess a single document using the parallel processing executor.
    This allows reprocessing to happen alongside bulk processing operations.
    """
    logger.info(f"=== REPROCESS ENDPOINT CALLED FOR {filename} ===")
    filepath = os.path.join(DOCUMENTS_DIR, filename)
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        raise HTTPException(status_code=404, detail="File not found")

    metadata = load_metadata()
    if filename not in metadata:
        logger.error(f"Metadata not found for: {filename}")
        raise HTTPException(status_code=404, detail="Metadata not found")

    # Update status to processing (not reprocessing) to match the new flow
    logger.info(f"Setting status to 'processing' for {filename}")
    metadata[filename]["status"] = "processing"
    save_metadata(metadata)

    # Re-run processing using ThreadPoolExecutor for parallel execution
    doc_type = metadata[filename].get("doc_type", "nda")
    logger.info(f"Submitting {filename} for parallel reprocessing (doc_type: {doc_type})")

    # Submit to thread pool - will process in parallel with other documents
    future = processing_executor.submit(process_document_sync, filename, filepath, doc_type)

    logger.info(f"Document {filename} submitted to parallel processing queue")
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

@app.post("/metadata/{filename}")
async def update_metadata(filename: str, request: UpdateMetadataRequest):
    metadata = load_metadata()
    if filename not in metadata:
        raise HTTPException(status_code=404, detail="File not found")

    # Validate competency_answers is a dictionary
    if not isinstance(request.competency_answers, dict):
        raise HTTPException(status_code=400, detail="competency_answers must be a dictionary")

    # Update competency_answers
    metadata[filename]["competency_answers"] = request.competency_answers
    save_metadata(metadata)

    return {"status": "updated", "filename": filename, "competency_answers": request.competency_answers}

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

    # MVP hardening: if vector DB isn't ready (no collection / no chunks), return a friendly answer
    # instead of erroring or sending empty context to the model.
    try:
        total_chunks = _safe_collection_count(collection) if collection is not None else 0
    except Exception:
        total_chunks = 0

    if collection is None or total_chunks <= 0:
        return {
            "answer": (
                "I’m not ready to answer document questions yet because the search index is empty.\n\n"
                "What to do:\n"
                "- Upload documents and wait for processing to finish\n"
                "- Then try your question again\n\n"
                "If you believe documents are already processed, go to Documents and reprocess, or use the RAG health tools."
            ),
            "sources": []
        }
    forced_context_files: List[str] = []

    # --- Best-practice multi-turn RAG: pin retrieval to recent cited sources ---
    # If the previous assistant turn cited sources, keep retrieval anchored to those files for follow-up questions.
    pinned_sources: List[str] = []
    if request.history:
        for msg in reversed(request.history):
            if getattr(msg, "role", None) == "assistant":
                srcs = getattr(msg, "sources", None)
                if srcs and isinstance(srcs, list):
                    pinned_sources = [s for s in srcs if isinstance(s, str) and s.strip()]
                    if pinned_sources:
                        break

    # Configurable cap for pinned files
    try:
        max_pinned = int((config or {}).get("rag", {}).get("max_pinned_files", 3))
    except Exception:
        max_pinned = 3
    max_pinned = max(1, min(max_pinned, 10))

    # Add pinned sources first (highest priority)
    if pinned_sources:
        for s in pinned_sources:
            if s not in forced_context_files:
                forced_context_files.append(s)
            if len(forced_context_files) >= max_pinned:
                break

        # Also expand to "related" docs by filename tokens (e.g., same vendor family across multiple agreements).
        # This is generic entity-style expansion, not word-specific heuristics.
        def _extract_filename_tokens(fn: str) -> List[str]:
            parts = fn.replace(".pdf", "").replace(".docx", "").replace("_", " ").split()
            toks = []
            for p in parts:
                pn = _normalize_token(p)
                if len(pn) >= 4:
                    toks.append(pn)
            return toks

        source_tokens: List[str] = []
        for s in forced_context_files:
            source_tokens.extend(_extract_filename_tokens(s))
        # Deduplicate while preserving order
        seen = set()
        source_tokens = [t for t in source_tokens if not (t in seen or seen.add(t))]

        for fname in (metadata.keys() if isinstance(metadata, dict) else []):
            if not isinstance(fname, str) or fname in forced_context_files:
                continue
            parts = fname.replace(".pdf", "").replace(".docx", "").replace("_", " ").split()
            fn_tokens = [_normalize_token(p) for p in parts if len(_normalize_token(p)) >= 4]
            matched = False
            for st in source_tokens[:8]:  # keep it bounded
                for ft in fn_tokens:
                    if st == ft or st in ft or ft in st:
                        matched = True
                        break
                    # Conservative fuzzy match
                    if _bounded_levenshtein(st, ft, 2) <= 2:
                        matched = True
                        break
                if matched:
                    break
            if matched:
                forced_context_files.append(fname)
                if len(forced_context_files) >= max_pinned:
                    break

    # Simple keyword matching in filenames (with light fuzzy matching for typos)
    query_lower = request.question.lower()
    query_words_norm = [_normalize_token(w) for w in query_lower.split()]
    query_words_norm = [w for w in query_words_norm if len(w) >= 3]
    for filename in metadata.keys():
        # Check if significant parts of the filename are in the query
        # e.g. "VENDOR" in "VENDOR_BRAWO_Supply..."
        # Split filename by common separators
        parts = filename.replace('.pdf', '').replace('.docx', '').replace('_', ' ').split()
        for part in parts:
            # Normalize the filename token for better matching (handles punctuation like "Vendor's")
            part_norm = _normalize_token(part)
            if len(part_norm) < 4:
                continue

            # Fast path: exact substring match against original query text
            if part.lower() in query_lower:
                forced_context_files.append(filename)
                break

            # Fuzzy path: tolerate small typos (e.g. vendrs/vendors vs vendor)
            # Pick a conservative max edit distance based on token length.
            if len(part_norm) <= 5:
                max_dist = 2
            elif len(part_norm) <= 8:
                max_dist = 2
            else:
                max_dist = 3

            matched = False
            for qw in query_words_norm:
                if len(qw) < 3:
                    continue
                # Quick prefix containment checks
                if qw in part_norm or part_norm in qw:
                    matched = True
                    break
                if _bounded_levenshtein(qw, part_norm, max_dist) <= max_dist:
                    matched = True
                    break

            if matched:
                forced_context_files.append(filename)
                break

    # Expand query using conversation history if the query is vague (contains pronouns)
    search_query = request.question
    vague_indicators = ['this', 'that', 'it', 'they', 'these', 'those', 'here', 'there']
    query_words = request.question.lower().split()
    is_vague_query = any(word in vague_indicators for word in query_words) and len(query_words) < 15

    if is_vague_query and request.history and len(request.history) > 0:
        # Extract key terms from recent conversation history to enhance the search
        logger.info(f"Detected vague query with pronouns, expanding using conversation history...")

        # Get the last few messages to extract context
        recent_history = request.history[-4:]  # Last 2 turns (4 messages)
        history_text = " ".join([msg.content for msg in recent_history])

        # Extract keywords from history
        history_keywords = extract_keywords(history_text)

        # Combine current query with history keywords for a richer search
        if history_keywords:
            # Add top keywords from history to the search query
            top_history_keywords = history_keywords[:5]  # Top 5 keywords from history
            search_query = f"{request.question} {' '.join(top_history_keywords)}"
            logger.info(f"Expanded search query: '{search_query}' (added keywords: {top_history_keywords})")

    # Perform HYBRID SEARCH using Reciprocal Rank Fusion (RRF)
    # Combines semantic vector search with keyword-based search for better results
    rag_debug = bool((config or {}).get("rag", {}).get("debug_logging", False))
    if rag_debug:
        logger.info(f"Performing hybrid search (RRF) for: '{search_query}'")

    # Determine how many results we need based on query type
    query_lower = search_query.lower()
    is_pricing_query = any(word in query_lower for word in ['pay', 'cost', 'price', 'fee', 'charge', 'hour', 'rate', 'per'])
    n_results = 8 if is_pricing_query else 5  # Get more results for pricing queries

    # Run hybrid search with the (possibly expanded) query
    hybrid_results = hybrid_search_rrf(search_query, collection, n_results=n_results * 2)

    # 2. Build Context from hybrid search results
    context_text = ""
    retrieved_files = set()

    # Add Forced Context first (high priority).
    # Keep the number of forced files bounded for latency and to avoid pulling in unrelated docs.
    forced_limit = max_pinned if pinned_sources else 1
    #
    # IMPORTANT: Do NOT re-read PDFs or run OCR during chat requests.
    # Chat must be low-latency and must not kick off heavyweight extraction.
    # Instead, reuse the already-indexed chunks stored in Chroma for this filename.
    for filename in forced_context_files[:forced_limit]:
        if collection is None:
            logger.warning(f"Forced context: Collection not initialized; cannot pull indexed chunks for {filename}")
            continue

        try:
            indexed = collection.get(where={"filename": filename}, include=["documents"])
            docs = indexed.get("documents") if indexed else None
            if not docs:
                logger.warning(f"Forced context: No indexed chunks found for {filename}; skipping (will not OCR during chat)")
                continue

            # Join a limited number of chunks to keep context bounded.
            # Chunks are already extracted/indexed during document processing.
            joined = "\n\n".join(docs[:25])
            context_text += f"--- INDEXED TEXT (chunks) from {filename} ---\n{joined[:50000]}\n\n"
            retrieved_files.add(filename)
            logger.info(f"Forced context: Added indexed chunks from {filename} (chunks={min(len(docs), 25)}, chars={len(joined)})")
        except Exception as e:
            logger.error(f"Forced context: Failed to load indexed chunks for {filename}: {e}")
            # Never fall back to OCR/pdf extraction during chat.
            continue

    # Add hybrid search results
    # Apply distance threshold to filter out semantically distant chunks
    # Chunks matched ONLY via keyword (no semantic match) are still included
    # Distance threshold: higher = more inclusive (OpenAI embeddings often need ~0.7+ for diluted-but-relevant chunks).
    # Configurable via config.yaml -> rag.distance_threshold (default 0.75) or env RAG_DISTANCE_THRESHOLD.
    DISTANCE_THRESHOLD = _get_distance_threshold()
    # For vague follow-up queries, only use top 1 result to avoid noise from unrelated docs
    if is_vague_query:
        max_chunks = 1
    elif is_pricing_query:
        max_chunks = 5
    else:
        max_chunks = 3
    chunks_added = 0
    relevant_chunks = []

    if rag_debug:
        logger.info(f"=== FILTERING HYBRID RESULTS (threshold={DISTANCE_THRESHOLD}) ===")
    for result in hybrid_results:
        if chunks_added >= max_chunks:
            break

        filename = result.get('filename', 'unknown')
        doc = result.get('doc', '')
        semantic_distance = result.get('semantic_distance')
        matched_keywords = result.get('matched_keywords', [])
        has_keyword_match = matched_keywords and len(matched_keywords) > 0

        if rag_debug:
            logger.info(f"  Evaluating: {filename[:50]} | dist={semantic_distance} | keywords={matched_keywords}")

        # Filter: If chunk only has semantic match (no keyword match), require low distance
        # If chunk has keyword match, include it even if semantic distance is high
        if semantic_distance is not None and not has_keyword_match:
            if semantic_distance > DISTANCE_THRESHOLD:
                if rag_debug:
                    logger.info(f"  -> SKIPPED: distance {semantic_distance:.3f} > {DISTANCE_THRESHOLD}, no keywords")
                continue

        if rag_debug:
            logger.info(f"  -> INCLUDED")

        # Skip if we already have this document from forced context
        if filename in retrieved_files:
            continue

        retrieved_files.add(filename)
        context_text += f"--- Excerpt from {filename} ---\n{doc}\n\n"
        chunks_added += 1

        # Track for logging
        relevant_chunks.append(result)

        sem_rank = result.get('semantic_rank', '-')
        kw_rank = result.get('keyword_rank', '-')
        rrf_score = result.get('score', 0)
        matched_kw = result.get('matched_keywords', [])
        if rag_debug:
            logger.info(f"Added chunk from {filename} (RRF={rrf_score:.4f}, sem_rank={sem_rank}, kw_rank={kw_rank}, keywords={matched_kw})")

    # Keep logs minimal by default (avoid leaking document excerpts/prompts into logs).
    if rag_debug:
        logger.info(f"Final: Added {chunks_added} chunks from {len(retrieved_files)} documents via hybrid search")
        logger.info(f"RAG retrieved context from {len(retrieved_files)} files: {retrieved_files}")
        logger.info(f"Total context length: {len(context_text)} characters")

    # 3. Call LLM with conversation history
    current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")

    system_prompt = prompts_config.get("prompts", {}).get("chat", {}).get("system", "You are a helpful assistant.")
    user_prompt_template = prompts_config.get("prompts", {}).get("chat", {}).get("user", "Context:\n{context_text}\n\nQuestion: {question}")

    # Build the current user message with context
    user_prompt = user_prompt_template.format(
        current_date=current_date,
        context_text=context_text,
        question=request.question
    )

    # Build messages array with conversation history
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history if provided (limit to last 10 turns to manage token usage)
    if request.history:
        history_count = min(len(request.history), 10)
        logger.info(f"Including {history_count} previous messages from conversation history")

        for msg in request.history[-10:]:  # Last 10 messages
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})

    # Add the current question with context
    messages.append({"role": "user", "content": user_prompt})

    if rag_debug:
        logger.info(f"=== LLM REQUEST ===")
        logger.info(f"  Total messages: {len(messages)} (1 system + {len(messages)-2} history + 1 current)")
        logger.info(f"=== END LLM REQUEST PREVIEW ===")

    response = openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages
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

@app.on_event("startup")
async def startup_event():
    """Run cleanup on startup to remove any legacy zip files from repo root"""
    global rag_init_state, rag_init_error
    cleanup_root_zip_artifacts()
    logger.info("Cleaned up any legacy zip files from repo root")
    # Kick off RAG initialization in a background thread so Uvicorn can start responding immediately.
    # This prevents the Electron UI from appearing "stuck" while heavy imports (chromadb) run.
    if rag_init_state == "not_started":
        rag_init_state = "initializing"
        rag_init_error = None

        async def _init_rag_async():
            global rag_init_state, rag_init_error
            try:
                ok = await asyncio.to_thread(initialize_openai_client)
                # Missing API key isn't an error; it simply disables RAG.
                rag_init_state = "ready" if ok else "disabled"
            except Exception as e:
                rag_init_state = "error"
                rag_init_error = str(e)
                logger.error(f"RAG initialization failed: {e}")

        asyncio.create_task(_init_rag_async())

if __name__ == "__main__":
    print("Starting FastAPI server...")
    port = int(os.environ.get("PORT", 8000))
    # Keep our application logs, but avoid spamming stdout with access logs
    # (e.g. repeated GET /health, /config, /documents from the UI polling).
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
