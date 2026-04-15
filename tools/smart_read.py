import os

def smart_read(path: str, max_chars: int = 2000):
    """
    Reads a file but prevents context overflow by truncating and summarizing large files.
    """
    if not os.path.exists(path):
        return f"Error: {path} not found."
        
    size = os.path.getsize(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if len(content) <= max_chars:
        return content
        
    # Truncate and add a "Deep Agent" meta-comment
    preview = content[:max_chars // 2]
    suffix = content[-max_chars // 2:]
    
    return (
        f"--- LARGE FILE TRUNCATED ({size} bytes) ---\n"
        f"PREVIEW:\n{preview}\n"
        f"...\n"
        f"END OF FILE:\n{suffix}\n"
        f"--- USE grep_search TO FIND SPECIFIC DETAILS ---"
    )

def register():
    return {"smart_read": smart_read}
