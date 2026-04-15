import os

def write_file(path: str, content: str):
    """Writes content to a file. Used to create or update project files."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Successfully updated {path}"

def read_file(path: str):
    """Reads a file and returns its raw string content."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def list_dir(path: str = "."):
    """Lists files in a directory to understand project structure."""
    return str(os.listdir(path))

def register():
    """Exposes tools to the Epsilon agent core."""
    return {
        "write_file": write_file,
        "read_file": read_file,
        "list_dir": list_dir
    }
