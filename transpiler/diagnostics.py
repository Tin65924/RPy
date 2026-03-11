"""
transpiler/diagnostics.py — Centralized diagnostic engine for RPy.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

class Severity(Enum):
    ERROR = auto()
    WARNING = auto()
    HINT = auto()

@dataclass
class Diagnostic:
    message: str
    severity: Severity
    line: Optional[int] = None
    col: Optional[int] = None
    filename: Optional[str] = None
    hint: Optional[str] = None

class DiagnosticManager:
    def __init__(self, silent: bool = False):
        self.diagnostics: List[Diagnostic] = []
        self.silent = silent

    def clear(self):
        self.diagnostics = []

    def report(self, message: str, severity: Severity, line: Optional[int] = None, 
               col: Optional[int] = None, filename: Optional[str] = None, hint: Optional[str] = None):
        diag = Diagnostic(message, severity, line, col, filename, hint)
        self.diagnostics.append(diag)
        if not self.silent:
            formatted = self._format(diag)
            try:
                print(formatted)
            except UnicodeEncodeError:
                # Fallback for terminals that don't support the characters (common on Windows)
                print(formatted.encode('ascii', errors='replace').decode('ascii'))

    def error(self, message: str, line: Optional[int] = None, col: Optional[int] = None, filename: Optional[str] = None, hint: Optional[str] = None):
        self.report(message, Severity.ERROR, line, col, filename, hint)

    def warning(self, message: str, line: Optional[int] = None, col: Optional[int] = None, filename: Optional[str] = None, hint: Optional[str] = None):
        self.report(message, Severity.WARNING, line, col, filename, hint)

    def hint(self, message: str, line: Optional[int] = None, col: Optional[int] = None, filename: Optional[str] = None, hint: Optional[str] = None):
        self.report(message, Severity.HINT, line, col, filename, hint)

    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self.diagnostics)

    def _format(self, diag: Diagnostic) -> str:
        loc = f"{diag.filename or ''}:{diag.line or ''}:{diag.col or ''}".strip(":")
        severity_str = {
            Severity.ERROR: "\033[91m[Error]\033[0m",
            Severity.WARNING: "\033[93m[Warning]\033[0m",
            Severity.HINT: "\033[94m[Hint]\033[0m"
        }[diag.severity]
        
        msg = f"{severity_str} {loc}: {diag.message}"
        if diag.hint:
            msg += f"\n  -> {diag.hint}"
        return msg

# Global manager instance
manager = DiagnosticManager()
