"""
transpiler/cache_manager.py — Incremental compilation cache for RPy.
"""

from __future__ import annotations
import hashlib
import json
import os
import pickle
from typing import Optional, Any
from transpiler import ir

class CacheManager:
    def __init__(self, cache_dir: str = ".rpy_cache"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _get_hash(self, source: str) -> str:
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def get_cached_ir(self, source: str) -> Optional[ir.IRModule]:
        h = self._get_hash(source)
        path = os.path.join(self.cache_dir, f"{h}.ir")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None
        return None

    def save_ir(self, source: str, ir_module: ir.IRModule):
        h = self._get_hash(source)
        path = os.path.join(self.cache_dir, f"{h}.ir")
        try:
            with open(path, "wb") as f:
                pickle.dump(ir_module, f)
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")

# Global cache instance
cache = CacheManager()
