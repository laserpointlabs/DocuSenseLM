import compileall
from pathlib import Path
import sys


def compile_dir(path: Path) -> bool:
    if not path.exists():
        return True  # skip missing optional dirs
    return compileall.compile_dir(str(path), quiet=1)


def main() -> int:
    # Directories containing project python code
    candidates = [
        Path("api"),
        Path("llm"),
        Path("ingest"),
        Path("python"),
    ]

    ok = True
    for candidate in candidates:
        ok = compile_dir(candidate) and ok

    # Fallback: compile standalone files in repo root if needed
    root_py_files = list(Path(".").glob("*.py"))
    if root_py_files:
        ok = compileall.compile_dir(".", quiet=1, maxlevels=0) and ok

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

