import os
from langchain_core.tools import tool
from pathlib import Path
from typing import Annotated

# Safety: Prevent operations outside the allowed base directory
PROJECT_ROOT = Path(os.getcwd()).resolve().parent.parent if "services" in os.getcwd() else Path(os.getcwd()).resolve()

def _is_safe_path(path: str) -> bool:
    try:
        requested = (PROJECT_ROOT / path).resolve()
        return requested.is_relative_to(PROJECT_ROOT) or "woorung-gaksi" in str(requested)
    except Exception:
        return False

@tool
def read_file(file_path: Annotated[str, "Relative path to file (e.g., 'services/core-gateway/main.go')"]) -> str:
    """Read contents of a file."""
    if not _is_safe_path(file_path):
        return f"Error: Path '{file_path}' is outside the allowed project directory."
        
    full_path = PROJECT_ROOT / file_path
    if not full_path.exists():
        return f"Error: File '{file_path}' not found."
        
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def write_file(file_path: Annotated[str, "Relative path"], content: Annotated[str, "Content to write"]) -> str:
    """Write content to a file. Use this to create or update files."""
    if not _is_safe_path(file_path):
        return f"Error: Path '{file_path}' is outside the allowed project directory."
        
    full_path = PROJECT_ROOT / file_path
    
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File '{file_path}' written successfully."
    except Exception as e:
        return f"Error writing file: {str(e)}"

@tool
def list_dir(dir_path: Annotated[str, "Directory path"] = ".") -> str:
    """List files in a directory."""
    if not _is_safe_path(dir_path):
        return f"Error: Path '{dir_path}' is outside the allowed project directory."
        
    full_path = PROJECT_ROOT / dir_path
    if not full_path.exists():
        return f"Error: Directory '{dir_path}' not found."
        
    try:
        items = os.listdir(full_path)
        # Filter hidden files/dirs to keep output clean
        visible_items = [i for i in items if not i.startswith('.')]
        return "\n".join(visible_items) or "(Empty directory)"
    except Exception as e:
        return f"Error listing directory: {str(e)}"
