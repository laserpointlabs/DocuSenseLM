import io
import os
from typing import List
from pathlib import Path

import easyocr
import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastmcp import FastMCP

app = FastAPI(title="MCP OCR Server")
mcp = FastMCP("mcp-ocr")

_reader = None


def get_models_directory():
    """Get the path to the local EasyOCR models directory.
    
    Checks in order:
    1. EASYOCR_MODELS_DIR environment variable
    2. tools/easyocr_models in project root (development)
    3. resources/tools/easyocr_models (built application)
    4. resources/easyocr_models (alternative built location)
    """
    # Check for environment variable first
    env_dir = os.environ.get("EASYOCR_MODELS_DIR")
    if env_dir and os.path.isdir(env_dir):
        return env_dir
    
    current_file = Path(__file__)
    python_dir = current_file.parent.parent
    
    # Try development location: project_root/tools/easyocr_models
    project_root = python_dir.parent
    models_dir = project_root / "tools" / "easyocr_models"
    if models_dir.exists() and models_dir.is_dir():
        return str(models_dir)
    
    # Try built application location: resources/tools/easyocr_models
    # (when running from release/win-unpacked/resources/python/...)
    # Structure: resources/python/mcp_ocr_server/main.py -> resources/tools/easyocr_models
    if python_dir.name == "python":
        resources_dir = python_dir.parent / "tools" / "easyocr_models"
        if resources_dir.exists() and resources_dir.is_dir():
            return str(resources_dir)
        
        # Try alternative built location: resources/easyocr_models
        alt_resources_dir = python_dir.parent / "easyocr_models"
        if alt_resources_dir.exists() and alt_resources_dir.is_dir():
            return str(alt_resources_dir)
    
    return None


def get_reader():
    """Lazy initialization of easyocr reader."""
    global _reader
    if _reader is None:
        models_dir = get_models_directory()
        reader_kwargs = {
            "lang_list": ["en"],
            "gpu": False,
            "verbose": False,
        }
        
        # Use local models if available
        if models_dir:
            reader_kwargs["model_storage_directory"] = models_dir
            reader_kwargs["download_enabled"] = False  # Don't download if missing
            print(f"Using local EasyOCR models from: {models_dir}")
        else:
            print("Using default EasyOCR model location (will download if needed)")
        
        _reader = easyocr.Reader(**reader_kwargs)
    return _reader


def pdf_pages_to_images(data: bytes, dpi: int = 200) -> List[bytes]:
    images = []
    doc = fitz.open(stream=data, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        images.append(pix.tobytes("png"))
    return images


def ocr_bytes(img_bytes: bytes) -> str:
    reader = get_reader()
    result = reader.readtext(img_bytes, detail=0)
    return "\n".join(result).strip() if result else ""


@app.post("/ocr_pdf")
async def ocr_pdf(file: UploadFile = File(...)):
    data = await file.read()
    images = pdf_pages_to_images(data)
    texts = []
    for img in images:
        text = ocr_bytes(img)
        texts.append(text)
    return {"pages": texts}


@app.post("/ocr_page")
async def ocr_page(file: UploadFile = File(...)):
    data = await file.read()
    text = ocr_bytes(data)
    return {"text": text}


@app.post("/classify_snippet")
async def classify_snippet(file: UploadFile = File(...)):
    data = await file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    if doc.page_count == 0:
        raise HTTPException(status_code=400, detail="Empty PDF")
    page0 = doc.load_page(0)
    pix = page0.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")
    text = ocr_bytes(img_bytes)
    return {"snippet": text}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("MCP_OCR_PORT", "8001")))


