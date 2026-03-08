import sys
from pathlib import Path

# Add the project root to sys.path
root = Path(__file__).parent.parent
sys.path.append(str(root))

try:
    from transpiler import node_registry
    print("Successfully imported node_registry")
    import transpiler.handlers
    print("Successfully imported handlers")
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Error: {e}")
