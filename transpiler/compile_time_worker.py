import sys
import json
import importlib.util
import os
import contextlib

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
