import os
import re
import subprocess

from mcp.server.fastmcp import Context

SEARCH_GLOBS = [
    "*.py",
    "*.pyi",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.toml",
    "*.ini",
    "*.cfg",
    "*.sh",
    "CMakeLists.txt",
    "*.cmake",
    "*.cpp",
    "*.cc",
    "*.c",
    "*.h",
    "*.hpp",
    "*.md",
]


async def search_code(pattern: str, path: str = ".", ctx: Context | None = None) -> str:
    try:
        if ctx:
            await ctx.info(f"Searching for '{pattern}' in {path}")
        glob_args = [arg for glob in SEARCH_GLOBS for arg in ("--glob", glob)]
        result = subprocess.run(
            ["rg", "-n", "--no-heading", *glob_args, pattern, path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return _truncate(result.stdout)
        if result.returncode == 1:
            return f"No matches found for '{pattern}'"
        raise ValueError(f"rg search failed: {result.stderr}")
    except FileNotFoundError:
        if ctx:
            await ctx.info("rg not found, using Python fallback")
        return await _native_search(pattern, path)
    except subprocess.TimeoutExpired:
        raise ValueError(f"Search timed out for pattern '{pattern}'")
    except Exception as e:
        raise ValueError(f"Search failed: {e}")


async def _native_search(pattern: str, path: str) -> str:
    matches = []
    for root, dirs, files in os.walk(path, topdown=True):
        dirs[:] = [d for d in dirs if not d.startswith((".", "__pycache__", "node_modules"))]
        for f in files:
            if not _is_searchable_file(f):
                continue
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if re.search(pattern, line):
                            rel = os.path.relpath(fp, path)
                            matches.append(f"{rel}:{i}:{line.rstrip()[:200]}")
            except (OSError, UnicodeDecodeError):
                continue
    if not matches:
        return f"No matches found for '{pattern}'"
    return _truncate("\n".join(matches[:500]))


def _is_searchable_file(filename: str) -> bool:
    if filename == "CMakeLists.txt":
        return True
    return any(
        filename.endswith(ext)
        for ext in (
            ".py",
            ".pyi",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".ini",
            ".cfg",
            ".sh",
            ".cmake",
            ".cpp",
            ".cc",
            ".c",
            ".h",
            ".hpp",
            ".md",
        )
    )


def _truncate(text: str, max_chars: int = 10000) -> str:
    if len(text) > max_chars:
        return text[:max_chars] + "\n... (truncated at 10000 chars)"
    return text
