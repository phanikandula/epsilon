import os
import json
import sqlite3
import base64
import re
import argparse
import importlib.util
from io import BytesIO
from datetime import datetime

import ollama
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from fuzzyfinder import fuzzyfinder
from PIL import Image, ImageGrab
import pyperclip

# --- CONFIG ---
MODEL_NAME = "gemma4:26b"
# --- PATH RESOLUTION ---
# BASE_DIR is the installation directory of Epsilon
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGINS_DIR = os.path.join(BASE_DIR, "tools")

# Data directory for session DB and terminal history
DATA_DIR = os.path.join(BASE_DIR, ".epsilon")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_PATH = os.path.join(DATA_DIR, "epsilon_sessions.db")
HISTORY_FILE = os.path.join(DATA_DIR, ".epsilon_history")

# --- CONSTRAINTS ---
MAX_INJECTION_CHARS = 100000  # Safety limit for @file content injection
MAX_TURNS = 10  # Safeguard against infinite loops
MEMORY_WINDOW = 20 # Max messages to keep in active memory/persistence
MAX_CONTEXT_CHARS = 100000 # Rough estimate to prevent context window blowout
MAX_TOOL_OUTPUT_CHARS = 50000 # Prevent SQLite/RAM bloating from massive tool outputs

# --- SECURITY ---
SENSITIVE_PATTERNS = [
    r'\.env$', r'\.ssh/', r'id_rsa', r'\.pgpass', r'key\.json', r'\.bash_history', r'\.zsh_history'
]
console = Console()

class FuzzyFileCompleter(Completer):
    def __init__(self):
        self.file_cache = []
        self.last_cache_time = 0

    def refresh_cache(self):
        now = datetime.now().timestamp()
        if now - self.last_cache_time < 10: return
        files_found = []
        # Walk user's current working directory
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules' and d != '.venv']
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), ".")
                files_found.append(rel_path)
        self.file_cache = files_found
        self.last_cache_time = now

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if '@' in text:
            parts = text.split('@')
            query = parts[-1]
            self.refresh_cache()
            suggestions = fuzzyfinder(query, self.file_cache)
            for path in suggestions:
                ext = os.path.splitext(path)[1].upper() or "FILE"
                yield Completion(path, start_position=-len(query), display=path, display_meta=ext)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, history TEXT, updated_at TEXT)")

def save_session(session_id, messages):
    serializable_history = []
    # Save the windowed version of history
    history_to_save = trim_messages(messages)

    for m in history_to_save:
        if hasattr(m, 'model_dump'):
            serializable_history.append(m.model_dump())
        elif hasattr(m, 'dict'):
            serializable_history.append(m.dict())
        elif not isinstance(m, dict):
            msg_dict = {'role': m.role, 'content': m.content}
            if hasattr(m, 'tool_calls') and m.tool_calls:
                msg_dict['tool_calls'] = [
                    {'function': {'name': tc.function.name, 'arguments': tc.function.arguments}}
                    for tc in m.tool_calls
                ]
            if hasattr(m, 'images') and m.images:
                msg_dict['images'] = m.images
            serializable_history.append(msg_dict)
        else:
            serializable_history.append(m)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (id, history, updated_at) VALUES (?, ?, ?)",
                (session_id, json.dumps(serializable_history), datetime.now().isoformat())
            )
    except Exception as e:
        console.print(f"[red]Database Error: {e}[/red]")

def load_session(session_id):
    if not os.path.exists(DB_PATH): return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT history FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row: return json.loads(row[0])
    return None

def load_all_tools():
    tools = {}
    if not os.path.exists(PLUGINS_DIR): os.makedirs(PLUGINS_DIR)
    for filename in os.listdir(PLUGINS_DIR):
        if filename.endswith(".py"):
            path = os.path.join(PLUGINS_DIR, filename)
            spec = importlib.util.spec_from_file_location(filename[:-3], path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "register"): tools.update(mod.register())
    return tools

def trim_messages(messages):
    """
    Sliding window: Keeps the system prompt (index 0) and the
    most recent (MEMORY_WINDOW - 1) messages.
    """
    if len(messages) <= MEMORY_WINDOW:
        return messages

    system_prompt = messages[0] if messages[0].get('role') == 'system' else None

    if system_prompt:
        return [system_prompt] + messages[-(MEMORY_WINDOW - 1):]
    return messages[-MEMORY_WINDOW:]

def check_context_size(messages):
    total_chars = sum(len(str(m.get('content', ''))) for m in messages)
    if total_chars > MAX_CONTEXT_CHARS:
        console.print(f"[yellow]⚠️ Context high ({total_chars} chars). Trimming active history.[/yellow]")
        return True
    return False

def run_agent(session_id, task=None):
    history = load_session(session_id) or [{"role": "system", "content": "You are Epsilon (ε). You are a small positive bridge between intention and code. Use tools precisely."}]
    messages = history
    tools_map = load_all_tools()
    input_session = PromptSession(history=FileHistory(HISTORY_FILE), completer=FuzzyFileCompleter(), complete_while_typing=True)
    
    console.print(Panel(f"[bold magenta]Epsilon (ε) Deep Agent[/bold magenta]\n[dim]Working in: {os.getcwd()}[/dim]\n[dim]Memory Window: {MEMORY_WINDOW} | Max Loop: {MAX_TURNS}[/dim]", title="ε Active"))

    while True:
        try:
            if task: user_input, task = task, None
            else: user_input = input_session.prompt("\nε > ").strip()
            
            if not user_input: continue
            if user_input.lower() in ["/exit", "exit", "quit"]: break
            if user_input.lower() == "/clear":
                messages = [messages[0]]; console.print("[yellow]Context reset.[/yellow]"); continue

            # --- Paste Handler ---
            if user_input.startswith("/paste"):
                img = ImageGrab.grabclipboard()
                if isinstance(img, Image.Image):
                    buf = BytesIO(); img.save(buf, format="PNG")
                    img_b64 = base64.b64encode(buf.getvalue()).decode()
                    messages.append({"role": "user", "content": "Screenshot attached:", "images": [img_b64]})
                    console.print("[magenta]📷 screenshot injected.[/magenta]")
                else:
                    text = pyperclip.paste()
                    messages.append({"role": "user", "content": f"Clipboard content:\n\n{text}"})
                    console.print("[magenta]📋 text injected.[/magenta]")
                continue

            # --- @mention Injection ---
            mentions = re.findall(r'@(\S+)', user_input)
            for path in mentions:
                is_sensitive = any(re.search(pattern, path) for pattern in SENSITIVE_PATTERNS)
                if is_sensitive:
                    console.print(f"[red]🚫 Access Denied: {path} is flagged as sensitive.[/red]")
                    continue

                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if len(content) > MAX_INJECTION_CHARS:
                            content = content[:MAX_INJECTION_CHARS] + "\n\n...[Truncated]..."
                        user_input += f"\n\n--- FILE: {path} ---\n{content}\n"
                    console.print(f"[dim]📎 Injected {path}[/dim]")

            messages.append({"role": "user", "content": user_input})
            if check_context_size(messages):
                messages = trim_messages(messages)

            # --- The Work Loop ---
            turn_count = 0
            while turn_count < MAX_TURNS:
                turn_count += 1
                with Status(f"[bold magenta]ε thinking (Turn {turn_count}/{MAX_TURNS})...", spinner="dots12"):
                    try:
                        response = ollama.chat(model=MODEL_NAME, messages=messages, tools=list(tools_map.values()))
                    except Exception as e:
                        console.print(f"\n[bold red]Ollama Connection Error:[/bold red] {e}")
                        break

                msg = response.message
                messages.append(msg)

                if not msg.tool_calls:
                    console.print("\n[bold magenta]ε:[/bold magenta]")
                    console.print(Markdown(msg.content or ""))
                    break

                for call in msg.tool_calls:
                    func, args = call.function.name, call.function.arguments

                    # 1. Handle missing tools (The "Dangling Tool" Problem)
                    if func not in tools_map:
                        res = f"Error: Tool '{func}' is not available."
                        messages.append({'role': 'tool', 'content': res, 'name': func})
                        console.print(f"[red]❌ Missing Tool: {func}[/red]")
                        continue

                    console.print(f"\n[bold yellow]🛠️  ACTION:[/bold yellow] {func}({args})")
                    if console.input("[bold red]Allow? (y/n): [/bold red]").lower() == "y":
                        try:
                            # 2. Execution & Serialization
                            raw_res = tools_map[func](**args)
                            res = json.dumps(raw_res) if isinstance(raw_res, (dict, list)) else str(raw_res)

                            # Size Guard for Database/Context Window
                            if len(res) > MAX_TOOL_OUTPUT_CHARS:
                                res = res[:MAX_TOOL_OUTPUT_CHARS] + "\n\n...[Output Truncated]..."

                            console.print(f"[green]✅ Success[/green]")
                        except Exception as tool_err:
                            res = f"Tool Failure: {str(tool_err)}"
                            console.print(f"[bold red]Tool Error:[/bold red] {str(tool_err)}")

                        # Map the result back to the model as a 'tool' role response
                        messages.append({'role': 'tool', 'content': res, 'name': func})
                    else:
                        # Return to model as 'tool' role to preserve turn-taking sequence
                        deny_msg = "Error: Operation denied by the user. Reason: User policy."
                        messages.append({'role': 'tool', 'content': deny_msg, 'name': func})
                        console.print(f"[red]🚫 Denied by user.[/red]")

                # Save and Trim after the whole tool-turn is complete
                messages = trim_messages(messages)
                save_session(session_id, messages)

            if turn_count >= MAX_TURNS:
                console.print("\n[bold red]⚠️ Loop threshold reached. Stopping for safety.[/bold red]")

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print("\n[bold red]Fatal System Error:[/bold red]")
            console.print(str(e), style="red", markup=False)

if __name__ == "__main__":
    init_db()
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default="epsilon-dev")
    parser.add_argument("--task", help="Optional starting task")
    args = parser.parse_args()
    run_agent(args.id, args.task)
