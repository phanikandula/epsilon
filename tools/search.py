import os
import re

def grep_search(pattern: str, file_pattern: str = "*"):
    """
    Searches for a regex pattern in files. Useful for finding definitions without reading everything.
    """
    results = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        for file in files:
            if file.endswith(file_pattern.replace("*", "")):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if re.search(pattern, line):
                                results.append(f"{path}:{i+1}: {line.strip()}")
                except: continue
    
    if not results: return "No matches found."
    return "\n".join(results[:20]) + ("\n...truncated" if len(results) > 20 else "")

def register():
    return {"grep_search": grep_search}
