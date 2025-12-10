"""
Download EasyOCR models to a local directory for faster initialization.
This script pre-downloads the English language models so they're available
during build and runtime without network access.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import easyocr
sys.path.insert(0, os.path.dirname(__file__))

try:
    import easyocr
except ImportError:
    print("ERROR: easyocr is not installed. Please run: pip install easyocr")
    sys.exit(1)


def download_models(models_dir: str):
    """Download EasyOCR models to the specified directory."""
    models_path = Path(models_dir)
    models_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading EasyOCR models to: {models_path}")
    print("This may take a few minutes on first run...")
    
    try:
        # Initialize reader with custom model directory
        # This will download models if they don't exist
        reader = easyocr.Reader(
            ["en"],
            gpu=False,
            verbose=True,  # Show progress
            model_storage_directory=str(models_path)
        )
        print(f"✅ Successfully downloaded models to: {models_path}")
        print(f"Model files are now available at: {models_path}")
        return True
    except Exception as e:
        print(f"❌ Error downloading models: {e}")
        return False


if __name__ == "__main__":
    # Default to tools/easyocr_models in project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    default_models_dir = project_root / "tools" / "easyocr_models"
    
    # Allow override via environment variable
    models_dir = os.environ.get("EASYOCR_MODELS_DIR", str(default_models_dir))
    
    print(f"EasyOCR Model Download Script")
    print(f"Target directory: {models_dir}")
    print()
    
    success = download_models(models_dir)
    sys.exit(0 if success else 1)

