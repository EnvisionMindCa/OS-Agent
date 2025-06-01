from __future__ import annotations

__all__ = ["execute_python"]


def execute_python(code: str) -> str:
    """Execute Python code in a sandbox with a broader set of built-ins.

    The code is executed with restricted but useful built-ins and can import a
    small whitelist of standard library modules. Results should be stored in a
    variable named ``result`` or printed. The value of ``result`` is returned if
    present; otherwise any standard output captured during execution is
    returned.
    """
    import sys
    from io import StringIO

    allowed_modules = {"math", "random", "statistics"}

    def _safe_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name in allowed_modules:
            return __import__(name, globals, locals, fromlist, level)
        raise ImportError(f"Import of '{name}' is not allowed")

    allowed_builtins = {
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "range": range,
        "sorted": sorted,
        "enumerate": enumerate,
        "map": map,
        "filter": filter,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
        "print": print,
        "__import__": _safe_import,
    }

    safe_globals: dict[str, object] = {"__builtins__": allowed_builtins}
    safe_locals: dict[str, object] = {}

    stdout = StringIO()
    original_stdout = sys.stdout
    try:
        sys.stdout = stdout
        exec(code, safe_globals, safe_locals)
    finally:
        sys.stdout = original_stdout

    if "result" in safe_locals:
        return str(safe_locals["result"])
    return stdout.getvalue().strip()
