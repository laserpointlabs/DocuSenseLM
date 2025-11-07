#!/usr/bin/env python3
"""
Syntax checker for all Python files in the project.
This script compiles all Python files to check for syntax errors.
"""
import os
import sys
import py_compile
from pathlib import Path

def check_file(filepath):
    """Check if a Python file compiles correctly."""
    try:
        py_compile.compile(filepath, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"

def main():
    """Check all Python files in the project."""
    project_root = Path(__file__).resolve().parent.parent
    python_dirs = ['api', 'llm', 'ingest', 'scripts', 'eval', 'tests']
    
    errors = []
    checked = 0
    
    for dir_name in python_dirs:
        dir_path = project_root / dir_name
        if not dir_path.exists():
            continue
            
        for py_file in dir_path.rglob('*.py'):
            # Skip __pycache__ directories
            if '__pycache__' in str(py_file):
                continue
            
            checked += 1
            success, error = check_file(str(py_file))
            if not success:
                errors.append((str(py_file.relative_to(project_root)), error))
    
    print(f"Checked {checked} Python files")
    
    if errors:
        print(f"\n❌ Found {len(errors)} syntax errors:\n")
        for filepath, error in errors:
            print(f"  {filepath}:")
            print(f"    {error}\n")
        sys.exit(1)
    else:
        print("✓ All Python files have valid syntax")
        return 0

if __name__ == '__main__':
    sys.exit(main())

