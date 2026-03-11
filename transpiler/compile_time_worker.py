import contextlib
import subprocess
import ast
import json
import sys
import os
import importlib.util
from typing import Any

def execute_macro(node: ast.Call, file_path: str | None) -> Any:
    """Invokes the current file as a script to run the compile-time function."""
    if not file_path: return None
    
    # We'll call ourselves (compile_time_worker.py)
    # This ensures a clean sandbox for the user code
    curr_script = __file__
    
    func_name = node.func.id if isinstance(node.func, ast.Name) else ""
    # Simplified: extract literal args only for now
    args = []
    for arg in node.args:
        if isinstance(arg, ast.Constant):
            args.append(arg.value)
            
    payload = json.dumps({
        "file_path": file_path,
        "func_name": func_name,
        "args": args
    })
    
    try:
        proc = subprocess.run(
            [sys.executable, curr_script],
            input=payload.encode("utf-8"),
            capture_output=True,
            check=True
        )
        resp = json.loads(proc.stdout.decode("utf-8"))
        if resp.get("status") == "success":
            return resp.get("result")
        else:
            print(f"Macro Error: {resp.get('message')}")
            return None
    except Exception as e:
        print(f"Macro Execution failed: {e}")
        return None

def main():
    try:
        data = json.loads(sys.stdin.read())
        file_path = data.get("file_path")
        func_name = data.get("func_name")
        args = data.get("args", [])
        
        if not file_path or not func_name:
            print(json.dumps({"status": "error", "message": "Missing file_path or func_name"}))
            return

        # Load the user module
        # Note: We append the project root to sys.path
        project_root = os.path.dirname(os.path.abspath(file_path))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        module_name = "rpy_compile_target"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            print(json.dumps({"status": "error", "message": f"Could not load {file_path}"}))
            return

        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(sys.stderr):
            spec.loader.exec_module(module)

        func = getattr(module, func_name, None)
        if not func:
            print(json.dumps({"status": "error", "message": f"Function {func_name} not found in {file_path}"}))
            return

        # Run the function
        result = func(*args)

        # Validate result (must be serializable)
        # json.dumps will raise TypeError if not serializable
        try:
            json_result = json.dumps({"status": "success", "result": result})
            print(json_result)
        except TypeError as e:
            print(json.dumps({"status": "error", "message": f"Result not serializable: {e}"}))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()
