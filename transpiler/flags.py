from dataclasses import dataclass

@dataclass
class CompilerFlags:
    typed: bool = False      # --typed  : emit Luau type annotations
    fast: bool = False       # --fast   : skip py_bool() shims
    no_runtime: bool = False # --no-runtime : don't prepend runtime at all
    shared_runtime: bool = False # --shared-runtime : use require() instead of injection
    source_refs: bool = False    # --source-refs : emit source line references as comments
    compile_time: bool = False   # --compile-time : enable build-time Python execution
    script_type: str = "module" # --script_type : "module", "server", "client"
    show_out: bool = False      # --show-out : reveal the hidden out folder
    backup_studio: bool = False # --backup-studio : archive scripts before overwrite
