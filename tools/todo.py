import os

def manage_todo(action: str, task: str = ""):
    """
    Manages a persistent TODO list to keep the agent focused on long tasks.
    Actions: 'add', 'list', 'complete', 'clear'.
    """
    todo_file = ".epsilon_todo.md"
    
    if action == "add":
        with open(todo_file, "a") as f:
            f.write(f"- [ ] {task}\n")
        return f"Added to plan: {task}"
    
    elif action == "list":
        if not os.path.exists(todo_file):
            return "No active plan."
        with open(todo_file, "r") as f:
            return f"Current Plan:\n{f.read()}"
            
    elif action == "complete":
        if not os.path.exists(todo_file): return "No plan found."
        with open(todo_file, "r") as f:
            lines = f.readlines()
        new_lines = [l.replace("[ ]", "[x]") if task in l else l for l in lines]
        with open(todo_file, "w") as f:
            f.writelines(new_lines)
        return f"Marked task as complete: {task}"
    
    elif action == "clear":
        if os.path.exists(todo_file): os.remove(todo_file)
        return "Plan cleared."

def register():
    return {"manage_todo": manage_todo}
