import os
from pathlib import Path
import easyocr


def main():
    models_dir = os.environ.get("EASYOCR_MODELS_DIR")
    if not models_dir:
        project_root = Path(__file__).resolve().parents[1]
        models_dir = project_root / "tools" / "easyocr_models"
    models_path = Path(models_dir)
    models_path.mkdir(parents=True, exist_ok=True)

    print(f"Downloading EasyOCR models to {models_path}...")
    # Instantiating the reader forces model download if missing
    easyocr.Reader(["en"], gpu=False, verbose=True, model_storage_directory=str(models_path))
    print("Download complete.")


if __name__ == "__main__":
    main()


