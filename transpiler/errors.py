"""
transpiler/errors.py — Compiler error hierarchy for RPy.

All errors produced by the transpiler should be instances of TranspileError
or one of its subclasses.  They carry source location information and a
human-readable message so that CLI output is immediately actionable.
"""

from __future__ import annotations


def _fmt_location(filename: str | None, line: int | None, col: int | None) -> str:
    """Format 'file.py:12:5' or just ':12' or '' depending on what's available."""
    parts: list[str] = []
    if filename:
        parts.append(filename)
    if line is not None:
        parts.append(str(line))
    if col is not None:
        parts.append(str(col))
    return ":".join(parts) if parts else "<unknown>"


class TranspileError(Exception):
    """
    Base class for all errors raised during transpilation.

    Attributes:
        message:  Human-readable description of the problem.
        line:     1-indexed source line number (None if unknown).
        col:      1-indexed column offset (None if unknown).
        filename: Source file path (None if transpiling a string).
        hint:     Optional suggestion shown below the main message.
    """

    def __init__(
        self,
        message: str,
        line: int | None = None,
        col: int | None = None,
        filename: str | None = None,
        hint: str | None = None,
    ) -> None:
        self.message = message
        self.line = line
        self.col = col
        self.filename = filename
        self.hint = hint
        # Call Exception.__init__ last so __str__ has all attrs available.
        Exception.__init__(self, str(self))

    def __str__(self) -> str:
        location = _fmt_location(self.filename, self.line, self.col)
        base = f"[TranspileError] {location}: {self.message}"
        if self.hint:
            base += f"\n  Hint: {self.hint}"
        return base

    def format_with_context(self, source: str | None = None) -> str:
        """Return the error message, optionally including the source line context."""
        base = str(self)
        if source and self.line is not None:
            lines = source.splitlines()
            if 0 < self.line <= len(lines):
                error_line = lines[self.line - 1]
                # Indent the source line for clarity
                base += f"\n\n    {error_line.strip()}"
                if self.col is not None:
                    # Simple pointer to the column (if available)
                    # Note: .strip() above changes offsets, so be careful.
                    # We'll stick to a simple block for now.
                    pass
        return base


class UnsupportedFeatureError(TranspileError):
    """
    Raised when the transpiler encounters valid Python syntax that is not
    yet (or will never be) supported in the target Python-to-Luau dialect.
    """

    DEFAULT_HINTS: dict[str, str] = {
        "match/case": "Rewrite as if/elif chains for now.",
        "async/await": "RPy does not support asynchronous Python constructs.",
        "yield": "Generators are not supported. Use lists or explicit loops instead.",
        "multiple inheritance": "Only single inheritance is supported. Combine behaviour via composition.",
        "super()": "super() is not yet supported. Call the parent class method directly.",
        "global": "Use a table passed by reference to share state across scopes.",
        "nonlocal": "Use a table passed by reference instead of nonlocal.",
        "decorator": "Decorators are not yet supported.",
        "walrus operator": "Walrus operator (:=) is not supported.",
        "set": "Sets are not natively supported. Use a dict with True values as keys.",
        "exec": "exec() is a security risk and will never be supported.",
        "eval": "eval() is a security risk and will never be supported.",
    }

    def __init__(
        self,
        feature: str,
        line: int | None = None,
        col: int | None = None,
        filename: str | None = None,
        hint: str | None = None,
    ) -> None:
        # Set subclass-specific attribute BEFORE super().__init__ so that
        # __str__ (called inside Exception.__init__) can reference it.
        self.feature = feature
        resolved_hint = hint or self.DEFAULT_HINTS.get(feature)
        super().__init__(
            message=f"'{feature}' is not supported by RPy.",
            line=line,
            col=col,
            filename=filename,
            hint=resolved_hint,
        )

    def __str__(self) -> str:
        location = _fmt_location(self.filename, self.line, self.col)
        base = f"[UnsupportedFeatureError] {location}: '{self.feature}' is not supported."
        if self.hint:
            base += f"\n  Hint: {self.hint}"
        return base


class ParseError(TranspileError):
    """
    Raised when Python source code has a syntax error that prevents parsing.
    Wraps the underlying SyntaxError from ast.parse().
    """

    def __init__(self, syntax_error: SyntaxError, filename: str | None = None) -> None:
        self.syntax_error = syntax_error
        super().__init__(
            message=f"Python syntax error: {syntax_error.msg}",
            line=syntax_error.lineno,
            col=syntax_error.offset,
            filename=filename or syntax_error.filename,
        )

    def __str__(self) -> str:
        location = _fmt_location(self.filename, self.line, self.col)
        return f"[ParseError] {location}: {self.syntax_error.msg}"


class InternalError(TranspileError):
    """
    Raised when the transpiler reaches an unexpected state — a bug in RPy
    itself, not in user code.  Should never appear in normal use.
    """

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(
            message=f"Internal compiler error: {message}",
            line=line,
            hint="This is a bug in RPy. Please report it at the project repository.",
        )

    def __str__(self) -> str:
        location = _fmt_location(self.filename, self.line, self.col)
        return (
            f"[InternalError] {location}: {self.message}\n"
            f"  Hint: {self.hint}"
        )


class CyclicDependencyError(TranspileError):
    """
    Raised when a circular import is detected in the dependency graph.
    RPy requires the project graph to be a strict Directed Acyclic Graph (DAG).
    """

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = cycle_path
        path_str = " -> ".join(cycle_path)
        super().__init__(
            message=f"Circular import detected:\n  {path_str}",
            hint="Refactor modules to remove the mutual dependency.",
        )

    def __str__(self) -> str:
        return f"[CyclicDependencyError] {self.message}\n  Hint: {self.hint}"

