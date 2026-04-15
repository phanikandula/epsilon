
<div align="center">
  <video src="https://github.com/user-attachments/assets/b4a5bdab-ce8a-415a-b65f-775fa72443cb" width="100%" controls autoplay loop>
  </video>
</div>


# **Epsilon (ε)**

In mathematics, **ε** represents a small positive quantity. This agent is the **Epsilon** of your workflow: the small, positive bridge that closes the gap between your intention and your code.

## **🧬 Philosophy**

Epsilon is a minimal, secure, and fully transparent coding harness. Unlike complex, multi-layered agents, Epsilon stays in your terminal, runs on your local GPU (via Ollama), and provides a direct, human-in-the-loop interface to your filesystem.

## **🚀 Quick Start**

1. **Install uv**: curl \-LsSf https://astral.sh/uv/install.sh | sh  
2. **Install Ollama & Gemma 4**: ollama pull gemma4:26b  
3. **Sync & Run**:  
   uv sync  
   uv run agent.py \--id dev-session

### **🌍 Global Access**

To run Epsilon from any directory, create a script named epsilon in your path (e.g., /usr/local/bin/epsilon):

```shell
#!/bin/bash  
# Absolute path to your Epsilon installation  
EPSILON_DIR="/path/to/your/cloned/epsilon"

uv run --project "${EPSILON_DIR}" "${EPSILON_DIR}/agent.py" "$@"
```

*Note: Update EPSILON\_DIR to your actual installation path and run chmod \+x on the script.*

## **🛠️ Deep Agent Features**

* **Fuzzy @Mentions**: Type @ to search and inject file contents into your prompt.  
* **Multimodal Context**: Use /paste to share screenshots (multimodal) or long text blocks from your clipboard.  
* **Deep Reasoning Tools**: Built-in support for planning (todo), semantic search (grep), and smart file reading.  
* **Persistent Memory**: Conversations are stored in a local SQLite database inside .epsilon/.  
* **Sovereign Security**: Written in pure Python. Every action requires explicit y/n confirmation.

## **🔌 Extensibility**

Drop new .py files into the tools/ folder. Define a register() function to expose your custom Python functions to Epsilon.

## **⚖️ License**

MIT
